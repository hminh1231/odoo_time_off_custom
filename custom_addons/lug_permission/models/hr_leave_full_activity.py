# -*- coding: utf-8 -*-
"""Show every leave in a full-activity manager's activity clock.

Some users are configured as approvers on one or more approval steps of a leave
type (multi-step) or of an employee's HR-responsible chain. By default the
activity systray ("đồng hồ") only surfaces a leave request when it is currently
that user's turn to approve.

When such a user is flagged with ``lug_leave_full_activity_report``, they instead
see EVERY pending leave in which they appear anywhere in the approval chain —
regardless of whether it is currently their step — so they can track how many
requests are waiting and remind whoever is stuck on the active step.
"""

from odoo import _, api, fields, models

_LEAVE_APPROVAL_ACTIVITY_XMLID = "hr_holidays.mail_act_leave_approval"


class HrLeaveFullActivity(models.Model):
    _inherit = "hr.leave"

    def activity_update(self):
        res = super().activity_update()
        self._lug_sync_full_chain_activities()
        return res

    def _lug_all_chain_approver_users(self):
        """All internal users configured on ANY approval step for this leave."""
        self.ensure_one()
        Users = self.env["res.users"]
        users = Users
        leave = self.sudo()
        vt = leave.validation_type
        if vt == "employee_hr_responsibles":
            users |= leave.responsible_approval_line_ids.mapped("user_id")
            users |= leave._get_responsible_approval_users()
        elif vt == "multi_step_6":
            for step in leave.holiday_status_id.multi_approval_step_ids:
                users |= step._get_all_approver_users()
        else:
            users |= leave.extra_approver_user_ids
            if leave.employee_id.leave_manager_id:
                users |= leave.employee_id.leave_manager_id
            if leave.holiday_status_id.responsible_ids:
                users |= leave.holiday_status_id.responsible_ids
        return users.filtered(lambda user: user and not user.share)

    def _lug_full_chain_activity_user_ids(self):
        """Full-activity managers who are somewhere in this leave's approval chain."""
        self.ensure_one()
        if self.state not in ("confirm", "validate1"):
            return self.env["res.users"]
        chain = self._lug_all_chain_approver_users()
        return chain.filtered(lambda user: user.sudo().lug_leave_full_activity_report)

    def _lug_sync_full_chain_activities(self):
        """Ensure each flagged chain manager has exactly one pending leave activity.

        A flagged manager who also happens to be the current-step approver receives
        a leave-approval activity from the core ``activity_update`` too, so we
        collapse any duplicates to keep the activity clock count accurate.
        """
        pending = self.filtered(lambda leave: leave.state in ("confirm", "validate1"))
        if not pending:
            return
        activity_type = self.env.ref(
            _LEAVE_APPROVAL_ACTIVITY_XMLID, raise_if_not_found=False
        )
        if not activity_type:
            return
        Activity = self.env["mail.activity"].sudo()
        model_id = self.env["ir.model"]._get_id("hr.leave")
        today = fields.Date.today()
        vals_list = []
        for leave in pending:
            managers = leave._lug_full_chain_activity_user_ids()
            if not managers:
                continue
            existing = Activity.search(
                [
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", leave.id),
                    ("activity_type_id", "=", activity_type.id),
                    ("user_id", "in", managers.ids),
                ]
            )
            existing_by_user = {}
            duplicates = Activity
            for activity in existing:
                if activity.user_id.id in existing_by_user:
                    duplicates |= activity
                else:
                    existing_by_user[activity.user_id.id] = activity
            if duplicates:
                duplicates.unlink()
            note = _(
                "Theo dõi toàn bộ hoạt động duyệt đơn nghỉ phép của %(employee)s.",
                employee=leave.employee_id.name or leave.display_name,
            )
            for user in managers:
                if user.id in existing_by_user:
                    continue
                vals_list.append(
                    {
                        "activity_type_id": activity_type.id,
                        "automated": True,
                        "date_deadline": today,
                        "note": note,
                        "user_id": user.id,
                        "res_id": leave.id,
                        "res_model_id": model_id,
                    }
                )
        if vals_list:
            Activity.with_context(short_name=False).create(vals_list)

    def _lug_cleanup_full_chain_activities_for_users(self, users):
        """Drop monitoring activities for users that are no longer flagged.

        A user that is still the genuine current-step approver keeps their
        activity; only the extra "monitoring" entries are removed.
        """
        activity_type = self.env.ref(
            _LEAVE_APPROVAL_ACTIVITY_XMLID, raise_if_not_found=False
        )
        if not activity_type or not users:
            return
        Activity = self.env["mail.activity"].sudo()
        model_id = self.env["ir.model"]._get_id("hr.leave")
        to_remove = Activity
        for leave in self.filtered(lambda l: l.state in ("confirm", "validate1")):
            current = leave.sudo()._get_responsible_for_approval()
            stale_users = users - current
            if not stale_users:
                continue
            to_remove |= Activity.search(
                [
                    ("res_model_id", "=", model_id),
                    ("res_id", "=", leave.id),
                    ("activity_type_id", "=", activity_type.id),
                    ("user_id", "in", stale_users.ids),
                ]
            )
        if to_remove:
            to_remove.unlink()

    @api.model
    def _lug_resync_full_activities_for_users(self, users):
        """Recompute monitoring activities after the flag changes on ``users``."""
        users = users.filtered(lambda user: user and not user.share)
        if not users:
            return
        pending = self.sudo().search([("state", "in", ("confirm", "validate1"))])
        if not pending:
            return
        flagged = users.filtered(lambda user: user.sudo().lug_leave_full_activity_report)
        if flagged:
            pending._lug_sync_full_chain_activities()
        unflagged = users - flagged
        if unflagged:
            pending._lug_cleanup_full_chain_activities_for_users(unflagged)

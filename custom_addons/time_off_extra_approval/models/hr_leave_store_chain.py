"""Store chain approval flow for hr.leave.

Sequential approval based on the employee's job title and Mã bộ phận.
All approval mechanics (responsible_approval_line_ids, action_responsible_approve,
notifications, timeout escalation) are shared with employee_hr_responsibles.

Approval flows:
  Cửa hàng trưởng → ASM → RSM         (pool by Mã bộ phận)
                  → org-chart above RSM (sequential) → Admin

ASM, RSM, and Giám sát use the leave type's configured org-chart approvers
(employee_hr_responsibles, sequential) — they do not enter this store chain.

Balance check (con_lai):
  All job titles in _CON_LAI_CHECKED_JOB_TITLES are blocked from creating or
  confirming a leave when their con_lai ≤ 0, regardless of the leave type's
  validation flow.
"""

import logging

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TODO: replace each placeholder with the real Odoo badge ID (barcode field).
# ---------------------------------------------------------------------------
_BADGE_ADMIN = "TODO_ADMIN_BADGE_ID"   # also used as Thủy (Admin) for refusal notification
# ---------------------------------------------------------------------------

# Job title keys (from hr_job_title_vn) that trigger the store chain flow.
_STORE_CHAIN_JOB_TITLES = frozenset({
    "cửa hàng trưởng",
})

# Job title keys whose con_lai must be > 0 before any leave can be created or confirmed.
# Covers all retail/store staff regardless of which approval flow their leave type uses.
_CON_LAI_CHECKED_JOB_TITLES = frozenset({
    "nhân viên ch",
    "cửa hàng trưởng",
    "asm",
    "rsm",
    "giám sát",
})


class HrLeaveStoreChain(models.Model):
    _inherit = "hr.leave"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _store_chain_employee_job_title(self):
        """Return the raw (lowercase, stripped) job_title key of the leave's employee."""
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return ""
        return (emp.job_title or "").strip().lower()

    def _is_store_chain_flow(self):
        self.ensure_one()
        return (
            self.validation_type == "vp_chain"
            and self._store_chain_employee_job_title() in _STORE_CHAIN_JOB_TITLES
        )

    def _store_chain_find_user_by_badge(self, badge_id):
        """Return the internal res.users for the employee with that Odoo badge ID (barcode)."""
        if not badge_id or badge_id.startswith("TODO_"):
            _logger.warning(
                "time_off_extra_approval: store chain badge ID placeholder not filled: %s", badge_id
            )
            return self.env["res.users"]
        emp = self.env["hr.employee"].sudo().search(
            [("barcode", "=", badge_id)], limit=1
        )
        if not emp:
            _logger.warning(
                "time_off_extra_approval: store chain — no employee for barcode=%s", badge_id
            )
            return self.env["res.users"]
        user = emp.user_id
        if not user or user.share:
            _logger.warning(
                "time_off_extra_approval: store chain — employee %s (barcode=%s) has no internal user",
                emp.name,
                badge_id,
            )
            return self.env["res.users"]
        return user

    def _store_chain_find_employee_by_title_and_dept(self, job_title_key, ma_bo_phan):
        """Return the first hr.employee with given job title and Mã bộ phận (no user required)."""
        if not ma_bo_phan:
            return self.env["hr.employee"]
        return self.env["hr.employee"].sudo().search(
            [
                ("job_title", "=", job_title_key),
                ("ma_bo_phan", "=", ma_bo_phan),
            ],
            limit=1,
        )

    def _store_chain_find_user_by_title_and_dept(self, job_title_key, ma_bo_phan):
        """Return the internal user for the first employee with given job title and Mã bộ phận."""
        if not ma_bo_phan:
            _logger.warning(
                "time_off_extra_approval: store chain — employee has no Mã bộ phận, cannot find %s approver",
                job_title_key,
            )
            return self.env["res.users"]
        emp = self.env["hr.employee"].sudo().search(
            [
                ("job_title", "=", job_title_key),
                ("ma_bo_phan", "=", ma_bo_phan),
                ("user_id", "!=", False),
            ],
            limit=1,
        )
        if not emp:
            _logger.warning(
                "time_off_extra_approval: store chain — no employee for job_title=%s ma_bo_phan=%s",
                job_title_key,
                ma_bo_phan,
            )
            return self.env["res.users"]
        user = emp.user_id
        if user.share:
            _logger.warning(
                "time_off_extra_approval: store chain — employee %s (job_title=%s, ma_bo_phan=%s) has only portal/shared user",
                emp.name,
                job_title_key,
                ma_bo_phan,
            )
            return self.env["res.users"]
        return user

    def _store_chain_org_chain_from_employee(self, start_emp, stop_badge=None):
        """Walk parent_id org chain upward from start_emp (exclusive — start_emp itself is not added).

        Stops and includes the employee whose barcode == stop_badge when given.
        Returns res.users in order (closest manager first).
        """
        user_ids = []
        seen = set()
        cur = start_emp.sudo().parent_id if start_emp else None
        while cur:
            if cur.user_id and not cur.user_id.share:
                uid = cur.user_id.id
                if uid not in seen:
                    user_ids.append(uid)
                    seen.add(uid)
                if stop_badge and (cur.barcode or "") == stop_badge:
                    break
            cur = cur.parent_id
        return self.env["res.users"].browse(user_ids)

    def _store_chain_after_rsm_approver_users(self, rsm_emp):
        """Org-chart chain starting above RSM, with Admin (Thủy) appended as final approver."""
        user_ids = []
        seen = set()

        def _add(user):
            if user and user.id and user.id not in seen:
                user_ids.append(user.id)
                seen.add(user.id)

        for user in self._store_chain_org_chain_from_employee(rsm_emp):
            _add(user)
        _add(self._store_chain_find_user_by_badge(_BADGE_ADMIN))
        return self.env["res.users"].browse(user_ids)

    def _get_store_chain_approver_users(self):
        """Build the ordered approver list for the store chain flow.

        Returns res.users in sequential approval order (first = approves first).
        Duplicate users are silently dropped (shouldn't happen in practice).
        """
        self.ensure_one()
        Users = self.env["res.users"]
        title = self._store_chain_employee_job_title()
        emp = self.employee_id
        ma_bo_phan = emp.sudo().ma_bo_phan if emp else False

        user_ids = []
        seen = set()

        def _add(user):
            if user and user.id and user.id not in seen:
                user_ids.append(user.id)
                seen.add(user.id)

        if title == "cửa hàng trưởng":
            # CHT → ASM → RSM (pool by ma_bo_phan) → org-chain above RSM → Admin
            _add(self._store_chain_find_user_by_title_and_dept("asm", ma_bo_phan))
            rsm_emp = self._store_chain_find_employee_by_title_and_dept("rsm", ma_bo_phan)
            _add(rsm_emp.user_id if rsm_emp and rsm_emp.user_id and not rsm_emp.user_id.share else self.env["res.users"])
            for user in self._store_chain_after_rsm_approver_users(rsm_emp):
                _add(user)

        return Users.browse(user_ids)

    # ------------------------------------------------------------------
    # Refusal notification
    # ------------------------------------------------------------------

    def _store_chain_notify_refusal_to_admin(self, refusal_reason=None, refuser_name=None):
        """Notify Admin (Thủy) via Discuss bot when a store chain leave is refused.

        The requester is already notified by the base action_refuse flow.
        This method adds a separate DM to Admin (Thủy) so she is always informed.
        """
        self.ensure_one()
        from odoo.tools.translate import _

        admin_user = self._store_chain_find_user_by_badge(_BADGE_ADMIN)
        if not admin_user or not admin_user.partner_id:
            return

        leave_date = self.request_date_from or (self.date_from and self.date_from.date())
        leave_date_text = leave_date.strftime("%d/%m/%Y") if leave_date else ""
        reason_text = (refusal_reason or self.last_refusal_reason or "").strip()
        by_text = refuser_name or (self.last_refuser_id and self.last_refuser_id.display_name) or _("người duyệt")

        if reason_text:
            body = _(
                "Đơn xin nghỉ ngày %(date)s của %(employee)s đã bị từ chối bởi %(refuser)s "
                "với lý do: %(reason)s."
            ) % {
                "date": leave_date_text,
                "employee": self.employee_id.name or "",
                "refuser": by_text,
                "reason": reason_text,
            }
        else:
            body = _(
                "Đơn xin nghỉ ngày %(date)s của %(employee)s đã bị từ chối bởi %(refuser)s."
            ) % {
                "date": leave_date_text,
                "employee": self.employee_id.name or "",
                "refuser": by_text,
            }

        bot_user = self.env.ref("business_discuss_bots.user_bot_approval", raise_if_not_found=False)
        if not bot_user:
            bot_user = self.env.ref("base.user_root")
        try:
            chat = (
                self.env["discuss.channel"]
                .with_user(bot_user)
                .sudo()
                ._get_or_create_chat([admin_user.partner_id.id], pin=True)
            )
            chat.with_user(bot_user).sudo().message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        except Exception:
            _logger.exception(
                "time_off_extra_approval: store chain — failed to send refusal notify to admin "
                "leave_id=%s admin_user_id=%s",
                self.id,
                admin_user.id,
            )

    # ------------------------------------------------------------------
    # Balance check (con_lai) — applies to all retail job titles
    # ------------------------------------------------------------------

    def _check_con_lai_balance(self):
        """Raise ValidationError for any retail employee whose con_lai ≤ 0."""
        for leave in self:
            emp = leave.employee_id.sudo()
            if not emp:
                continue
            title = (emp.job_title or "").strip().lower()
            if title not in _CON_LAI_CHECKED_JOB_TITLES:
                continue
            if (emp.con_lai or 0) <= 0:
                raise ValidationError(
                    _(
                        "Nhân viên %(name)s không còn đủ ngày phép (Còn lại: %(remaining)s). "
                        "Không thể tạo đơn xin nghỉ.",
                        name=emp.name,
                        remaining=emp.con_lai or 0,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("leave_fast_create"):
            records._check_con_lai_balance()
        return records

    def action_confirm(self):
        self._check_con_lai_balance()
        return super().action_confirm()

    # ------------------------------------------------------------------
    # Override: plug into the shared responsible-flow machinery
    # ------------------------------------------------------------------

    def _get_responsible_approval_users(self):
        self.ensure_one()
        if self._is_store_chain_flow():
            return self._get_store_chain_approver_users()
        return super()._get_responsible_approval_users()

    def action_responsible_refuse(self, reason=False):
        res = super().action_responsible_refuse(reason=reason)
        if self._is_store_chain_flow():
            self._store_chain_notify_refusal_to_admin(
                refusal_reason=reason or self.env.context.get("refusal_reason"),
                refuser_name=self.env.user.display_name,
            )
        return res

"""Store chain approval flow for hr.leave.

Sequential approval based on the employee's job title and Mã bộ phận.
All approval mechanics (responsible_approval_line_ids, action_responsible_approve,
notifications, timeout escalation) are shared with employee_hr_responsibles.

Approval flows (Nhóm trưởng / Cửa hàng trưởng):
  The chain follows the org chart (hr.employee.parent_id), one approver per level.
  ASM is the anchor/first step (preferring the Work Handover ASM); the walk then
  continues upward from the ASM's reporting line.
  The chain STOPS at the first job title flagged as "Mức duyệt cuối" (is_final_level)
  in the OdooBot Duyệt đơn config (hr.leave.odoobot.notify.rule), matched by the
  requester's Miền. If no final-level title is met, the chain stops at the topmost
  approver found on the org chart (no hard-coded "admin tổng" anymore).

ASM, RSM, and Giám sát use the leave type's configured org-chart approvers
(employee_hr_responsibles, sequential) — they do not enter this store chain.

Balance warning (con_lai):
  When con_lai ≤ 0, hr_employee_hrm_detail shows a confirmation dialog on save
  (all employees, all leave types). This module does not hard-block creation.
"""

import logging

from odoo import api, fields, models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TODO: replace each placeholder with the real Odoo badge ID (barcode field).
# ---------------------------------------------------------------------------
_BADGE_ADMIN = "TODO_ADMIN_BADGE_ID"   # also used as Thủy (Admin) for refusal notification
# ---------------------------------------------------------------------------

# Job title keys (from hr_job_title_vn) that trigger the store chain flow.
# "nhóm trưởng" = store group leader (part of chain); "trưởng nhóm" = internal team lead (separate title, not in chain).
_STORE_CHAIN_JOB_TITLES = frozenset({
    "nhóm trưởng",
    "cửa hàng trưởng",
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

    def _is_store_chain_validation_type(self):
        self.ensure_one()
        return self.validation_type in ("vp_chain", "employee_hr_responsibles")

    def _is_store_chain_flow(self):
        self.ensure_one()
        return self._is_store_chain_validation_type() and (
            self._store_chain_employee_job_title() in _STORE_CHAIN_JOB_TITLES
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

    def _store_chain_user_from_employee(self, employee):
        """Return employee's internal user, or an empty res.users recordset."""
        if employee and employee.user_id and not employee.user_id.share:
            return employee.user_id
        return self.env["res.users"]

    def _store_chain_handover_asm_employee(self):
        """ASM explicitly selected on Work Handover To, if any."""
        self.ensure_one()
        employees = (
            self.handover_acceptance_ids.mapped("employee_id")
            | self.handover_employee_ids
        )
        return employees.sudo().filtered(
            lambda emp: (emp.job_title or "").strip().lower() == "asm"
            and emp.user_id
            and not emp.user_id.share
        )[:1]

    def _store_chain_existing_asm_approval_employee(self):
        """ASM already present in approval lines, useful for old in-flight tickets."""
        self.ensure_one()
        lines = self.responsible_approval_line_ids.sorted(
            lambda line: (line.sequence, line.id)
        )
        for line in lines:
            employee = line.user_id.sudo().employee_id
            if employee and (employee.job_title or "").strip().lower() == "asm":
                return employee
        return self.env["hr.employee"]

    def _store_chain_asm_anchor_employee(self, ma_bo_phan):
        """Best ASM anchor for the store chain.

        Prefer the selected handover ASM because that is the person actually
        receiving and approving this ticket. Fall back to existing approval
        lines for old tickets, then to the Mã bộ phận pool lookup.
        """
        self.ensure_one()
        return (
            self._store_chain_handover_asm_employee()
            or self._store_chain_existing_asm_approval_employee()
            or self._store_chain_find_employee_by_title_and_dept("asm", ma_bo_phan)
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

    def _store_chain_find_user_on_requester_org_chain(self, job_title_key):
        """Find approver only on the requester's upward org chart (parent_id chain)."""
        self.ensure_one()
        cur = self.employee_id.sudo().parent_id
        while cur:
            if (cur.job_title or "").strip().lower() == job_title_key:
                user = self._store_chain_user_from_employee(cur)
                if user:
                    return user
            cur = cur.parent_id
        return self.env["res.users"]

    def _store_chain_title_is_final(self, job_title_key, mien):
        """True when the OdooBot Duyệt đơn config flags this title as the final level for ``mien``."""
        self.ensure_one()
        if not job_title_key or not mien:
            return False
        rule = self._odoobot_notify_rule_env()._find_rule(
            company=self.company_id,
            mien=mien,
            job_title=job_title_key,
            bot_type="approval",
        )
        return bool(rule and rule.is_final_level)

    def _store_chain_anchor_user_and_employee(self, ma_bo_phan):
        """Resolve the ASM anchor user (and its employee) that starts the chain.

        Prefer the Work Handover ASM, then an ASM already on the approval lines,
        then the Mã bộ phận pool, then any ASM on the requester's org chart.
        Returns (user, employee); both may be empty recordsets.
        """
        self.ensure_one()
        asm_emp = self._store_chain_asm_anchor_employee(ma_bo_phan)
        user = self._store_chain_user_from_employee(asm_emp)
        if user:
            return user, asm_emp
        user = self._store_chain_find_user_by_title_and_dept("asm", ma_bo_phan)
        if user:
            return user, user.sudo().employee_id
        user = self._store_chain_find_user_on_requester_org_chain("asm")
        if user:
            return user, user.sudo().employee_id
        return self.env["res.users"], self.env["hr.employee"]

    def _get_store_chain_approver_users(self):
        """Build the ordered approver list for the store chain flow.

        Walks the org chart (parent_id) one approver per level, starting from the ASM
        anchor (Work Handover ASM preferred). Stops at the first title flagged as the
        final level ("Mức duyệt cuối") in the OdooBot Duyệt đơn config for the
        requester's Miền; otherwise stops at the topmost approver on the org chart.
        Returns res.users in sequential approval order (first = approves first).
        """
        self.ensure_one()
        Users = self.env["res.users"]
        title = self._store_chain_employee_job_title()
        if title not in _STORE_CHAIN_JOB_TITLES:
            return Users

        emp = self.employee_id
        ma_bo_phan = emp.sudo().ma_bo_phan if emp else False
        requester_mien = self._leave_request_mien()

        user_ids = []
        seen = set()

        def _add(user):
            if user and user.id and user.id not in seen:
                user_ids.append(user.id)
                seen.add(user.id)
                return True
            return False

        # ASM anchor opens the chain; the org-chart walk continues from its reporting line.
        anchor_user, anchor_emp = self._store_chain_anchor_user_and_employee(ma_bo_phan)
        walk_start_emp = anchor_emp or (emp.sudo() if emp else self.env["hr.employee"])

        stop = False
        if anchor_user and _add(anchor_user):
            if self._store_chain_title_is_final("asm", requester_mien):
                stop = True

        if not stop:
            cur = walk_start_emp.sudo().parent_id if walk_start_emp else self.env["hr.employee"]
            visited = set()
            while cur and cur.id not in visited:
                visited.add(cur.id)
                cur_title = (cur.job_title or "").strip().lower()
                user = self._store_chain_user_from_employee(cur)
                if user and _add(user):
                    if self._store_chain_title_is_final(cur_title, requester_mien):
                        break
                cur = cur.sudo().parent_id

        # Last-resort safety so a request is never left with no approver at all.
        if not user_ids:
            _add(self._store_chain_find_user_by_badge(_BADGE_ADMIN))

        _logger.info(
            "time_off_extra_approval: store chain approvers leave_id=%s title=%s ma_bo_phan=%s mien=%s users=%s",
            self.id,
            title,
            ma_bo_phan,
            requester_mien,
            Users.browse(user_ids).mapped("login"),
        )
        return Users.browse(user_ids)

    def _store_chain_reconcile_approval_lines(self):
        """Align approval log with the computed store-chain approvers (create missing, compact 1..n)."""
        self.ensure_one()
        if not self.id or not self._is_store_chain_flow():
            return
        users = self._get_store_chain_approver_users()
        if not users:
            return
        line_model = self.env["hr.leave.responsible.approval"].sudo()
        existing_by_user = {ln.user_id.id: ln for ln in self.responsible_approval_line_ids}
        expected_user_ids = set(users.ids)
        for ln in self.responsible_approval_line_ids.filtered(
            lambda line: line.state == "pending" and line.user_id.id not in expected_user_ids
        ):
            ln.write(
                {
                    "state": "skipped",
                    "action_date": fields.Datetime.now(),
                }
            )
        has_active_wave = bool(
            self.with_context(skip_responsible_auto_skip_pending=True)._responsible_pending_current_wave_raw()
        )
        now = fields.Datetime.now()
        for seq, user in enumerate(users, start=1):
            line = existing_by_user.get(user.id)
            if line:
                if line.sequence != seq:
                    line.write({"sequence": seq})
                continue
            vals = {
                "leave_id": self.id,
                "user_id": user.id,
                "sequence": seq,
            }
            if not has_active_wave and seq == 1:
                vals["pending_since"] = now
                has_active_wave = True
            line_model.create(vals)
            _logger.info(
                "time_off_extra_approval: store chain reconciled approval line leave_id=%s user=%s sequence=%s",
                self.id,
                user.login,
                seq,
            )

    def _store_chain_ensure_missing_approval_lines(self):
        """Backward-compatible alias for reconcile."""
        self._store_chain_reconcile_approval_lines()

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
    # Override: plug into the shared responsible-flow machinery
    # ------------------------------------------------------------------

    def _sync_responsible_approval_lines(self):
        """Keep store-chain approval log rows aligned with the computed approver chain."""
        hook = getattr(super(), "_sync_responsible_approval_lines", None)
        if hook:
            hook()
        for leave in self.filtered(lambda leave: leave._is_store_chain_flow()):
            leave._store_chain_reconcile_approval_lines()

    def _get_responsible_approval_users_override(self):
        hook = getattr(super(), "_get_responsible_approval_users_override", None)
        res = hook() if hook else None
        if res is not None:
            return res
        if self._is_store_chain_flow():
            return self._get_store_chain_approver_users()
        return None

    def _store_chain_notify_all_remaining_approvers(self):
        """After the Mã bộ phận (ASM) step completes, notify every still-pending approver.

        The sequential order is preserved — only the next-in-line can actually approve —
        but all remaining approvers receive the bot DM so they know the ticket is coming.
        The next-wave approver was already notified by _notify_responsible_current_turn();
        we notify the others here (they are pending but not the current wave).
        """
        self.ensure_one()
        already_notified = self._responsible_pending_current_wave().mapped("user_id")
        remaining = self.responsible_approval_line_ids.filtered(
            lambda ln: ln.state == "pending" and ln.user_id not in already_notified
        )
        for ln in remaining:
            user = ln.user_id
            if not user or user.share or not user.partner_id:
                continue
            try:
                self._notify_responsible_current_turn_via_approval_bot(user)
            except Exception:
                _logger.exception(
                    "time_off_extra_approval: store chain — failed to notify remaining approver "
                    "leave_id=%s user_id=%s",
                    self.id,
                    user.id,
                )

    def _responsible_approval_before_approve(self):
        hook = getattr(super(), "_responsible_approval_before_approve", None)
        res = hook() if hook else None
        if not self._is_store_chain_flow():
            return res
        self._store_chain_ensure_missing_approval_lines()
        _logger.info(
            "time_off_extra_approval: store chain before approve leave_id=%s approver=%s approved_seq=%s lines=%s",
            self.id,
            self.env.user.login,
            self.responsible_approval_line_ids.filtered(
                lambda line: line.user_id == self.env.user and line.state == "pending"
            )[:1].sequence,
            [
                (line.sequence, line.user_id.login, line.state)
                for line in self.responsible_approval_line_ids.sorted(lambda l: (l.sequence, l.id))
            ],
        )
        return res

    def _responsible_approval_after_approve(self, approved_line=None):
        hook = getattr(super(), "_responsible_approval_after_approve", None)
        res = hook(approved_line=approved_line) if hook else None
        if not self._is_store_chain_flow():
            return res
        # After the Mã bộ phận (sequence-1) step is done, notify all remaining approvers.
        if approved_line and approved_line.sequence == 1:
            self._store_chain_notify_all_remaining_approvers()

        _logger.info(
            "time_off_extra_approval: store chain after approve leave_id=%s lines=%s current_wave=%s",
            self.id,
            [
                (line.sequence, line.user_id.login, line.state)
                for line in self.responsible_approval_line_ids.sorted(lambda l: (l.sequence, l.id))
            ],
            self._responsible_pending_current_wave().mapped("user_id.login"),
        )
        return res

    def action_responsible_refuse(self, reason=False):
        res = super().action_responsible_refuse(reason=reason)
        if self._is_store_chain_flow():
            self._store_chain_notify_refusal_to_admin(
                refusal_reason=reason or self.env.context.get("refusal_reason"),
                refuser_name=self.env.user.display_name,
            )
        return res

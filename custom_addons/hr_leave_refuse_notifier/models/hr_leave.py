# -*- coding: utf-8 -*-
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = "hr.leave"

    def _notify_manager(self):
        result = super()._notify_manager()
        try:
            self._notify_refuse_ticket_notifier()
        except Exception:
            _logger.exception("hr_leave_refuse_notifier: failed to notify refuse ticket notifier")
        return result

    def _notify_refuse_ticket_notifier(self):
        for leave in self:
            employee = leave.holiday_status_id.refuse_notify_employee_id
            if not employee or not employee.user_id:
                _logger.info(
                    "hr_leave_refuse_notifier: skip leave_id=%s employee=%s has_user=%s",
                    leave.id,
                    employee.id if employee else None,
                    bool(employee.user_id) if employee else False,
                )
                continue
            _logger.info(
                "hr_leave_refuse_notifier: notifying employee_id=%s (%s) for leave_id=%s",
                employee.id,
                employee.user_id.login,
                leave.id,
            )
            leave.sudo().message_post(
                partner_ids=employee.user_id.partner_id.ids,
                body=_(
                    "%(leave_name)s has been refused.",
                    leave_name=leave.display_name,
                ),
                subtype_xmlid="mail.mt_comment",
            )

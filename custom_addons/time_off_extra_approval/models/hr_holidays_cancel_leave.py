from odoo import fields, models, _


class HrHolidaysCancelLeave(models.TransientModel):
    _inherit = "hr.holidays.cancel.leave"

    # Dashboard popup may open cancel wizard before leave is persisted.
    # Keep field optional here to avoid technical ValidationError on wizard creation.
    leave_id = fields.Many2one("hr.leave", string="Đơn xin nghỉ phép", required=False)

    def action_cancel_leave(self):
        self.ensure_one()
        if not self.leave_id:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "message": _("Vui lòng lưu/gửi đơn xin nghỉ phép trước khi hủy."),
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        return super().action_cancel_leave()

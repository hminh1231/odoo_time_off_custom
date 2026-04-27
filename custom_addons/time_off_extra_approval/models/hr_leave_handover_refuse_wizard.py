from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HrLeaveHandoverRefuseWizard(models.TransientModel):
    _name = "hr.leave.handover.refuse.wizard"
    _description = "Lý do từ chối bàn giao công việc"

    leave_id = fields.Many2one("hr.leave", string="Đơn xin nghỉ phép", required=True, readonly=True)
    reason = fields.Text(string="Lý do", required=True)

    def action_submit(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if not reason:
            raise ValidationError(_("Vui lòng nhập lý do trước khi gửi."))
        self.leave_id.action_handover_refuse_with_reason(reason)
        return {"type": "ir.actions.act_window_close"}

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HrLeaveHandoverRefuseWizard(models.TransientModel):
    _name = "hr.leave.handover.refuse.wizard"
    _description = "Reason for refusing work handover"

    leave_id = fields.Many2one("hr.leave", string="Time Off Request", required=True, readonly=True)
    reason = fields.Text(string="Reason", required=True)

    def action_submit(self):
        self.ensure_one()
        reason = (self.reason or "").strip()
        if not reason:
            raise ValidationError(_("Please provide a reason before submitting."))
        self.leave_id.action_handover_refuse_with_reason(reason)
        return {"type": "ir.actions.act_window_close"}

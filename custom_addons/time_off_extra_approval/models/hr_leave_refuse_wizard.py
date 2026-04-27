from odoo import api, fields, models
from odoo.exceptions import UserError


class HrLeaveRefuseWizard(models.TransientModel):
    _name = "hr.leave.refuse.wizard"
    _description = "Time Off Refuse Reason Wizard"

    reason = fields.Text(string="Lý do", required=True)
    leave_ids = fields.Many2many("hr.leave", string="Đơn xin nghỉ phép")
    refuse_action = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("multi_step", "Multi-step"),
            ("responsible", "Responsible"),
        ],
        default="standard",
        required=True,
    )

    @api.model
    def default_get(self, field_list):
        defaults = super().default_get(field_list)
        if "leave_ids" in field_list and not defaults.get("leave_ids"):
            defaults["leave_ids"] = self.env.context.get("active_ids", [])
        return defaults

    def action_refuse(self):
        self.ensure_one()
        if self.refuse_action == "multi_step":
            if len(self.leave_ids) != 1:
                raise UserError("Chỉ hỗ trợ từ chối theo bước cho từng đơn riêng lẻ.")
            self.leave_ids.action_multi_step_refuse(reason=self.reason)
        elif self.refuse_action == "responsible":
            if len(self.leave_ids) != 1:
                raise UserError("Chỉ hỗ trợ từ chối theo người phụ trách cho từng đơn riêng lẻ.")
            self.leave_ids.action_responsible_refuse(reason=self.reason)
        else:
            self.leave_ids.action_refuse(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}

from odoo import fields, models


class HrLeaveHandoverAcceptance(models.Model):
    _name = "hr.leave.handover.acceptance"
    _description = "Work handover acknowledgement"
    _order = "id"

    leave_id = fields.Many2one(
        comodel_name="hr.leave",
        string="Time Off",
        required=True,
        ondelete="cascade",
        index=True,
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Recipient",
        required=True,
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("refused", "Refused"),
        ],
        string="Response",
        default="pending",
        required=True,
    )
    responded_at = fields.Datetime(string="Responded On")
    refusal_reason = fields.Text(string="Refusal Reason")

    _sql_constraints = [
        (
            "leave_employee_unique",
            "unique(leave_id, employee_id)",
            "Each colleague can only have one work handover line per time off request.",
        ),
    ]

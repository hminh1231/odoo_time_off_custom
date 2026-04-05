from odoo import fields, models


class HrLeaveResponsibleApproval(models.Model):
    _name = "hr.leave.responsible.approval"
    _description = "Time Off Employee Responsible Approval Log"
    _order = "sequence, id"

    leave_id = fields.Many2one(
        comodel_name="hr.leave",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        ondelete="restrict",
        index=True,
    )
    sequence = fields.Integer(required=True, default=1, index=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("refused", "Refused"),
        ],
        required=True,
        default="pending",
    )
    action_date = fields.Datetime()

    _sql_constraints = [
        (
            "leave_user_unique",
            "UNIQUE(leave_id, user_id)",
            "A responsible user can only appear once per leave request.",
        ),
    ]

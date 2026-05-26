from odoo import api, fields, models

_SKIP_SPECIAL_EMPLOYEE_RESEQUENCE = "skip_special_employee_line_resequence"

# Matches _ORG_CHART_STOP_JOB_POSITIONS / _ORG_CHART_STOP_JOB_POSITIONS_GIAM_SAT in responsible_approval.
_STOP_POSITION_SELECTION = [
    ("sale admin", "SALE ADMIN"),
    ("human resources manager", "Human Resources Manager"),
]


def _sequence_as_int(seq):
    if seq is False or seq is None:
        return 0
    return int(seq)


class HrLeaveTypeSpecialEmployeeLine(models.Model):
    _name = "hr.leave.type.special.employee.line"
    _description = "Time Off Type — special employees requiring all directors approval"
    _order = "sequence, id"

    leave_type_id = fields.Many2one(
        comodel_name="hr.leave.type",
        string="Time Off Type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="STT", default=1)
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee",
        required=True,
        ondelete="cascade",
    )
    org_chart_stop_position = fields.Selection(
        selection=_STOP_POSITION_SELECTION,
        string="Stop at Job Position",
        help="Org-chart walk stops (inclusive) at the first approver with this Job Position. "
             "Leave empty to use the default stop position for the employee's job title.",
    )

    _sql_constraints = [
        (
            "leave_type_employee_unique",
            "unique(leave_type_id, employee_id)",
            "Each employee can only appear once in the special list for this time off type.",
        ),
    ]

    @api.onchange("employee_id")
    def _onchange_resequence_lines_realtime(self):
        """Same idea as handover acceptance: keep STT 1..n while editing in the form (incl. popup)."""
        for line in self:
            lt = line.leave_type_id
            if not lt:
                continue
            for idx, sibling in enumerate(lt.special_director_employee_line_ids, start=1):
                sibling.sequence = idx

    @api.model
    def _resequence_by_leave_type(self, leave_type_ids):
        """Pack STT to 1..n after create/write/unlink (mirrors hr.leave.handover.acceptance)."""
        if not leave_type_ids:
            return
        for lt_id in set(leave_type_ids):
            lines = self.search([("leave_type_id", "=", lt_id)], order="sequence,id")
            for idx, rec in enumerate(lines, start=1):
                if _sequence_as_int(rec.sequence) != idx:
                    rec.with_context(**{_SKIP_SPECIAL_EMPLOYEE_RESEQUENCE: True}).write(
                        {"sequence": idx}
                    )

    @api.model_create_multi
    def create(self, vals_list):
        Line = self.env["hr.leave.type.special.employee.line"]
        for vals in vals_list:
            if "sequence" in vals and vals.get("sequence"):
                continue
            ltid = (
                vals.get("leave_type_id")
                or self.env.context.get("default_leave_type_id")
                or (
                    self.env.context.get("active_id")
                    if self.env.context.get("active_model") == "hr.leave.type"
                    else False
                )
            )
            if ltid:
                vals["leave_type_id"] = ltid
                siblings = Line.search([("leave_type_id", "=", ltid)])
                max_seq = max(
                    (_sequence_as_int(s) for s in siblings.mapped("sequence")),
                    default=0,
                )
                vals["sequence"] = max_seq + 1
            else:
                vals["sequence"] = 1
        records = super().create(vals_list)
        records._resequence_by_leave_type(records.mapped("leave_type_id").ids)
        return records

    def write(self, vals):
        if self.env.context.get(_SKIP_SPECIAL_EMPLOYEE_RESEQUENCE):
            return super().write(vals)
        old_lt = self.mapped("leave_type_id").ids
        res = super().write(vals)
        new_lt = self.mapped("leave_type_id").ids
        if "sequence" in vals or "leave_type_id" in vals:
            self._resequence_by_leave_type(old_lt + new_lt)
        return res

    def unlink(self):
        lt_ids = self.mapped("leave_type_id").ids
        res = super().unlink()
        self._resequence_by_leave_type(lt_ids)
        return res

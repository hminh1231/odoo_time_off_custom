from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

_SKIP_SPECIAL_EMPLOYEE_RESEQUENCE = "skip_special_employee_line_resequence"

_LEGACY_STOP_POSITION_SELECTION = [
    ("sale admin", "SALE ADMIN"),
    ("human resources manager", "Human Resources Manager"),
]


def _sequence_as_int(seq):
    if seq is False or seq is None:
        return 0
    return int(seq)


class HrLeaveTypeSpecialEmployeeLine(models.Model):
    _name = "hr.leave.type.special.employee.line"
    _description = "Time Off Type Special Employee Approval"
    _order = "sequence, id"

    leave_type_id = fields.Many2one(
        comodel_name="hr.leave.type",
        string="Time Off Type",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="STT", default=1)
    employee_hrm_id = fields.Char(
        string="Employee",
        index=True,
        help="Enter the employee's ID HRM. The employee is resolved automatically.",
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Linked Employee",
        required=True,
        ondelete="cascade",
    )
    approval_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        relation="hr_leave_type_special_employee_approver_rel",
        column1="line_id",
        column2="employee_id",
        string="Approvals Employee",
        required=True,
        domain=[("user_id", "!=", False)],
        help="Every selected employee must approve, in organization-chart order. "
        "Each employee must have an active internal user.",
    )
    readonly_notifier_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        relation="hr_leave_type_special_employee_notifier_rel",
        column1="line_id",
        column2="employee_id",
        string="Read only Notifier",
        domain=[("user_id", "!=", False)],
        help="Employees who receive a read-only Discuss DM when this special employee submits a request.",
    )
    org_chart_stop_position = fields.Selection(
        selection=_LEGACY_STOP_POSITION_SELECTION,
        string="Legacy Stop at Job Position",
        help="Compatibility field for existing rows without explicit approval employees.",
    )

    _sql_constraints = [
        (
            "leave_type_employee_unique",
            "unique(leave_type_id, employee_id)",
            "Each employee can only appear once in the special list for this time off type.",
        ),
    ]

    @api.model
    def _employee_from_hrm_id(self, employee_hrm_id):
        employee_hrm_id = (employee_hrm_id or "").strip()
        if not employee_hrm_id:
            return self.env["hr.employee"]
        return (
            self.env["hr.employee"]
            .sudo()
            .with_context(active_test=False)
            .search([("id_hrm", "=", employee_hrm_id)], limit=1)
        )

    @api.onchange("employee_hrm_id")
    def _onchange_employee_hrm_id(self):
        for line in self:
            line.employee_hrm_id = (line.employee_hrm_id or "").strip()
            line.employee_id = line._employee_from_hrm_id(line.employee_hrm_id)
            if line.employee_hrm_id and not line.employee_id:
                return {
                    "warning": {
                        "title": _("ID HRM not found"),
                        "message": _("No employee was found with ID HRM %(id_hrm)s.")
                        % {"id_hrm": line.employee_hrm_id},
                    }
                }
        return None

    @api.onchange("employee_hrm_id", "employee_id")
    def _onchange_resequence_lines_realtime(self):
        """Same idea as handover acceptance: keep STT 1..n while editing in the form (incl. popup)."""
        for line in self:
            lt = line.leave_type_id
            if not lt:
                continue
            for idx, sibling in enumerate(lt.special_director_employee_line_ids, start=1):
                sibling.sequence = idx

    @api.constrains("employee_hrm_id", "employee_id")
    def _check_employee_hrm_link(self):
        for line in self:
            employee_hrm_id = (line.employee_hrm_id or "").strip()
            employee = line._employee_from_hrm_id(employee_hrm_id)
            if not employee:
                raise ValidationError(
                    _("No employee was found with ID HRM %(id_hrm)s.")
                    % {"id_hrm": employee_hrm_id or "—"}
                )
            if employee != line.employee_id:
                raise ValidationError(
                    _("ID HRM %(id_hrm)s does not match the linked employee.")
                    % {"id_hrm": employee_hrm_id}
                )

    @api.constrains("approval_employee_ids", "readonly_notifier_employee_ids")
    def _check_notification_employees_have_internal_users(self):
        for line in self:
            if not line.approval_employee_ids:
                raise ValidationError(
                    _("Select at least one Approvals Employee.")
                )
            for employee in line.approval_employee_ids | line.readonly_notifier_employee_ids:
                if not employee.user_id or employee.user_id.share or not employee.user_id.active:
                    raise ValidationError(
                        _("%(employee)s must have an active internal user.")
                        % {"employee": employee.display_name}
                    )

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
            employee_hrm_id = (vals.get("employee_hrm_id") or "").strip()
            if employee_hrm_id:
                employee = self._employee_from_hrm_id(employee_hrm_id)
                if not employee:
                    raise ValidationError(
                        _("No employee was found with ID HRM %(id_hrm)s.")
                        % {"id_hrm": employee_hrm_id}
                    )
                vals["employee_hrm_id"] = employee_hrm_id
                vals["employee_id"] = employee.id
            elif vals.get("employee_id"):
                employee = self.env["hr.employee"].sudo().browse(vals["employee_id"])
                vals["employee_hrm_id"] = (employee.id_hrm or "").strip()
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
        vals = dict(vals)
        if "employee_hrm_id" in vals:
            employee_hrm_id = (vals.get("employee_hrm_id") or "").strip()
            employee = self._employee_from_hrm_id(employee_hrm_id)
            if not employee:
                raise ValidationError(
                    _("No employee was found with ID HRM %(id_hrm)s.")
                    % {"id_hrm": employee_hrm_id or "—"}
                )
            vals["employee_hrm_id"] = employee_hrm_id
            vals["employee_id"] = employee.id
        elif "employee_id" in vals and vals.get("employee_id"):
            employee = self.env["hr.employee"].sudo().browse(vals["employee_id"])
            vals["employee_hrm_id"] = (employee.id_hrm or "").strip()
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

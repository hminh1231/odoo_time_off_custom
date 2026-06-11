from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

_SKIP_FILE_EXPORT_RESEQUENCE = "skip_file_export_config_resequence"

EXPORT_FILE_TYPE_FIELDS = {
    "leave_ch": "export_leave_ch",
    "leave_vp": "export_leave_vp",
    "import_capnhatcong": "export_import_capnhatcong_ch",
    "import_capnhatcong_vp": "export_import_capnhatcong_vp",
}


def _sequence_as_int(seq):
    if seq is False or seq is None:
        return 0
    return int(seq)


class HrLeaveFileExportConfig(models.Model):
    _name = "hr.leave.file.export.config"
    _description = "Time Off File Export Configuration"
    _order = "sequence, id"

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
        index=True,
    )
    employee_name = fields.Char(
        string="Employee Name",
        related="employee_id.name",
        readonly=True,
        store=True,
    )
    export_leave_ch = fields.Boolean(string="Nghỉ phép CH", default=False)
    export_leave_vp = fields.Boolean(string="Nghỉ phép VP", default=False)
    export_import_capnhatcong_ch = fields.Boolean(
        string="Import công CH",
        default=False,
    )
    export_import_capnhatcong_vp = fields.Boolean(
        string="Import công VP",
        default=False,
    )

    _sql_constraints = [
        (
            "employee_unique",
            "unique(employee_id)",
            "Each employee can only appear once in the export configuration.",
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

    @api.model
    def get_export_file_types_for_employee(self, employee):
        if not employee:
            return set()
        line = self.sudo().search([("employee_id", "=", employee.id)], limit=1)
        if not line:
            return set()
        return {
            export_type
            for export_type, field_name in EXPORT_FILE_TYPE_FIELDS.items()
            if line[field_name]
        }

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

    @api.model
    def _resequence_all(self):
        lines = self.search([], order="sequence,id")
        for idx, rec in enumerate(lines, start=1):
            if _sequence_as_int(rec.sequence) != idx:
                rec.with_context(**{_SKIP_FILE_EXPORT_RESEQUENCE: True}).write(
                    {"sequence": idx}
                )

    @api.model_create_multi
    def create(self, vals_list):
        Config = self.env["hr.leave.file.export.config"]
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
            if not vals.get("sequence"):
                siblings = Config.search([])
                max_seq = max(
                    (_sequence_as_int(s) for s in siblings.mapped("sequence")),
                    default=0,
                )
                vals["sequence"] = max_seq + 1
        records = super().create(vals_list)
        records._resequence_all()
        return records

    def write(self, vals):
        if self.env.context.get(_SKIP_FILE_EXPORT_RESEQUENCE):
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
        res = super().write(vals)
        if "sequence" in vals:
            self._resequence_all()
        return res

    def unlink(self):
        res = super().unlink()
        self._resequence_all()
        return res

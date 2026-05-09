# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    managed_department_ids = fields.Many2many(
        "hr.department",
        string="Managed Departments",
        groups="hr.group_hr_user",
        compute="_compute_managed_department_ids",
        inverse="_inverse_managed_department_ids",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Phòng ban mà nhân viên này quản lý (đồng bộ với trường Manager trên Phòng ban).",
    )
    is_department_director = fields.Boolean(
        compute="_compute_is_department_director",
        groups="hr.group_hr_user",
    )

    def _compute_managed_department_ids(self):
        Department = self.env["hr.department"]
        for employee in self:
            if employee.id:
                employee.managed_department_ids = Department.search(
                    [("manager_id", "=", employee.id)]
                )
            else:
                employee.managed_department_ids = Department.browse()

    def _inverse_managed_department_ids(self):
        """Gán/bỏ Manager trên phòng ban theo lựa chọn (many2many không lưu bảng riêng)."""
        for employee in self:
            if not employee.id:
                continue
            previous = self.env["hr.department"].search(
                [("manager_id", "=", employee.id)]
            )
            selected = employee.managed_department_ids
            (previous - selected).sudo().write({"manager_id": False})
            (selected - previous).sudo().write({"manager_id": employee.id})

    @api.depends("job_title", "job_id.name")
    def _compute_is_department_director(self):
        for employee in self:
            job_title = (employee.job_title or employee.job_id.name or "").casefold()
            employee.is_department_director = any(
                keyword in job_title
                for keyword in ("director", "giam doc", "giám đốc")
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Cho phép set phòng ban khi tạo NV mới (sau khi có id mới gán manager)."""
        prepared = []
        deferred_commands = []
        for vals in vals_list:
            cmds = vals.pop("managed_department_ids", None)
            prepared.append(vals)
            deferred_commands.append(cmds)
        employees = super().create(prepared)
        for employee, cmds in zip(employees, deferred_commands):
            if cmds:
                employee.write({"managed_department_ids": cmds})
        return employees

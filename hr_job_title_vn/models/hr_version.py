# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

# Static list: Odoo passes the model as first arg to callable selection helpers; use a list, not a 0-arg function.
JOB_TITLE_SELECTION = [
    ("nhân viên", "Nhân viên"),
    ("trưởng nhóm", "Trưởng nhóm"),
    ("cửa hàng trưởng", "Cửa hàng trưởng"),
    ("asm", "ASM"),
    ("trưởng bộ phận", "Trưởng bộ phận"),
    ("trưởng phòng", "Trưởng phòng"),
    ("trưởng phòng hcns", "Trưởng phòng HCNS"),
    ("giám đốc", "Giám đốc"),
]


class HrVersion(models.Model):
    _inherit = "hr.version"

    job_title = fields.Selection(
        selection=JOB_TITLE_SELECTION,
        string="Job Title",
        tracking=True,
    )

    def write(self, vals):
        res = super().write(vals)
        if "job_title" in vals:
            for ver in self:
                if ver.employee_id:
                    ver.employee_id._check_manager_job_title_hierarchy()
        return res

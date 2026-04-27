from odoo import fields, models

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


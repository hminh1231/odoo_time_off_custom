from odoo import fields, models

JOB_TITLE_SELECTION = [
    ("nhân viên", "nhân viên"),
    ("trưởng nhóm", "trưởng nhóm"),
    ("trưởng BP", "trưởng BP"),
    ("kiểm soát", "kiểm soát"),
    ("trưởng phòng HCNS", "trưởng phòng HCNS"),
    ("giám đốc", "giám đốc"),
]


class HrVersion(models.Model):
    _inherit = "hr.version"

    job_title = fields.Selection(
        selection=JOB_TITLE_SELECTION,
        string="Job Title",
        tracking=True,
    )


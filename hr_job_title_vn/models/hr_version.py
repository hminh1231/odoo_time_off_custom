# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

# Static list: Odoo passes the model as first arg to callable selection helpers; use a list, not a 0-arg function.
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

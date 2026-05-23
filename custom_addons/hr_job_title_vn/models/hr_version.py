# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

# Static list: Odoo passes the model as first arg to callable selection helpers; use a list, not a 0-arg function.
JOB_TITLE_SELECTION = [
    ("nhân viên vp", "Nhân viên VP"),
    ("nhân viên ch", "Nhân viên CH"),
    ("giám sát", "Giám sát"),
    ("trưởng nhóm", "Trưởng nhóm"),
    ("nhóm trưởng", "Nhóm trưởng"),
    ("cửa hàng trưởng", "Cửa hàng trưởng"),
    ("asm", "ASM"),
    ("rsm", "RSM"),
    ("quản lý kho", "Quản lý kho"),
    ("admin", "Admin"),
    ("admin tổng", "Admin tổng"),
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

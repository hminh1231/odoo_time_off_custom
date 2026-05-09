# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrDepartment(models.Model):
    _inherit = "hr.department"

    managed_list_stt = fields.Integer(
        string="STT",
        compute="_compute_managed_list_stt",
        compute_sudo=True,
        groups="hr.group_hr_user",
    )

    @api.depends("manager_id", "complete_name", "name")
    def _compute_managed_list_stt(self):
        """STT trong từng nhóm cùng Manager; nếu không đọc được manager (ACL/cache),
        vẫn đánh 1..n theo thứ tự tên trong batch (đúng với bảng trên form nhân viên)."""
        def sort_key(dept):
            return ((dept.complete_name or dept.name or "").casefold(), dept.id or 0)

        with_manager = self.filtered("manager_id")
        without_manager = self - with_manager
        for _mgr, depts in with_manager.grouped("manager_id").items():
            for idx, dept in enumerate(depts.sorted(key=sort_key), start=1):
                dept.managed_list_stt = idx
        if without_manager:
            for idx, dept in enumerate(without_manager.sorted(key=sort_key), start=1):
                dept.managed_list_stt = idx

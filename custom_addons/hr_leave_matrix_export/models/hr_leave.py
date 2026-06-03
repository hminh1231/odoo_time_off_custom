# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    @api.model
    def get_matrix_export_menu_access(self):
        """Quyền hiển thị menu kết xuất theo miền của user đang đăng nhập."""
        return self.env["hr.leave.store.export.mixin"]._get_matrix_export_menu_access()

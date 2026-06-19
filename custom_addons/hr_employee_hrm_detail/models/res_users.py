# -*- coding: utf-8 -*-

from odoo import api, fields, models

VISIBILITY_POLICIES = [
    ("self", "Chỉ bản thân"),
    ("ma_bo_phan", "Cùng mã bộ phận"),
    ("assigned", "Chỉ định mã bộ phận"),
    ("department", "Cùng phòng ban"),
    ("region", "Cùng khu vực (Miền)"),
    ("all", "Toàn bộ"),
]


class ResUsers(models.Model):
    _inherit = "res.users"

    visibility_policy = fields.Selection(
        selection=VISIBILITY_POLICIES,
        string="Phạm vi xem nhân viên",
        default="self",
        help=(
            "Quy định user được nhìn thấy hồ sơ nhân viên nào. "
            "Quản trị viên (HR Administrator) luôn thấy toàn bộ."
        ),
    )
    assigned_ma_bo_phan_ids = fields.Many2many(
        "hr.store.code",
        "res_users_assigned_ma_bo_phan_rel",
        "user_id",
        "store_code_id",
        string="Mã bộ phận được xem",
        help="Chỉ dùng khi Phạm vi xem = 'Chỉ định mã bộ phận'. "
        "User sẽ thấy mọi nhân viên thuộc các mã bộ phận được chọn.",
    )

    employee_ma_bo_phan_id = fields.Many2one(
        "hr.store.code",
        string="Mã bộ phận (nhân viên)",
        compute="_compute_employee_ma_bo_phan_id",
        store=True,
        index=True,
    )
    employee_department_id = fields.Many2one(
        "hr.department",
        string="Phòng ban (nhân viên)",
        compute="_compute_employee_org",
        store=True,
        index=True,
    )
    employee_mien = fields.Char(
        string="Miền (nhân viên)",
        compute="_compute_employee_org",
        store=True,
        index=True,
    )

    @api.depends("employee_id", "employee_id.ma_bo_phan_id")
    def _compute_employee_ma_bo_phan_id(self):
        for user in self:
            emp = user.sudo().employee_id
            user.employee_ma_bo_phan_id = emp.ma_bo_phan_id if emp else False

    @api.depends(
        "employee_id",
        "employee_id.department_id",
        "employee_id.mien",
        "employee_id.ma_bo_phan_id.mien",
    )
    def _compute_employee_org(self):
        for user in self:
            emp = user.sudo().employee_id
            user.employee_department_id = emp.department_id if emp else False
            if emp:
                user.employee_mien = emp.mien or (
                    emp.ma_bo_phan_id.mien if emp.ma_bo_phan_id else False
                )
            else:
                user.employee_mien = False

    def write(self, vals):
        res = super().write(vals)
        if {"group_ids", "visibility_policy", "assigned_ma_bo_phan_ids"} & set(vals):
            self.env.registry.clear_cache()
        return res

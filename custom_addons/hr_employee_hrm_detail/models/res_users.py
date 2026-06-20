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

USER_ROLES = [
    ("employee", "Nhân viên (Employee)"),
    ("asm", "Quản lý cửa hàng (ASM)"),
    ("rm", "Quản lý vùng (RM)"),
    ("hr", "Nhân sự (HR)"),
    ("admin", "Quản trị (Admin)"),
]

# Role -> list of group XML ids granted. Groups from apps that are not installed
# are resolved with raise_if_not_found=False and silently skipped, so the same
# mapping keeps working when Chi phí/CRM/POS/Kế toán get installed later.
ROLE_GROUP_XMLIDS = {
    "employee": [
        "base.group_user",
    ],
    "asm": [
        "base.group_user",
        "hr.group_hr_user",
        "hr_holidays.group_hr_holidays_responsible",
        "hr_attendance.group_hr_attendance_officer",
        # Chi phí (khi cài hr_expense)
        "hr_expense.group_hr_expense_team_approver",
    ],
    "rm": [
        "base.group_user",
        "hr.group_hr_user",
        "hr_holidays.group_hr_holidays_responsible",
        "hr_attendance.group_hr_attendance_officer",
        "hr_expense.group_hr_expense_team_approver",
        # CRM (khi cài crm/sale)
        "sales_team.group_sale_salesman_all_leads",
    ],
    "hr": [
        "base.group_user",
        "hr.group_hr_user",
        "hr_holidays.group_hr_holidays_user",
        "hr_attendance.group_hr_attendance_user",
        # Kế toán (khi cài account)
        "account.group_account_user",
    ],
    "admin": [
        "base.group_user",
        "hr.group_hr_manager",
        "hr_holidays.group_hr_holidays_manager",
        "hr_attendance.group_hr_attendance_manager",
        "hr_expense.group_hr_expense_manager",
        "sales_team.group_sale_manager",
        "point_of_sale.group_pos_manager",
        "account.group_account_manager",
    ],
}

# Default Data Scope applied when a role is assigned (admin can still override).
ROLE_DEFAULT_SCOPE = {
    "employee": "self",
    "asm": "assigned",
    "rm": "region",
    "hr": "all",
    "admin": "all",
}

# App Access checkboxes -> the security group that represents "can use this app".
# Ticking grants the group, unticking removes it. Apps whose module is not
# installed resolve to no group (checkbox shown read-only as "chưa cài").
# Each entry: field_name -> (primary group xmlid, module technical name).
APP_ACCESS_DEFS = {
    "app_access_hr": ("hr.group_hr_user", "hr"),
    "app_access_leave": ("hr_holidays.group_hr_holidays_user", "hr_holidays"),
    "app_access_attendance": (
        "hr_attendance.group_hr_attendance_user",
        "hr_attendance",
    ),
    "app_access_expense": ("hr_expense.group_hr_expense_user", "hr_expense"),
    "app_access_crm": ("sales_team.group_sale_salesman", "crm"),
    "app_access_pos": ("point_of_sale.group_pos_user", "point_of_sale"),
    "app_access_accounting": ("account.group_account_user", "account"),
}


class ResUsers(models.Model):
    _inherit = "res.users"

    user_role = fields.Selection(
        selection=USER_ROLES,
        string="Vai trò",
        help=(
            "Gán nhanh bộ quyền theo vai trò nghiệp vụ. Khi chọn vai trò, hệ "
            "thống tự cấp quyền truy cập các app phù hợp và đặt phạm vi dữ liệu "
            "(Data Scope) mặc định. Có thể tinh chỉnh lại phạm vi bên dưới."
        ),
    )

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

    # --- App Access checkboxes (compute + inverse on security groups) ---
    app_access_hr = fields.Boolean(
        "Hồ sơ nhân viên",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )
    app_access_leave = fields.Boolean(
        "Nghỉ phép",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )
    app_access_attendance = fields.Boolean(
        "Chấm công",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )
    app_access_expense = fields.Boolean(
        "Chi phí",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )
    app_access_crm = fields.Boolean(
        "CRM",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )
    app_access_pos = fields.Boolean(
        "POS",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )
    app_access_accounting = fields.Boolean(
        "Kế toán",
        compute="_compute_app_access",
        inverse="_inverse_app_access",
    )

    # Availability flags (module installed?) to drive read-only in the form.
    app_avail_expense = fields.Boolean(compute="_compute_app_avail")
    app_avail_crm = fields.Boolean(compute="_compute_app_avail")
    app_avail_pos = fields.Boolean(compute="_compute_app_avail")
    app_avail_accounting = fields.Boolean(compute="_compute_app_avail")

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

    @api.depends("group_ids", "group_ids.all_implied_ids")
    def _compute_app_access(self):
        groups = {}
        for fname, (xmlid, _module) in APP_ACCESS_DEFS.items():
            groups[fname] = self.env.ref(xmlid, raise_if_not_found=False)
        for user in self:
            for fname, group in groups.items():
                user[fname] = bool(group) and user.has_group(
                    APP_ACCESS_DEFS[fname][0]
                )

    def _inverse_app_access(self):
        for user in self:
            commands = []
            for fname, (xmlid, _module) in APP_ACCESS_DEFS.items():
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if not group:
                    continue
                wanted = bool(user[fname])
                has = group in user.group_ids
                if wanted and not has:
                    commands.append((4, group.id))
                elif not wanted and has:
                    commands.append((3, group.id))
            if commands:
                super(ResUsers, user).write({"group_ids": commands})

    @api.depends_context("uid")
    def _compute_app_avail(self):
        installed = set(
            self.env["ir.module.module"]
            .sudo()
            .search([("state", "=", "installed")])
            .mapped("name")
        )
        for user in self:
            user.app_avail_expense = "hr_expense" in installed
            user.app_avail_crm = "crm" in installed
            user.app_avail_pos = "point_of_sale" in installed
            user.app_avail_accounting = "account" in installed

    @api.model
    def _role_group(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.model
    def _role_managed_group_ids(self):
        """Every group id that any role may grant (only those that exist)."""
        ids = set()
        for xmlids in ROLE_GROUP_XMLIDS.values():
            for xmlid in xmlids:
                group = self._role_group(xmlid)
                if group:
                    ids.add(group.id)
        return ids

    def _role_target_group_ids(self, role):
        """Group ids granted by the given role (existing groups only)."""
        ids = []
        for xmlid in ROLE_GROUP_XMLIDS.get(role, []):
            group = self._role_group(xmlid)
            if group:
                ids.append(group.id)
        return ids

    def _apply_user_role(self, set_scope=True):
        """Sync group membership (and default scope) from each user's role."""
        managed = self._role_managed_group_ids()
        for user in self:
            role = user.user_role
            if not role:
                continue
            target = set(user._role_target_group_ids(role))
            commands = [(3, gid) for gid in managed - target]
            commands += [(4, gid) for gid in target]
            if commands:
                super(ResUsers, user).write({"group_ids": commands})
            if set_scope:
                scope = ROLE_DEFAULT_SCOPE.get(role)
                if scope and user.visibility_policy != scope:
                    super(ResUsers, user).write({"visibility_policy": scope})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        role_users = users.filtered("user_role")
        if role_users:
            role_users._apply_user_role()
            self.env.registry.clear_cache()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "user_role" in vals and not self.env.context.get("skip_role_apply"):
            # Reapply scope only when role itself changed (preserve manual scope
            # overrides done in the same write).
            self._apply_user_role(set_scope="visibility_policy" not in vals)
        cache_keys = {
            "group_ids",
            "visibility_policy",
            "assigned_ma_bo_phan_ids",
            "user_role",
        } | set(APP_ACCESS_DEFS)
        if cache_keys & set(vals):
            self.env.registry.clear_cache()
        return res

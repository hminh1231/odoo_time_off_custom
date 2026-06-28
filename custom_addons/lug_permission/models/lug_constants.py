# -*- coding: utf-8 -*-

LUG_PERMISSION_FIELDS = [
    ("perm_view", "view"),
    ("perm_create", "create"),
    ("perm_edit", "edit"),
    ("perm_delete", "delete"),
    ("perm_approve", "approve"),
    ("perm_export", "export"),
    ("perm_import", "import"),
    ("perm_print", "print"),
]

LUG_DATA_SCOPES = [
    ("self", "SELF - Chỉ bản thân"),
    ("store", "STORE - Cửa hàng / mã bộ phận"),
    ("department", "DEPARTMENT - Cùng phòng ban"),
    ("region", "REGION - Khu vực (Miền)"),
    ("company", "COMPANY - Toàn công ty"),
]

# LUG data scope -> hr_employee_hrm_detail visibility_policy (base mapping).
LUG_SCOPE_TO_VISIBILITY = {
    "self": "self",
    "store": "ma_bo_phan",
    "department": "department",
    "region": "region",
    "company": "all",
}

# Reverse mapping for backfill / role quick-setup.
VISIBILITY_TO_LUG_SCOPE = {
    "self": "self",
    "ma_bo_phan": "store",
    "assigned": "store",
    "department": "department",
    "region": "region",
    "all": "company",
}

ROLE_TO_LUG_SCOPE = {
    "employee": "self",
    "asm": "store",
    "rm": "region",
    "hr": "company",
    "admin": "company",
}

# ir.rule domain_force for lug_permission.hr_leave_lug_scope_rule (synced in hooks).
def lug_leave_lug_scope_rule_domain():
    from odoo.addons.hr_employee_hrm_detail.models.hr_employee_mien_rule_domains import (
        leave_peer_read_rule_domain,
    )

    peer = leave_peer_read_rule_domain()
    return (
        "[(1, '=', 1)] if user.has_group('base.group_system') "
        "or user.has_group('hr.group_hr_manager') "
        "or not (user.lug_group_ids or user.lug_user_permission_ids) "
        f"else {peer}"
    )

# Discuss submenus hidden for all employees; visible only for Administrator or
# LUG users with Discuss Edit (or stronger) — not View/Create alone.
LUG_DISCUSS_EMPLOYEE_HIDDEN_MENU_XMLIDS = [
    "mail.menu_channel",
    "mail.menu_configuration",
]
LUG_DISCUSS_ADMIN_MENU_PERMISSIONS = frozenset(
    {"edit", "delete", "approve", "export", "import", "print"}
)

# HR submenus hidden when the user only has View on the HR app.
LUG_HR_VIEW_ONLY_HIDDEN_MENU_XMLIDS = [
    "hr_skills.hr_skill_learning_menu",
    "hr.hr_menu_hr_reports",
    "hr.menu_hr_department_kanban",
    "hr.menu_human_resources_configuration",
    "hr.menu_config_employee",
    "hr.menu_hr_main",
    "hr.menu_hr_employee",
]

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
    ("region", "REGION - Khu vực (Miền)"),
    ("company", "COMPANY - Toàn công ty"),
]

# LUG data scope -> hr_employee_hrm_detail visibility_policy (base mapping).
LUG_SCOPE_TO_VISIBILITY = {
    "self": "self",
    "store": "ma_bo_phan",
    "region": "region",
    "company": "all",
}

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

# -*- coding: utf-8 -*-
"""domain_force strings for ir.rule (safe_eval).

Employee visibility is enforced in Python (hr.employee._search via the access
mixin), so the hr.employee / hr.employee.public / hr.version record rules stay
permissive here. Only the hr.leave peer-read rule needs an explicit domain so
that leave requests follow the same visibility_policy as employee profiles.
"""


def employee_access_rule_domain(*args, **kwargs):
    """Permissive: Python layer (access mixin) enforces visibility."""
    return "[(1, '=', 1)]"


# hr.leave peer-read: always show own + records I approve (leave_manager_id),
# then widen by the user's visibility_policy.
_LEAVE_SELF = (
    "('employee_id.user_id', '=', user.id), "
    "('employee_id', '=', user.employee_id.id), "
    "('employee_id.leave_manager_id', '=', user.id)"
)


def _leave_branch(extra_leaf):
    # OR of: extra_leaf, own, my-employee, records-I-manage  (4 leaves -> 3 '|')
    return f"['|', '|', '|', {extra_leaf}, {_LEAVE_SELF}]"


def leave_peer_read_rule_domain():
    ma_bo_phan = _leave_branch(
        "('employee_id.ma_bo_phan_id', '=', user.employee_ma_bo_phan_id.id)"
    )
    assigned = _leave_branch(
        "('employee_id.ma_bo_phan_id', 'in', user.assigned_ma_bo_phan_ids.ids)"
    )
    department = _leave_branch(
        "('employee_id.department_id', '=', user.employee_department_id.id)"
    )
    region = _leave_branch("('employee_id.mien', '=', user.employee_mien)")
    self_only = f"['|', '|', {_LEAVE_SELF}]"
    return (
        "[(1, '=', 1)] if user.has_group('hr.group_hr_manager') "
        "or (user.visibility_policy or 'self') == 'all' "
        "else "
        f"({ma_bo_phan}) if user.visibility_policy == 'ma_bo_phan' "
        "and user.employee_ma_bo_phan_id "
        "else "
        f"({assigned}) if user.visibility_policy == 'assigned' "
        "else "
        f"({department}) if user.visibility_policy == 'department' "
        "else "
        f"({region}) if user.visibility_policy == 'region' "
        "else "
        f"({self_only})"
    )


HR_LEAVE_PEER_READ_DOMAIN = leave_peer_read_rule_domain()

HR_EMPLOYEE_MIEN_RULE_DOMAIN = employee_access_rule_domain()
HR_EMPLOYEE_PUBLIC_MIEN_RULE_DOMAIN = employee_access_rule_domain()
HR_VERSION_MIEN_RULE_DOMAIN = employee_access_rule_domain()

# -*- coding: utf-8 -*-
"""Extend hr_employee_self_only privacy checks for LUG zone-based HR editors."""

import odoo.addons.hr_employee_self_only.models.hr_employee_privacy as _privacy

_orig_can_edit = _privacy._privacy_can_edit_employee_profile


def _lug_privacy_can_edit_employee_profile(env):
    if _orig_can_edit(env):
        return True
    user = env.user
    if env.su or not user.has_group("hr.group_hr_user"):
        return False
    sudo_user = user.sudo()
    if (sudo_user.lug_hr_employee_edit_policy or "none") != "zones":
        return False
    if not sudo_user.lug_hr_employee_edit_mien_zone_ids:
        return False
    return "edit" in user._lug_effective_permission_map().get("hr", set())


def _lug_privacy_is_employee_edit_forbidden(env):
    if not env.user.has_group("hr.group_hr_user"):
        return False
    return not _lug_privacy_can_edit_employee_profile(env)


_privacy._privacy_can_edit_employee_profile = _lug_privacy_can_edit_employee_profile
_privacy._privacy_is_employee_edit_forbidden = _lug_privacy_is_employee_edit_forbidden

# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.exceptions import AccessError


def _privacy_is_employees_no_user(env):
    user = env.user
    if user.has_group("hr.group_hr_manager"):
        return False
    return user.has_group("hr_employee_self_only.group_hr_employees_no")


def _privacy_raise_if_employee_no_write(env, employees):
    """Employees=No: no create/write/unlink/mail on hr.employee (including own profile)."""
    if not _privacy_is_employees_no_user(env):
        return
    if employees:
        raise AccessError(_("Bạn chỉ có quyền xem thông tin nhân viên."))


def _privacy_raise_if_hr_version_no_write(env):
    """Employees=No: cannot change employee versions or contract templates (hr.version)."""
    if _privacy_is_employees_no_user(env):
        raise AccessError(_("Bạn chỉ có quyền xem hồ sơ nhân viên."))


def _privacy_raise_if_hr_employee_resource_no_write(env, resources):
    """Employees=No: cannot change resources linked to an employee (e.g. name/calendar)."""
    if not _privacy_is_employees_no_user(env):
        return
    if resources.filtered(lambda r: r.employee_id):
        raise AccessError(_("Bạn chỉ có quyền xem thông tin nhân viên."))


def _privacy_raise_if_employee_create_forbidden(env):
    if not _privacy_is_employees_no_user(env):
        return
    raise AccessError(_("Bạn không có quyền tạo nhân viên."))

"""Refresh stored HRM leave counters for office employees."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    employees = env["hr.employee"].search(
        [
            "|",
            ("mien", "=", "VP"),
            ("mien_zone_id.legacy_mien", "=", "VP"),
        ]
    )
    if not employees or not hasattr(employees, "_compute_time_off_summary"):
        return
    employees.with_context(
        employees_no_timeoff_write=True,
        employees_no_allowed_employee_ids=employees.ids,
    )._compute_time_off_summary()

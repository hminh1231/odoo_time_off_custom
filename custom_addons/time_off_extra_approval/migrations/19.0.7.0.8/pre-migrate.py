from odoo.tools import sql


def migrate(cr, version):
    if not sql.column_exists(cr, "hr_leave_type_special_employee_line", "org_chart_stop_position"):
        cr.execute(
            "ALTER TABLE hr_leave_type_special_employee_line "
            "ADD COLUMN org_chart_stop_position VARCHAR"
        )

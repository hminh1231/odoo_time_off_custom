from odoo.tools import sql


def migrate(cr, version):
    if not sql.table_exists(cr, "hr_employee"):
        return
    renames = (
        ("thai_san_ngay_cap_phep", "unpaid_leave_start_date"),
        ("thai_san_di_lam_lai", "unpaid_leave_return_date"),
    )
    for old_name, new_name in renames:
        if sql.column_exists(cr, "hr_employee", old_name) and not sql.column_exists(
            cr, "hr_employee", new_name
        ):
            cr.execute(
                'ALTER TABLE hr_employee RENAME COLUMN "%s" TO "%s"'
                % (old_name, new_name)
            )

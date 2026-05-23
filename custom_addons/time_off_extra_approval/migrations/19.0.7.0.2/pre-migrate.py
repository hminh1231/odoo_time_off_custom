from odoo.tools import sql


def migrate(cr, version):
    if not sql.column_exists(cr, "hr_leave", "p2_leave_id"):
        cr.execute("ALTER TABLE hr_leave ADD COLUMN p2_leave_id INTEGER")
    if not sql.column_exists(cr, "hr_leave", "p1_leave_id"):
        cr.execute("ALTER TABLE hr_leave ADD COLUMN p1_leave_id INTEGER")

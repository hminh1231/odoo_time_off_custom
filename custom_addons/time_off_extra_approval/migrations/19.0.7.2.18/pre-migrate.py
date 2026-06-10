import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    table = "hr_leave_type_special_employee_line"
    if not sql.table_exists(cr, table):
        return
    if not sql.column_exists(cr, table, "employee_hrm_id"):
        cr.execute(
            """
            ALTER TABLE hr_leave_type_special_employee_line
            ADD COLUMN employee_hrm_id VARCHAR
            """
        )
    cr.execute(
        """
        UPDATE hr_leave_type_special_employee_line AS line
           SET employee_hrm_id = NULLIF(BTRIM(employee.id_hrm), '')
          FROM hr_employee AS employee
         WHERE employee.id = line.employee_id
           AND (
               line.employee_hrm_id IS NULL
               OR BTRIM(line.employee_hrm_id) = ''
           )
        """
    )
    cr.execute(
        """
        SELECT COUNT(*)
          FROM hr_leave_type_special_employee_line
         WHERE employee_hrm_id IS NULL OR BTRIM(employee_hrm_id) = ''
        """
    )
    missing_count = cr.fetchone()[0]
    if missing_count:
        _logger.warning(
            "time_off_extra_approval: %s special employee row(s) have no ID HRM; "
            "configure ID HRM on the linked employees before editing those rows",
            missing_count,
        )

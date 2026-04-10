# -*- coding: utf-8 -*-
"""Ensure DB columns exist if the module code was deployed without a full ORM sync."""


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = %s
        """,
        (table,),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _column_exists(cr, "hr_leave_type", "employee_responsible_source"):
        cr.execute(
            """
            ALTER TABLE hr_leave_type
            ADD COLUMN employee_responsible_source VARCHAR
            """
        )
        cr.execute(
            """
            UPDATE hr_leave_type SET employee_responsible_source = 'manual'
            WHERE employee_responsible_source IS NULL
            """
        )
    if not _column_exists(cr, "hr_leave_type", "employee_responsible_escalation_hours"):
        cr.execute(
            """
            ALTER TABLE hr_leave_type
            ADD COLUMN employee_responsible_escalation_hours DOUBLE PRECISION DEFAULT 2.0
            """
        )
    if _table_exists(cr, "hr_leave_responsible_approval") and not _column_exists(
        cr, "hr_leave_responsible_approval", "pending_since"
    ):
        cr.execute(
            """
            ALTER TABLE hr_leave_responsible_approval
            ADD COLUMN pending_since TIMESTAMP WITHOUT TIME ZONE
            """
        )

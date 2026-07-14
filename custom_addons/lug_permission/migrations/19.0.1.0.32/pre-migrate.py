# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE res_users
        ADD COLUMN IF NOT EXISTS lug_leave_full_activity_report boolean
        """
    )
    cr.execute(
        """
        UPDATE res_users
           SET lug_leave_full_activity_report = false
         WHERE lug_leave_full_activity_report IS NULL
        """
    )

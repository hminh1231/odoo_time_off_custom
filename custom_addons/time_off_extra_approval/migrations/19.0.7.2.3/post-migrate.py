# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_leave_odoobot_notify_rule r
        SET display_name = COALESCE(r.display_name, r.mien || ' · ' || COALESCE(r.job_title, ''))
        WHERE r.display_name IS NULL
        """
    )

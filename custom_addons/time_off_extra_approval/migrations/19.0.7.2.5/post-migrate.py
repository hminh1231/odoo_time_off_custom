# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        UPDATE hr_leave_odoobot_notify_rule
        SET active = TRUE
        WHERE active IS NOT TRUE
        """
    )

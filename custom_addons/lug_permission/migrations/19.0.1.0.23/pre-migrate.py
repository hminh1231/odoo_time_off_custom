# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_ui_view
        WHERE model = 'res.users'
          AND (
            arch_db::text LIKE '%%name="employee_visibility"%%'
            OR name = 'res.users.form.remove.legacy.visibility'
          )
        """
    )

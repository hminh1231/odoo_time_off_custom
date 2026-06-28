# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id
            FROM ir_model_data
            WHERE module = 'hr_employee_hrm_detail'
              AND name = 'view_users_form_visibility'
        )
        """
    )

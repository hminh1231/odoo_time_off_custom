def migrate(cr, version):
    # Reset the inherit_id of view_hr_leave_form_multi_step to point at
    # hr_holidays.hr_leave_view_form. A previous broken upgrade may have left it
    # pointing at a wrong parent, which causes view-validation to fail when the
    # arch (which uses xpath against the base form) is re-written during upgrade.
    cr.execute("""
        UPDATE ir_ui_view
           SET inherit_id = (
               SELECT res_id FROM ir_model_data
                WHERE module = 'hr_holidays' AND name = 'hr_leave_view_form'
           )
         WHERE id IN (
               SELECT res_id FROM ir_model_data
                WHERE name = 'view_hr_leave_form_multi_step'
           )
           AND inherit_id IS DISTINCT FROM (
               SELECT res_id FROM ir_model_data
                WHERE module = 'hr_holidays' AND name = 'hr_leave_view_form'
           )
    """)

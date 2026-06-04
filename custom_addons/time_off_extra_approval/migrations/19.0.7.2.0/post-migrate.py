# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'time_off_extra_approval'
          AND name IN (
            'action_hr_leave_odoobot_notify_config',
            'model_hr_leave_odoobot_notify_config',
            'view_hr_leave_odoobot_notify_config_form'
          )
        """
    )

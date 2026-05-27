# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM ir_model_fields
        WHERE model = 'hr.leave'
          AND name IN (
              'holiday_status_id_mien_o_locked',
              'holiday_status_id_tenure_o_locked'
          )
        """
    )

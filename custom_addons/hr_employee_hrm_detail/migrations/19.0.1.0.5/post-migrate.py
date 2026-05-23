def migrate(cr, version):
    cr.execute("""
        UPDATE ir_model_fields
        SET relation = 'hr.store.code'
        WHERE model = 'hr.employee'
          AND name = 'ma_bo_phan_id'
          AND relation = 'hr.store'
    """)

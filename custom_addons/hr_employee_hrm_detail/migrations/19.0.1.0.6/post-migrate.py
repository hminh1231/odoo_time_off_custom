def migrate(cr, version):
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'hr_employee' AND column_name = 'ma_bo_phan_id'
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE hr_employee e
            SET ma_bo_phan = s.code
            FROM hr_store s
            WHERE e.ma_bo_phan_id = s.id
              AND s.code IS NOT NULL
              AND TRIM(s.code) != ''
              AND (e.ma_bo_phan IS NULL OR TRIM(e.ma_bo_phan) = '')
        """)
        cr.execute("ALTER TABLE hr_employee DROP COLUMN IF EXISTS ma_bo_phan_id")

    cr.execute("DROP VIEW IF EXISTS hr_store_code CASCADE")

    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'hr.employee' AND name = 'ma_bo_phan_id'
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model = 'ir.model.fields'
          AND name LIKE 'field_hr_employee__ma_bo_phan_id%'
    """)
    cr.execute("""
        DELETE FROM ir_model WHERE model = 'hr.store.code'
    """)

def migrate(cr, version):
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'hr_employee' AND column_name = 'ma_bo_phan_id'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE hr_employee
            ADD COLUMN ma_bo_phan_id INTEGER
        """)

    cr.execute("""
        CREATE OR REPLACE VIEW hr_store_code AS
        SELECT
            id,
            id AS store_id,
            code,
            name,
            mien,
            active
        FROM hr_store
        WHERE code IS NOT NULL
          AND TRIM(code) != ''
    """)

    cr.execute("""
        UPDATE hr_employee e
        SET ma_bo_phan_id = s.id
        FROM hr_store s
        WHERE e.ma_bo_phan IS NOT NULL
          AND TRIM(e.ma_bo_phan) != ''
          AND TRIM(s.code) = TRIM(e.ma_bo_phan)
          AND e.ma_bo_phan_id IS NULL
    """)

    cr.execute("""
        UPDATE ir_model_fields
        SET relation = 'hr.store.code', ttype = 'many2one'
        WHERE model = 'hr.employee' AND name = 'ma_bo_phan_id'
    """)

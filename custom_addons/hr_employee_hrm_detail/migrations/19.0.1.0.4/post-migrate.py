def migrate(cr, version):
    cr.execute("""
        UPDATE hr_employee e
        SET ma_bo_phan_id = s.id
        FROM hr_store s
        WHERE e.ma_bo_phan IS NOT NULL
          AND TRIM(e.ma_bo_phan) != ''
          AND TRIM(s.code) = TRIM(e.ma_bo_phan)
          AND e.ma_bo_phan_id IS NULL
    """)

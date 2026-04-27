# Part of Odoo. See LICENSE file for full copyright and licensing details.


def pre_init_hook(env):
    """Clear job_title values that are not valid selection keys before the field type changes."""
    env.cr.execute(
        """
        UPDATE hr_version
        SET job_title = CASE
            WHEN job_title = 'trưởng BP' THEN 'trưởng bộ phận'
            WHEN job_title = 'trưởng phòng HCNS' THEN 'trưởng phòng hcns'
            ELSE NULL
        END
        WHERE job_title IS NOT NULL
          AND job_title NOT IN (
              'nhân viên',
              'trưởng nhóm',
              'cửa hàng trưởng',
              'asm',
              'trưởng bộ phận',
              'trưởng phòng',
              'trưởng phòng hcns',
              'giám đốc'
          )
        """
    )

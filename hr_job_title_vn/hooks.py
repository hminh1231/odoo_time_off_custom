# Part of Odoo. See LICENSE file for full copyright and licensing details.


def pre_init_hook(env):
    """Clear job_title values that are not valid selection keys before the field type changes."""
    env.cr.execute(
        """
        UPDATE hr_version
        SET job_title = NULL
        WHERE job_title IS NOT NULL
          AND job_title NOT IN (
              'nhân viên',
              'trưởng nhóm',
              'trưởng BP',
              'kiểm soát',
              'trưởng phòng HCNS',
              'giám đốc'
          )
        """
    )

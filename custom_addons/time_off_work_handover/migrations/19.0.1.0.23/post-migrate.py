from odoo import SUPERUSER_ID, api

from odoo.addons.time_off_work_handover.hooks import cleanup_duplicate_hr_leave_views


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    removed = cleanup_duplicate_hr_leave_views(env)
    if removed:
        env.registry.clear_cache()

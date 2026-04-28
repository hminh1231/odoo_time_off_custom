#!/usr/bin/env sh
set -eu

DB_NAME="${DB_NAME:-odoo_db}"
MODULES="${MODULES:-hr_employee_multi_responsible,time_off_extra_approval,hr_job_title_vn,hr_employee_cccd_scan,hr_employee_self_only,business_discuss_bots}"

echo "Updating modules on database: ${DB_NAME}"
docker compose -f deploy/docker-compose.yml exec -T odoo \
  odoo -c /etc/odoo/odoo.conf -d "${DB_NAME}" -u "${MODULES}" --stop-after-init

echo "Post-deploy update done."

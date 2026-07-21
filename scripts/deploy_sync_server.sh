#!/usr/bin/env sh
# Chay TREN SERVER sau khi may Windows da copy code local len odoo/addons.
set -eu

ODOO_CONTAINER="${ODOO_CONTAINER:-odoo-odoo19-1}"
DB_NAME="${DB_NAME:-master}"
ADDONS_PATH="${ADDONS_PATH:-/home/lug_odoo/odoo/addons}"

MODULE_ORDER="
hr_employee_multi_responsible
hr_job_title_vn
business_discuss_bots
hr_employee_hrm_detail
hr_employee_managed_departments
hr_employee_self_only
hr_employee_cccd_scan
hr_employee_gate_ticket
hr_employee_checklist
hr_store
time_off_extra_approval
time_off_responsible_approval
hr_leave_type_mien
hr_leave_mien_tenure_unpaid
time_off_work_handover
hr_leave_dashboard_department
hr_leave_delete_cancel
hr_leave_matrix_export
hr_leave_mobile_header
hr_leave_vp_sunday
timeoff_calendar_toggle
mail_discuss_lark_ui
mail_discuss_mobile_links
user_menu_reset_password
vn_language_switch
vn_translations_custom
lug_permission
lug_app_center
"

get_manifest_version() {
    python3 - "$1" <<'PY'
import ast
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    data = ast.literal_eval(f.read())
print(data.get("version", ""))
PY
}

MODULES_TO_UPDATE=""
for module in ${MODULE_ORDER}; do
    manifest="${ADDONS_PATH}/${module}/__manifest__.py"
    if [ ! -f "${manifest}" ]; then
        continue
    fi
    manifest_ver="$(get_manifest_version "${manifest}")"
    db_ver="$(docker exec odoo-db-1 psql -U odoo -d "${DB_NAME}" -t -A -c \
        "SELECT COALESCE(latest_version, '') FROM ir_module_module WHERE name='${module}' AND state='installed'")"
    db_ver="$(echo "${db_ver}" | tr -d '\r')"
    if [ -n "${manifest_ver}" ] && [ "${manifest_ver}" != "${db_ver}" ]; then
        echo "Can cap nhat: ${module} (${db_ver:-chua cai} -> ${manifest_ver})"
        MODULES_TO_UPDATE="${MODULES_TO_UPDATE} ${module}"
    fi
done

for module_path in "${ADDONS_PATH}"/*; do
    [ -d "${module_path}" ] || continue
    module="$(basename "${module_path}")"
    echo "${MODULES_TO_UPDATE}" | grep -qw "${module}" && continue
    manifest="${module_path}/__manifest__.py"
    [ -f "${manifest}" ] || continue
    manifest_ver="$(get_manifest_version "${manifest}")"
    db_ver="$(docker exec odoo-db-1 psql -U odoo -d "${DB_NAME}" -t -A -c \
        "SELECT COALESCE(latest_version, '') FROM ir_module_module WHERE name='${module}' AND state='installed'")"
    db_ver="$(echo "${db_ver}" | tr -d '\r')"
    if [ -n "${manifest_ver}" ] && [ -n "${db_ver}" ] && [ "${manifest_ver}" != "${db_ver}" ]; then
        echo "Can cap nhat: ${module} (${db_ver} -> ${manifest_ver})"
        MODULES_TO_UPDATE="${MODULES_TO_UPDATE} ${module}"
    fi
done

if [ -z "${MODULES_TO_UPDATE}" ]; then
    echo "Khong co module nao can cap nhat (version tren server da khop voi code local)."
else
    echo ""
    echo "========================================"
    echo "  Cap nhat module"
    echo "========================================"
    for module in ${MODULES_TO_UPDATE}; do
        echo "--- Cap nhat: ${module} ---"
        docker exec -u odoo "${ODOO_CONTAINER}" odoo \
            -c /etc/odoo/odoo.conf \
            -d "${DB_NAME}" \
            -u "${module}" \
            --i18n-overwrite \
            --stop-after-init \
            --no-http
    done
fi

echo ""
echo "========================================"
echo "  Restart Odoo"
echo "========================================"
docker restart "${ODOO_CONTAINER}"

echo ""
echo "Deploy tu may tinh len server hoan tat."

#!/usr/bin/env sh
# Chay TREN SERVER cong ty.
set -eu

ODOO_CONTAINER="${ODOO_CONTAINER:-odoo-odoo19-1}"
DB_NAME="${DB_NAME:-master}"
GIT_REPO_PATH="${GIT_REPO_PATH:-/home/lug_odoo/odoo_time_off_custom}"
ADDONS_PATH="${ADDONS_PATH:-/home/lug_odoo/odoo/addons}"
GIT_BRANCH="${GIT_BRANCH:-main}"
UPDATE_ALL="${UPDATE_ALL:-0}"

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
"

echo "========================================"
echo "  BUOC 1: git pull + phat hien module thay doi"
echo "========================================"
cd "${GIT_REPO_PATH}"
OLD="$(git rev-parse HEAD)"
git pull origin "${GIT_BRANCH}"

CHANGED="$(git diff --name-only "${OLD}" HEAD -- custom_addons/ \
  | awk -F/ 'NF>=2 {print $2}' \
  | sort -u)"

echo ""
echo "========================================"
echo "  BUOC 2: Dong bo code sang odoo/addons"
echo "========================================"
rsync -a "${GIT_REPO_PATH}/custom_addons/" "${ADDONS_PATH}/"

MODULES_TO_UPDATE=""
if [ "${UPDATE_ALL}" = "1" ]; then
    MODULES_TO_UPDATE="${MODULE_ORDER}"
else
    if [ -z "${CHANGED}" ]; then
        echo "Khong co module nao thay doi. Bo qua cap nhat module."
    else
        echo "Module thay doi:"
        echo "${CHANGED}" | sed 's/^/  - /'
        for module in ${MODULE_ORDER}; do
            if echo "${CHANGED}" | grep -qx "${module}"; then
                MODULES_TO_UPDATE="${MODULES_TO_UPDATE} ${module}"
            fi
        done
        for module in ${CHANGED}; do
            if ! echo "${MODULES_TO_UPDATE}" | grep -qw "${module}"; then
                MODULES_TO_UPDATE="${MODULES_TO_UPDATE} ${module}"
            fi
        done
    fi
fi

if [ -n "${MODULES_TO_UPDATE}" ]; then
    echo ""
    echo "========================================"
    echo "  BUOC 3: Cap nhat tung module"
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
echo "  BUOC 4: Restart Odoo"
echo "========================================"
docker restart "${ODOO_CONTAINER}"

echo ""
echo "Deploy server hoan tat."

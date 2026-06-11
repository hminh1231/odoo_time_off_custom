param(
    [string]$ServerHost = "172.13.0.31",
    [string]$ServerUser = "lug_odoo",
    [string]$GitBranch = "main",
    [string]$DbName = "master",
    [string]$OdooContainer = "odoo-odoo19-1",
    [string]$GitRepoPath = "/home/lug_odoo/odoo_time_off_custom",
    [string]$AddonsPath = "/home/lug_odoo/odoo/addons",
    [switch]$UpdateAll
)

$ErrorActionPreference = "Stop"

# Thu tu cap nhat theo phu thuoc module (module sau can module truoc).
$ModuleOrder = @(
    "hr_employee_multi_responsible",
    "hr_job_title_vn",
    "business_discuss_bots",
    "hr_employee_hrm_detail",
    "hr_employee_managed_departments",
    "hr_employee_self_only",
    "hr_employee_cccd_scan",
    "hr_employee_gate_ticket",
    "hr_employee_checklist",
    "hr_store",
    "time_off_extra_approval",
    "time_off_responsible_approval",
    "hr_leave_type_mien",
    "hr_leave_mien_tenure_unpaid",
    "time_off_work_handover",
    "hr_leave_dashboard_department",
    "hr_leave_delete_cancel",
    "hr_leave_matrix_export",
    "hr_leave_mobile_header",
    "hr_leave_vp_sunday",
    "timeoff_calendar_toggle",
    "mail_discuss_lark_ui",
    "mail_discuss_mobile_links",
    "user_menu_reset_password",
    "vn_language_switch",
    "vn_translations_custom"
)

$SshTarget = "${ServerUser}@${ServerHost}"
$SshKey = Join-Path $env:USERPROFILE ".ssh\id_ed25519"
$SshArgs = @(
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=20",
    "-o", "StrictHostKeyChecking=accept-new"
)

if (Test-Path $SshKey) {
    $SshArgs += @("-i", $SshKey)
}

function Invoke-Remote {
    param([string]$Command)
    $output = & ssh @SshArgs $SshTarget $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        if ($output) { $output | ForEach-Object { Write-Host $_ } }
        throw "Lenh that bai (exit $LASTEXITCODE): $Command"
    }
    return $output
}

function Sort-ModulesByOrder {
    param([string[]]$Names)
    $ordered = [System.Collections.Generic.List[string]]::new()
    foreach ($name in $ModuleOrder) {
        if ($Names -contains $name) { $ordered.Add($name) }
    }
    foreach ($name in ($Names | Sort-Object)) {
        if (-not $ordered.Contains($name)) { $ordered.Add($name) }
    }
    return $ordered.ToArray()
}

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  $Message"
    Write-Host "========================================"
}

Write-Host ""
Write-Host "Deploy Odoo len server cong ty"
Write-Host "Server: $SshTarget"
Write-Host "Database: $DbName"
Write-Host ""
Write-Host "Luu y:"
Write-Host "  - Moi nguoi push len GitHub (nhanh main), roi chay file .bat nay."
Write-Host "  - Script tu dong lay TAT CA code moi tren main (ca code dong nghiep)."
Write-Host "  - Chi cap nhat (-u) nhung module co file thay doi trong lan pull nay."
Write-Host ""

Write-Step "BUOC 0: Kiem tra SSH"
Invoke-Remote "echo connected && hostname" | Out-Null

Write-Step "BUOC 1: git pull + phat hien module thay doi"
$detectScript = @"
set -eu
cd $GitRepoPath
OLD=`$(git rev-parse HEAD)
git pull origin $GitBranch
git diff --name-only "`$OLD" HEAD -- custom_addons/ \
  | awk -F/ 'NF>=2 {print `$2}' \
  | sort -u
"@

$changedRaw = Invoke-Remote $detectScript
$changedModules = @(
    $changedRaw |
        Where-Object { $_ -and $_ -notmatch '^\s*$' } |
        ForEach-Object { $_.Trim() } |
        Select-Object -Unique
)

if ($UpdateAll) {
    $modulesToUpdate = $ModuleOrder
    Write-Host "Che do -UpdateAll: cap nhat tat ca module trong danh sach."
}
elseif ($changedModules.Count -eq 0) {
    Write-Host "Khong co module nao thay doi trong lan pull nay."
    Write-Host "Chi dong bo file (rsync), bo qua buoc cap nhat module."
    $modulesToUpdate = @()
}
else {
    $modulesToUpdate = Sort-ModulesByOrder -Names $changedModules
    Write-Host "Module thay doi (tu GitHub):"
    $modulesToUpdate | ForEach-Object { Write-Host "  - $_" }
}

Write-Step "BUOC 2: Dong bo code sang thu muc Odoo dang chay"
Invoke-Remote "rsync -a $GitRepoPath/custom_addons/ $AddonsPath/" | Out-Null

if ($modulesToUpdate.Count -gt 0) {
    foreach ($module in $modulesToUpdate) {
        Write-Step "Cap nhat module: $module"
        Invoke-Remote "docker exec -u odoo $OdooContainer odoo -c /etc/odoo/odoo.conf -d $DbName -u $module --i18n-overwrite --stop-after-init --no-http" | Out-Null
    }

    Write-Step "Restart Odoo"
    Invoke-Remote "docker restart $OdooContainer" | Out-Null

    Write-Step "Kiem tra version module vua cap nhat"
    $moduleList = ($modulesToUpdate | ForEach-Object { "'$_'" }) -join ","
    Invoke-Remote "docker exec odoo-db-1 psql -U odoo -d $DbName -t -A -c `"SELECT name || '|' || latest_version || '|' || state FROM ir_module_module WHERE name IN ($moduleList) ORDER BY name`""
}
else {
    Write-Step "Restart Odoo (khong cap nhat module)"
    Invoke-Remote "docker restart $OdooContainer" | Out-Null
}

Write-Host ""
Write-Host "========================================"
Write-Host "  XONG! Deploy server cong ty thanh cong."
Write-Host "  Mo Odoo va nhan Ctrl+F5 tren trinh duyet."
Write-Host "========================================"
Write-Host ""

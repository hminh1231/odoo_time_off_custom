param(
    [string]$DbName = "odoo_db",
    [string]$Modules = "hr_employee_multi_responsible,time_off_extra_approval,hr_job_title_vn,hr_employee_cccd_scan,hr_employee_self_only,business_discuss_bots"
)

Write-Host "Updating modules on database: $DbName"
docker compose -f deploy/docker-compose.yml exec -T odoo `
  odoo -c /etc/odoo/odoo.conf -d $DbName -u $Modules --stop-after-init

if ($LASTEXITCODE -ne 0) {
    throw "post_deploy failed with exit code $LASTEXITCODE"
}

Write-Host "Post-deploy update done."

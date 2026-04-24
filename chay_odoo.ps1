# Chay Odoo dung ma nguon tai C:\Users\Admin\odoo (giong huong dan ban dau).
# Double-click hoac: powershell -ExecutionPolicy Bypass -File .\chay_odoo.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Khong tim thay venv: $py — cai dat lai venv hoac dung: python odoo-bin -c odoo.conf"
}

$conf = Join-Path $PSScriptRoot "odoo.conf"
if (-not (Test-Path $conf)) {
    Write-Error "Khong tim thay odoo.conf"
}

Write-Host "Dang khoi dong Odoo (can Postgres dang chay, db trong odoo.conf)..."
Write-Host "Mo trinh duyet: http://localhost:8069"
Write-Host ""

& $py "odoo-bin" "-c" "odoo.conf"

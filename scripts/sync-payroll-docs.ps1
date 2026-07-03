# Re-download Gusto Embedded Payroll + Check HQ markdown docs into docs/payroll/
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Missing .venv Python at $python"
}

$script = @'
import urllib.request
from pathlib import Path

ROOT = Path("docs/payroll")

GUSTO = [
    ("llms-index.txt", "https://docs.gusto.com/llms.txt"),
    ("gusto-configure-employee-tax-information.md", "https://docs.gusto.com/embedded-payroll/docs/configure-employee-tax-information.md"),
    ("gusto-complete-a-regular-payroll.md", "https://docs.gusto.com/embedded-payroll/docs/complete-a-regular-payroll.md"),
    ("gusto-manage-w-2-employees.md", "https://docs.gusto.com/embedded-payroll/docs/manage-w-2-employees.md"),
    ("gusto-get-employee-federal-taxes.md", "https://docs.gusto.com/embedded-payroll/reference/get-v1-employees-employee_id-federal_taxes.md"),
    ("gusto-put-employee-federal-taxes.md", "https://docs.gusto.com/embedded-payroll/reference/put-v1-employees-employee_id-federal_taxes.md"),
    ("gusto-get-employee-state-taxes.md", "https://docs.gusto.com/embedded-payroll/reference/get-v1-employees-employee_id-state_taxes.md"),
    ("gusto-put-employee-state-taxes.md", "https://docs.gusto.com/embedded-payroll/reference/put-v1-employees-employee_id-state_taxes.md"),
    ("gusto-calculate-payroll.md", "https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_id-payrolls-payroll_id-calculate.md"),
    ("gusto-get-payroll-with-taxes.md", "https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_id-payrolls-payroll_id.md"),
    ("gusto-get-company-tax-requirements.md", "https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_uuid-tax_requirements.md"),
    ("gusto-get-state-tax-requirements.md", "https://docs.gusto.com/embedded-payroll/reference/get-v1-companies-company_uuid-tax_requirements-state.md"),
    ("gusto-put-state-tax-requirements.md", "https://docs.gusto.com/embedded-payroll/reference/put-v1-companies-company_uuid-tax_requirements-state.md"),
    ("gusto-get-employee-home-addresses.md", "https://docs.gusto.com/embedded-payroll/reference/get-v1-employees-employee_id-home_addresses.md"),
    ("gusto-post-employee-home-address.md", "https://docs.gusto.com/embedded-payroll/reference/post-v1-employees-employee_id-home_addresses.md"),
    ("gusto-maryland-county-withholding-notes.md", "https://support.gusto.com/article/106622321100000/maryland-registration-and-tax-info"),
]

CHECK = [
    ("llms-index.txt", "https://docs.checkhq.com/llms.txt"),
    ("checkhq-tax-parameters.md", "https://docs.checkhq.com/docs/tax-parameters.md"),
    ("checkhq-calculating-payroll-taxes.md", "https://docs.checkhq.com/docs/calculating-payroll-taxes.md"),
    ("checkhq-multi-state-withholdings.md", "https://docs.checkhq.com/docs/multi-state-taxation-and-reciprocity.md"),
    ("checkhq-overriding-withholding-taxes.md", "https://docs.checkhq.com/docs/overriding-withholding-taxes.md"),
    ("checkhq-taxes-and-agencies.md", "https://docs.checkhq.com/docs/taxes-and-agencies.md"),
    ("checkhq-jurisdictions.md", "https://docs.checkhq.com/docs/jurisdictions.md"),
    ("checkhq-courtesy-withholdings.md", "https://docs.checkhq.com/docs/courtesy-withholdings.md"),
    ("checkhq-overrides.md", "https://docs.checkhq.com/docs/overrides.md"),
    ("checkhq-workplaces.md", "https://docs.checkhq.com/docs/workplaces.md"),
    ("checkhq-list-employee-tax-parameters.md", "https://docs.checkhq.com/reference/list-employees-tax-parameters.md"),
    ("checkhq-list-employee-tax-parameter-settings.md", "https://docs.checkhq.com/reference/list-employee-tax-parameter-settings.md"),
    ("checkhq-bulk-get-employee-tax-params.md", "https://docs.checkhq.com/reference/bulk-get-employee-tax-params.md"),
    ("checkhq-bulk-get-employee-tax-parameter-settings.md", "https://docs.checkhq.com/reference/bulk-get-employee-tax-parameter-settings.md"),
    ("checkhq-bulk-update-employee-tax-parameters.md", "https://docs.checkhq.com/reference/bulk-update-employee-tax-parameters.md"),
    ("checkhq-update-employee-tax-parameters.md", "https://docs.checkhq.com/reference/update-employee-tax-parameters.md"),
    ("checkhq-get-employee-tax-parameter-setting.md", "https://docs.checkhq.com/reference/get-employee-tax-parameter-setting.md"),
    ("checkhq-the-payroll-item-object.md", "https://docs.checkhq.com/reference/the-payroll-item-object.md"),
    ("checkhq-list-taxes.md", "https://docs.checkhq.com/reference/list-taxes.md"),
    ("checkhq-the-tax-object.md", "https://docs.checkhq.com/reference/the-tax-object.md"),
    ("checkhq-preview-payroll.md", "https://docs.checkhq.com/reference/preview-payroll.md"),
    ("checkhq-approve-payroll.md", "https://docs.checkhq.com/reference/approve-payroll.md"),
    ("checkhq-employee-withholdings-setup.md", "https://docs.checkhq.com/reference/employee-withholdings-setup.md"),
    ("checkhq-employee-tax-elections.md", "https://docs.checkhq.com/reference/employee-tax-elections.md"),
    ("checkhq-update-employee-tax-elections.md", "https://docs.checkhq.com/reference/update-employee-tax-elections.md"),
]

def fetch(name, url, subdir):
    dest = ROOT / subdir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "VettedCare-Docs-Mirror/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())
    print(f"ok {subdir}/{name} ({dest.stat().st_size} bytes)")

for name, url in GUSTO:
    fetch(name, url, "gusto")
for name, url in CHECK:
    fetch(name, url, "checkhq")
print("done")
'@

& $python -c $script

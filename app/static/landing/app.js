const els = {
  heroHeadline: document.getElementById("hero-headline"),
  heroSubheadline: document.getElementById("hero-subheadline"),
  valueProps: document.getElementById("value-props"),
  comarNote: document.getElementById("comar-note"),
  payGrid: document.getElementById("pay-grid"),
  applyForm: document.getElementById("apply-form"),
  applyCredential: document.getElementById("apply-credential"),
  applyRate: document.getElementById("apply-rate"),
  npiField: document.getElementById("npi-field"),
  applyNpi: document.getElementById("apply-npi"),
  applyError: document.getElementById("apply-error"),
  applySuccess: document.getElementById("apply-success"),
  successTitle: document.getElementById("success-title"),
  successMessage: document.getElementById("success-message"),
  successBadges: document.getElementById("success-badges"),
  portalLink: document.getElementById("portal-link"),
  applyAgainBtn: document.getElementById("apply-again-btn"),
  toast: document.getElementById("toast"),
};

let landingData = null;

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.borderColor = isError ? "#7f1d1d" : "#1f3344";
  els.toast.classList.remove("hidden");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => els.toast.classList.add("hidden"), 3500);
}

function badge(status, label) {
  const token = String(status || "").toUpperCase();
  let cls = "pending";
  if (["VERIFIED", "ACTIVE", "CLEAR", "PASS", "STUB_PASS"].includes(token)) cls = "ok";
  if (["REJECTED", "SUSPENDED", "EXCLUDED", "FLAGGED", "FAIL", "BLOCKED"].includes(token)) cls = "fail";
  return `<span class="badge ${cls}">${label || token}</span>`;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function renderLanding(data) {
  landingData = data;
  els.heroHeadline.textContent = data.headline;
  els.heroSubheadline.textContent = data.subheadline;
  els.valueProps.innerHTML = (data.value_props || []).map((line) => `<li>${line}</li>`).join("");
  els.comarNote.textContent = data.comar_note || "";
  els.payGrid.innerHTML = (data.credentials || [])
    .map(
      (row) => `
      <article class="pay-card">
        <div>${row.label}</div>
        <strong>$${Number(row.typical_hourly_pay).toFixed(0)}/hr</strong>
        <span>Suggested minimum $${Number(row.suggested_minimum).toFixed(2)}/hr</span>
      </article>`,
    )
    .join("");
  els.applyCredential.innerHTML = (data.credentials || [])
    .map((row) => `<option value="${row.code}">${row.label}</option>`)
    .join("");
  refreshCredentialFields();
  if (els.portalLink) els.portalLink.href = data.portal_url || "/portal";
}

function payBandForCredential(code) {
  return (landingData?.credentials || []).find((row) => row.code === code);
}

function refreshCredentialFields() {
  const code = els.applyCredential.value || "CNA";
  const requiresNpi = code === "LPN";
  els.npiField.classList.toggle("hidden", !requiresNpi);
  els.applyNpi.required = requiresNpi;
  const band = payBandForCredential(code);
  if (band && !els.applyRate.dataset.touched) {
    els.applyRate.value = String(band.suggested_minimum);
  }
}

function showSuccess(result) {
  els.applyForm.classList.add("hidden");
  els.applySuccess.classList.remove("hidden");
  els.successTitle.textContent = result.credentialing_blocked
    ? "Application received — review required"
    : "You're cleared for Maryland shifts";
  els.successMessage.textContent = result.message;
  els.successBadges.innerHTML = [
    badge(result.license_status, `License ${result.license_status}`),
    badge(result.dispatch_status, `Dispatch ${result.dispatch_status}`),
    badge(result.mbon_status, `MBON ${result.mbon_status}`),
    badge(result.oig_status, `OIG ${result.oig_status}`),
    badge(result.judiciary_status, `Judiciary ${result.judiciary_status}`),
  ].join("");
  if (els.portalLink) {
    els.portalLink.href = result.portal_url || "/portal";
  }
}

function resetApplyForm() {
  els.applySuccess.classList.add("hidden");
  els.applyForm.classList.remove("hidden");
  els.applyError.classList.add("hidden");
  els.applyForm.reset();
  delete els.applyRate.dataset.touched;
  refreshCredentialFields();
}

async function submitApplication(event) {
  event.preventDefault();
  els.applyError.classList.add("hidden");
  const credential = els.applyCredential.value;
  const payload = {
    full_name: document.getElementById("apply-name").value.trim(),
    email: document.getElementById("apply-email").value.trim(),
    phone_number: document.getElementById("apply-phone").value.trim(),
    md_license_number: document.getElementById("apply-license").value.trim(),
    credential_type: credential,
    npi_number: credential === "LPN" ? document.getElementById("apply-npi").value.trim() : null,
    home_zip: document.getElementById("apply-zip").value.trim() || null,
    min_hourly_rate: Number(els.applyRate.value),
    password: document.getElementById("apply-password").value,
    service_lines: "NURSING_HOME",
  };
  try {
    const result = await api("/api/landing/maryland/apply", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showSuccess(result);
    showToast(result.credentialing_blocked ? "Application submitted for review" : "License verified — welcome aboard");
  } catch (error) {
    let message = error.message;
    if (message === "duplicate_application") {
      message = "An application with this email, phone, or license already exists. Sign in at the clinician portal.";
    }
    els.applyError.textContent = message;
    els.applyError.classList.remove("hidden");
    showToast(message, true);
  }
}

async function bootstrap() {
  try {
    const data = await api("/api/landing/maryland");
    renderLanding(data);
  } catch (error) {
    els.heroHeadline.textContent = "Maryland CNA & LPN shifts";
    els.heroSubheadline.textContent = "Flexible per-diem nursing home coverage with instant credential verification.";
    showToast(`Could not load pay bands: ${error.message}`, true);
  }
}

els.applyCredential.addEventListener("change", refreshCredentialFields);
els.applyRate.addEventListener("input", () => {
  els.applyRate.dataset.touched = "1";
});
els.applyForm.addEventListener("submit", submitApplication);
els.applyAgainBtn.addEventListener("click", resetApplyForm);

bootstrap();

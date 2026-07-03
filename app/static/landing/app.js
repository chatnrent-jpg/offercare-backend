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
  consentCredential: document.getElementById("consent-credential"),
  consentSms: document.getElementById("consent-sms"),
  consentPrivacy: document.getElementById("consent-privacy"),
  consentTos: document.getElementById("consent-tos"),
  consentCredentialText: document.getElementById("consent-credential-text"),
  consentSmsText: document.getElementById("consent-sms-text"),
  consentPrivacyText: document.getElementById("consent-privacy-text"),
  consentTosText: document.getElementById("consent-tos-text"),
  openPrivacyBtn: document.getElementById("open-privacy-btn"),
  footerPrivacyBtn: document.getElementById("footer-privacy-btn"),
  privacyOverlay: document.getElementById("privacy-overlay"),
  privacyModal: document.getElementById("privacy-modal"),
  privacyTitle: document.getElementById("privacy-title"),
  privacyMeta: document.getElementById("privacy-meta"),
  privacyBody: document.getElementById("privacy-body"),
  closePrivacyBtn: document.getElementById("close-privacy-btn"),
  closePrivacyFooterBtn: document.getElementById("close-privacy-footer-btn"),
  openTosBtn: document.getElementById("open-tos-btn"),
  footerTosBtn: document.getElementById("footer-tos-btn"),
  tosOverlay: document.getElementById("tos-overlay"),
  tosModal: document.getElementById("tos-modal"),
  tosTitle: document.getElementById("tos-title"),
  tosMeta: document.getElementById("tos-meta"),
  tosBody: document.getElementById("tos-body"),
  closeTosBtn: document.getElementById("close-tos-btn"),
  closeTosFooterBtn: document.getElementById("close-tos-footer-btn"),
  toast: document.getElementById("toast"),
  aedtMount: document.getElementById("aedt-disclosure-mount"),
};

let landingData = null;
let consentVersion = "";
let termsOfService = null;
let privacyPolicy = null;
let aedtDisclosure = null;

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

function renderLegalDocument(data, { titleEl, metaEl, bodyEl, store }) {
  store.current = data;
  if (titleEl) titleEl.textContent = data.title || "Legal document";
  if (metaEl) {
    metaEl.textContent = `Version ${data.version || "—"} · Effective ${data.effective_date || "—"}`;
  }
  if (bodyEl) {
    const sections = data.sections || [];
    if (!sections.length) {
      bodyEl.innerHTML = `<p class="tos-loading muted">Document temporarily unavailable. Please refresh and try again.</p>`;
      return;
    }
    bodyEl.innerHTML = sections
      .map(
        (section) => `
        <section class="tos-section">
          <h3>${section.heading}</h3>
          <p>${section.body}</p>
        </section>`,
      )
      .join("");
  }
}

function renderTermsOfService(data) {
  renderLegalDocument(data, {
    titleEl: els.tosTitle,
    metaEl: els.tosMeta,
    bodyEl: els.tosBody,
    store: { get current() { return termsOfService; }, set current(v) { termsOfService = v; } },
  });
  termsOfService = data;
}

function renderPrivacyPolicy(data) {
  renderLegalDocument(data, {
    titleEl: els.privacyTitle,
    metaEl: els.privacyMeta,
    bodyEl: els.privacyBody,
    store: { get current() { return privacyPolicy; }, set current(v) { privacyPolicy = v; } },
  });
  privacyPolicy = data;
}

async function ensureTermsLoaded() {
  if (termsOfService) return termsOfService;
  if (els.tosBody) {
    els.tosBody.innerHTML = `<p class="tos-loading muted">Loading Terms of Service…</p>`;
  }
  if (landingData?.terms_of_service) {
    renderTermsOfService(landingData.terms_of_service);
    return termsOfService;
  }
  const sources = ["/join/terms.json", "/api/landing/maryland/terms-of-service"];
  for (const path of sources) {
    try {
      const data = await api(path);
      renderTermsOfService(data);
      return data;
    } catch {
      // try next source
    }
  }
  throw new Error("Terms of Service could not be loaded. Restart the API and hard-refresh this page.");
}

async function ensurePrivacyLoaded() {
  if (privacyPolicy) return privacyPolicy;
  if (els.privacyBody) {
    els.privacyBody.innerHTML = `<p class="tos-loading muted">Loading Privacy Policy…</p>`;
  }
  if (landingData?.privacy_policy) {
    renderPrivacyPolicy(landingData.privacy_policy);
    return privacyPolicy;
  }
  const sources = ["/join/privacy.json", "/api/landing/maryland/privacy-policy"];
  for (const path of sources) {
    try {
      const data = await api(path);
      renderPrivacyPolicy(data);
      return data;
    } catch {
      // try next source
    }
  }
  throw new Error("Privacy Policy could not be loaded. Restart the API and hard-refresh this page.");
}

async function openTermsDialog() {
  if (!els.tosOverlay) return;
  try {
    await ensureTermsLoaded();
  } catch (error) {
    showToast(`Could not load Terms of Service: ${error.message}`, true);
    return;
  }
  els.tosOverlay.classList.remove("hidden");
  document.body.classList.add("tos-open");
  els.closeTosBtn?.focus();
}

async function openPrivacyDialog() {
  if (!els.privacyOverlay) return;
  try {
    await ensurePrivacyLoaded();
  } catch (error) {
    showToast(`Could not load Privacy Policy: ${error.message}`, true);
    return;
  }
  els.privacyOverlay.classList.remove("hidden");
  document.body.classList.add("tos-open");
  els.closePrivacyBtn?.focus();
}

function closeTermsDialog(markAccepted = false) {
  if (markAccepted && els.consentTos) {
    els.consentTos.checked = true;
  }
  if (!els.tosOverlay) return;
  els.tosOverlay.classList.add("hidden");
  if (!els.privacyOverlay || els.privacyOverlay.classList.contains("hidden")) {
    document.body.classList.remove("tos-open");
  }
}

function closePrivacyDialog(markAccepted = false) {
  if (markAccepted && els.consentPrivacy) {
    els.consentPrivacy.checked = true;
  }
  if (!els.privacyOverlay) return;
  els.privacyOverlay.classList.add("hidden");
  if (!els.tosOverlay || els.tosOverlay.classList.contains("hidden")) {
    document.body.classList.remove("tos-open");
  }
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
  const disclosures = data.consent_disclosures || {};
  consentVersion = disclosures.version || "";
  if (els.consentCredentialText) els.consentCredentialText.textContent = disclosures.credential_screening || "";
  if (els.consentSmsText) els.consentSmsText.textContent = disclosures.sms_dispatch || "";
  if (els.consentPrivacyText) els.consentPrivacyText.textContent = disclosures.privacy_policy || "";
  if (els.consentTosText) els.consentTosText.textContent = disclosures.terms_of_service || "";
  if (data.terms_of_service) {
    renderTermsOfService(data.terms_of_service);
  }
  if (data.privacy_policy) {
    renderPrivacyPolicy(data.privacy_policy);
  }
  mountAedtDisclosure(data.consent_disclosures || {});
}

function mountAedtDisclosure(disclosures) {
  if (!els.aedtMount || !window.VettedCareAedtDisclosure) return;
  els.aedtMount.innerHTML = "";
  aedtDisclosure = window.VettedCareAedtDisclosure.createAedtDisclosureBox({
    copy: {
      body: disclosures.maryland_aedt_30_day || window.VettedCareAedtDisclosure.DEFAULT_COPY.body,
    },
  });
  els.aedtMount.appendChild(aedtDisclosure.element);
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
  if (els.consentCredential) els.consentCredential.checked = false;
  if (els.consentSms) els.consentSms.checked = false;
  if (els.consentPrivacy) els.consentPrivacy.checked = false;
  if (els.consentTos) els.consentTos.checked = false;
  aedtDisclosure?.reset();
  delete els.applyRate.dataset.touched;
  refreshCredentialFields();
}

async function submitApplication(event) {
  event.preventDefault();
  els.applyError.classList.add("hidden");
  if (aedtDisclosure && !aedtDisclosure.validate()) {
    els.applyError.textContent =
      "You must accept the Maryland AEDT automated shift-routing disclosure before applying.";
    els.applyError.classList.remove("hidden");
    showToast("Maryland AEDT disclosure acceptance is required.", true);
    return;
  }
  if (
    !els.consentCredential?.checked ||
    !els.consentSms?.checked ||
    !els.consentPrivacy?.checked ||
    !els.consentTos?.checked
  ) {
    els.applyError.textContent = "Please check all required consent boxes, including Privacy Policy and Terms of Service.";
    els.applyError.classList.remove("hidden");
    showToast("Privacy Policy, consent, and Terms of Service acceptance are required.", true);
    return;
  }
  if (!consentVersion) {
    els.applyError.textContent = "Consent disclosures failed to load. Refresh the page and try again.";
    els.applyError.classList.remove("hidden");
    return;
  }
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
    consent_version: consentVersion,
    consent_credential_screening: true,
    consent_sms_dispatch: true,
    consent_privacy_policy: true,
    consent_terms_of_service: true,
    consent_aedt_30_day: true,
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
    if (message === "consent_required" || message === "consent_version_mismatch") {
      message = "Please refresh the page and accept the current Privacy Policy and Terms of Service before applying.";
    }
    els.applyError.textContent = message;
    els.applyError.classList.remove("hidden");
    showToast(message, true);
  }
}

async function bootstrap() {
  const [landingResult, termsResult, privacyResult] = await Promise.allSettled([
    api("/api/landing/maryland"),
    api("/join/terms.json"),
    api("/join/privacy.json"),
  ]);

  if (landingResult.status === "fulfilled") {
    renderLanding(landingResult.value);
    if (landingResult.value.terms_of_service) {
      renderTermsOfService(landingResult.value.terms_of_service);
    }
    if (landingResult.value.privacy_policy) {
      renderPrivacyPolicy(landingResult.value.privacy_policy);
    }
  } else {
    els.heroHeadline.textContent = "Maryland CNA & LPN shifts";
    els.heroSubheadline.textContent = "Flexible per-diem nursing home coverage with instant credential verification.";
    showToast(`Could not load apply page: ${landingResult.reason?.message || "error"}`, true);
  }

  if (!termsOfService && termsResult.status === "fulfilled") {
    renderTermsOfService(termsResult.value);
  }
  if (!privacyPolicy && privacyResult.status === "fulfilled") {
    renderPrivacyPolicy(privacyResult.value);
  }
}

els.applyCredential.addEventListener("change", refreshCredentialFields);
els.applyRate.addEventListener("input", () => {
  els.applyRate.dataset.touched = "1";
});
els.applyForm.addEventListener("submit", submitApplication);
els.applyAgainBtn.addEventListener("click", resetApplyForm);
els.openPrivacyBtn?.addEventListener("click", () => {
  openPrivacyDialog().catch((error) => showToast(error.message, true));
});
els.footerPrivacyBtn?.addEventListener("click", () => {
  openPrivacyDialog().catch((error) => showToast(error.message, true));
});
els.openTosBtn?.addEventListener("click", () => {
  openTermsDialog().catch((error) => showToast(error.message, true));
});
els.footerTosBtn?.addEventListener("click", () => {
  openTermsDialog().catch((error) => showToast(error.message, true));
});
els.closePrivacyBtn?.addEventListener("click", () => closePrivacyDialog(false));
els.closePrivacyFooterBtn?.addEventListener("click", () => closePrivacyDialog(true));
els.closeTosBtn?.addEventListener("click", () => closeTermsDialog(false));
els.closeTosFooterBtn?.addEventListener("click", () => closeTermsDialog(true));
els.privacyOverlay?.addEventListener("click", (event) => {
  if (event.target === els.privacyOverlay) closePrivacyDialog(false);
});
els.tosOverlay?.addEventListener("click", (event) => {
  if (event.target === els.tosOverlay) closeTermsDialog(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (els.privacyOverlay && !els.privacyOverlay.classList.contains("hidden")) {
      closePrivacyDialog(false);
    } else if (els.tosOverlay && !els.tosOverlay.classList.contains("hidden")) {
      closeTermsDialog(false);
    }
  }
});

bootstrap();

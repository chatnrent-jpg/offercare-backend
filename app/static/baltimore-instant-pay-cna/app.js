const els = {
  heroHeadline: document.getElementById("hero-headline"),
  heroSubheadline: document.getElementById("hero-subheadline"),
  trustChips: document.getElementById("trust-chips"),
  typicalPay: document.getElementById("typical-pay"),
  badgeInstant: document.getElementById("badge-instant"),
  titleInstant: document.getElementById("title-instant"),
  bodyInstant: document.getElementById("body-instant"),
  badgeW2: document.getElementById("badge-w2"),
  titleW2: document.getElementById("title-w2"),
  bodyW2: document.getElementById("body-w2"),
  applyHeadline: document.getElementById("apply-headline"),
  applySubheadline: document.getElementById("apply-subheadline"),
  applyForm: document.getElementById("text-apply-form"),
  applyPhone: document.getElementById("apply-phone"),
  applyName: document.getElementById("apply-name"),
  consentSms: document.getElementById("consent-sms"),
  consentLabel: document.getElementById("consent-label"),
  applySubmit: document.getElementById("apply-submit"),
  applyError: document.getElementById("apply-error"),
  applySuccess: document.getElementById("apply-success"),
  successMessage: document.getElementById("success-message"),
  fullApplyLink: document.getElementById("full-apply-link"),
  stickyCta: document.getElementById("sticky-cta"),
  stickyApplyBtn: document.getElementById("sticky-apply-btn"),
  toast: document.getElementById("toast"),
};

let landingData = null;
let consentVersion = "";

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.remove("hidden");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => els.toast.classList.add("hidden"), 3200);
}

function formatPhoneInput(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 10);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

function resolveLandingApiPaths() {
  const routeMatch = window.location.pathname.match(/^\/([^/]+)-instant-pay-([^/]+)\/?$/);
  if (routeMatch) {
    const apiPath = `/api/landing/instant-pay/${routeMatch[1]}/${routeMatch[2]}`;
    return { apiPath, textApplyPath: `${apiPath}/text-apply` };
  }
  return {
    apiPath: "/api/landing/baltimore-instant-pay-cna",
    textApplyPath: "/api/landing/baltimore-instant-pay-cna/text-apply",
  };
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
  consentVersion = data.consent_version || "";

  els.heroHeadline.textContent = data.headline;
  els.heroSubheadline.textContent = data.subheadline;
  els.typicalPay.textContent = `$${Number(data.typical_hourly_pay || 0).toFixed(0)}`;

  els.trustChips.innerHTML = (data.trust_chips || [])
    .map((chip) => `<span class="trust-chip">${chip}</span>`)
    .join("");

  const points = data.selling_points || [];
  const instant = points.find((p) => p.id === "instant_stripe_payout") || points[0];
  const w2 = points.find((p) => p.id === "w2_compliance") || points[1];

  if (instant) {
    els.badgeInstant.textContent = instant.badge;
    els.titleInstant.textContent = instant.title;
    els.bodyInstant.textContent = instant.body;
  }
  if (w2) {
    els.badgeW2.textContent = w2.badge;
    els.titleW2.textContent = w2.title;
    els.bodyW2.textContent = w2.body;
  }

  const textApply = data.text_apply || {};
  els.applyHeadline.textContent = textApply.headline || "Text to apply";
  els.applySubheadline.textContent = textApply.subheadline || "";
  els.applyPhone.placeholder = textApply.phone_placeholder || "(410) 555-0199";
  els.consentLabel.textContent = textApply.consent_label || "";
  els.applySubmit.querySelector(".cta-label").textContent = textApply.cta_label || "Text me shift offers";
  if (els.fullApplyLink && data.full_apply_url) {
    els.fullApplyLink.href = data.full_apply_url;
  }
}

function hideStickyWhenApplyVisible() {
  if (!els.stickyCta || !els.applyForm) return;
  const observer = new IntersectionObserver(
    ([entry]) => {
      els.stickyCta.classList.toggle("is-hidden", entry.isIntersecting);
    },
    { threshold: 0.35, rootMargin: "0px 0px -80px 0px" }
  );
  observer.observe(els.applyForm);
}

async function submitTextApply(event, textApplyPath) {
  event.preventDefault();
  els.applyError.classList.add("hidden");

  if (!els.consentSms.checked) {
    els.applyError.textContent = "Please agree to receive shift-offer text messages.";
    els.applyError.classList.remove("hidden");
    return;
  }
  if (!consentVersion) {
    els.applyError.textContent = "Page failed to load. Refresh and try again.";
    els.applyError.classList.remove("hidden");
    return;
  }

  const phoneDigits = els.applyPhone.value.replace(/\D/g, "");
  if (phoneDigits.length !== 10) {
    els.applyError.textContent = "Enter a valid 10-digit US mobile number.";
    els.applyError.classList.remove("hidden");
    return;
  }

  els.applySubmit.disabled = true;
  const payload = {
    phone_number: phoneDigits,
    full_name: els.applyName.value.trim() || null,
    credential_type: landingData?.apply_defaults?.credential_type || "CNA",
    consent_version: consentVersion,
    consent_sms_dispatch: true,
  };

  try {
    const result = await api(textApplyPath, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    els.applyForm.classList.add("hidden");
    els.applySuccess.classList.remove("hidden");
    els.successMessage.textContent = result.message;
    if (result.full_apply_url && els.fullApplyLink) {
      els.fullApplyLink.href = result.full_apply_url;
    }
    const market = landingData?.region_label || landingData?.market || "Maryland";
    showToast(`You're in the ${market} intake queue`);
    els.stickyCta?.classList.add("is-hidden");
  } catch (error) {
    let message = error.message;
    if (message === "duplicate_application") {
      message = "This number is already in our intake queue. Watch for our text or sign in at the portal.";
    }
    if (message === "portal_account_exists") {
      message = "An account with this number already exists. Sign in at the clinician portal.";
    }
    els.applyError.textContent = message;
    els.applyError.classList.remove("hidden");
    showToast(message);
  } finally {
    els.applySubmit.disabled = false;
  }
}

async function bootstrap() {
  const { apiPath, textApplyPath } = resolveLandingApiPaths();

  try {
    const data = await api(apiPath);
    renderLanding(data);
  } catch {
    els.heroHeadline.textContent = "Maryland shifts — instant pay";
    els.heroSubheadline.textContent = "W-2 compliance and Stripe instant payout after every shift.";
  }

  els.applyPhone.addEventListener("input", (event) => {
    event.target.value = formatPhoneInput(event.target.value);
  });
  els.applyForm.addEventListener("submit", (event) => submitTextApply(event, textApplyPath));
  els.stickyApplyBtn?.addEventListener("click", () => {
    document.getElementById("apply")?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => els.applyPhone?.focus(), 350);
  });
  hideStickyWhenApplyVisible();
}

bootstrap();

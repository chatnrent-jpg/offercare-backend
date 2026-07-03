(function initMarylandAedtDisclosure(global) {
  const DEFAULT_COPY = {
    eyebrow: "Required · Maryland AEDT 30-day notice",
    title: "Automated shift-routing disclosure",
    body:
      "VettedCare.ai uses an automated AI tool to evaluate your Maryland license credentials, " +
      "geographic proximity to open shifts, and experience parameters when routing per-diem " +
      "shift opportunities. Maryland law requires this notice before automated employment " +
      "decision tools are used in hiring and shift matching.",
    checkboxLabel:
      "I have read and understand this Maryland AEDT disclosure. I consent to automated AI " +
      "processing of my license credentials, geographic proximity, and experience parameters " +
      "for shift routing.",
  };

  function createAedtDisclosureBox(options = {}) {
    const copy = { ...DEFAULT_COPY, ...(options.copy || {}) };
    const checkboxId = options.checkboxId || `aedt-consent-${Math.random().toString(36).slice(2, 9)}`;

    const root = document.createElement("div");
    root.className = "aedt-disclosure-box";
    root.innerHTML = `
      <p class="aedt-disclosure-box__eyebrow">${copy.eyebrow}</p>
      <h3 class="aedt-disclosure-box__title">${copy.title}</h3>
      <p class="aedt-disclosure-box__body">${copy.body}</p>
      <label class="aedt-disclosure-box__check" for="${checkboxId}">
        <input id="${checkboxId}" type="checkbox" name="consent_aedt_30_day" value="true" />
        <span>${copy.checkboxLabel}</span>
      </label>
      <p class="aedt-disclosure-box__error hidden" data-aedt-error></p>
    `;

    const checkbox = root.querySelector(`#${checkboxId}`);
    const errorEl = root.querySelector("[data-aedt-error]");

    function clearError() {
      root.classList.remove("is-invalid");
      errorEl.classList.add("hidden");
      errorEl.textContent = "";
    }

    function showError(message) {
      root.classList.remove("is-invalid");
      root.classList.add("is-invalid");
      errorEl.textContent = message;
      errorEl.classList.remove("hidden");
    }

    checkbox.addEventListener("change", clearError);

    return {
      element: root,
      checkbox,
      isAccepted() {
        return Boolean(checkbox.checked);
      },
      validate(message = "You must accept the Maryland AEDT automated shift-routing disclosure.") {
        if (this.isAccepted()) {
          clearError();
          return true;
        }
        showError(message);
        checkbox.focus();
        return false;
      },
      reset() {
        checkbox.checked = false;
        clearError();
      },
      payloadField() {
        return { consent_aedt_30_day: this.isAccepted() };
      },
    };
  }

  function renderAedtConsentStatus(container, signedAtIso) {
    if (!container) return;
    const signed = signedAtIso ? new Date(signedAtIso) : null;
    const valid = signed && !Number.isNaN(signed.getTime());
    container.innerHTML = valid
      ? `<div class="aedt-disclosure-status">Maryland AEDT disclosure signed ${signed.toLocaleString()}.</div>`
      : `<div class="aedt-disclosure-status is-pending">Maryland AEDT disclosure not yet recorded. Complete registration at <a href="/join">/join</a>.</div>`;
  }

  global.VettedCareAedtDisclosure = {
    DEFAULT_COPY,
    createAedtDisclosureBox,
    renderAedtConsentStatus,
  };
})(window);

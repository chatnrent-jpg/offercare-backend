const STORAGE_KEY = "offercare_clinician_token";
const INSTALL_DISMISS_KEY = "offercare_install_dismissed";

const els = {
  gate: document.getElementById("gate"),
  app: document.getElementById("app"),
  tabLogin: document.getElementById("tab-login"),
  tabApply: document.getElementById("tab-apply"),
  loginForm: document.getElementById("login-form"),
  applyForm: document.getElementById("apply-form"),
  gateError: document.getElementById("gate-error"),
  welcomeName: document.getElementById("welcome-name"),
  refreshBtn: document.getElementById("refresh-btn"),
  logoutBtn: document.getElementById("logout-btn"),
  stats: document.getElementById("stats"),
  statusCard: document.getElementById("status-card"),
  historyList: document.getElementById("history-list"),
  shiftsTable: document.getElementById("shifts-table"),
  shiftStateFilter: document.getElementById("shift-state-filter"),
  shiftCountyFilter: document.getElementById("shift-county-filter"),
  shiftFacilityTypeFilter: document.getElementById("shift-facility-type-filter"),
  shiftRoleFilter: document.getElementById("shift-role-filter"),
  shiftMinPayFilter: document.getElementById("shift-min-pay-filter"),
  applyShiftFiltersBtn: document.getElementById("apply-shift-filters-btn"),
  placementsTable: document.getElementById("placements-table"),
  preferencesForm: document.getElementById("preferences-form"),
  prefMinRate: document.getElementById("pref-min-rate"),
  prefServiceLines: document.getElementById("pref-service-lines"),
  downloadMatchedCalendarBtn: document.getElementById("download-matched-calendar-btn"),
  showAllShiftsToggle: document.getElementById("show-all-shifts-toggle"),
  downloadPlacementsCalendarBtn: document.getElementById("download-placements-calendar-btn"),
  enablePushBtn: document.getElementById("enable-push-btn"),
  disablePushBtn: document.getElementById("disable-push-btn"),
  pushStatus: document.getElementById("push-status"),
  installBanner: document.getElementById("install-banner"),
  installAppBtn: document.getElementById("install-app-btn"),
  dismissInstallBtn: document.getElementById("dismiss-install-btn"),
  installAppTopBtn: document.getElementById("install-app-top-btn"),
  toast: document.getElementById("toast"),
  demoHintBanner: document.getElementById("demo-hint-banner"),
  demoHintMismatchBanner: document.getElementById("demo-hint-mismatch-banner"),
};

let activePushEndpoint = null;
let deferredInstallPrompt = null;
let careTaxonomy = null;
let showAllOpenShifts = false;

function credentialsForState(state) {
  const gnaStates = new Set(careTaxonomy?.state_credential_rules?.gna_license_states || ["MD", "DC"]);
  const all = careTaxonomy?.credential_types || [];
  if (!all.length) {
    return [
      { code: "RN", label: "Registered Nurse (RN)" },
      { code: "LPN", label: "Licensed Practical Nurse (LPN)" },
      { code: "CNA", label: "Certified Nursing Assistant (CNA)" },
      ...(gnaStates.has(state) ? [{ code: "GNA", label: "Geriatric Nursing Assistant (GNA)" }] : []),
      { code: "NA", label: "Nursing Assistant" },
    ];
  }
  if (gnaStates.has(state)) return all;
  return all.filter((row) => row.code !== "GNA");
}

function refreshApplyCredentialOptions() {
  const stateSelect = document.getElementById("apply-state");
  const credentialSelect = document.getElementById("apply-credential");
  const hint = document.getElementById("apply-credential-hint");
  if (!stateSelect || !credentialSelect) return;

  const state = stateSelect.value || "MD";
  const previous = credentialSelect.value;
  const options = credentialsForState(state);
  credentialSelect.innerHTML = options
    .map((row) => `<option value="${row.code}">${row.label}</option>`)
    .join("");
  if (options.some((row) => row.code === previous)) credentialSelect.value = previous;
  else credentialSelect.value = options[0]?.code || "RN";

  const gnaStates = new Set(careTaxonomy?.state_credential_rules?.gna_license_states || ["MD", "DC"]);
  if (hint) {
    if (gnaStates.has(state)) {
      hint.textContent = "Maryland and DC license GNA as a distinct credential.";
    } else {
      hint.textContent = "GNA is not licensed in this state — select CNA for skilled nursing shifts.";
    }
    hint.classList.remove("hidden");
  }
  refreshNpiField();
}

function refreshNpiField() {
  const credentialSelect = document.getElementById("apply-credential");
  const npiInput = document.getElementById("apply-npi");
  const npiLabel = document.querySelector('label[for="apply-npi"]');
  if (!credentialSelect || !npiInput) return;
  const requiresNpi = ["RN", "LPN"].includes(credentialSelect.value);
  npiInput.required = requiresNpi;
  npiInput.placeholder = requiresNpi ? "Required for RN/LPN" : "Optional for CNA/GNA/NA";
  if (npiLabel) {
    npiLabel.textContent = requiresNpi ? "NPI (10 digits, required)" : "NPI (optional for assistants)";
  }
}

async function loadCareTaxonomy() {
  if (careTaxonomy) return careTaxonomy;
  careTaxonomy = await api("/api/care/taxonomy");
  return careTaxonomy;
}

async function initApplyForm() {
  await loadCareTaxonomy();
  refreshApplyCredentialOptions();
}

function getToken() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

function setToken(value) {
  if (value) localStorage.setItem(STORAGE_KEY, value);
  else localStorage.removeItem(STORAGE_KEY);
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.borderColor = isError ? "#7f1d1d" : "#2a3650";
  els.toast.classList.remove("hidden");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => els.toast.classList.add("hidden"), 3500);
}

function showInstallPrompt() {
  if (localStorage.getItem(INSTALL_DISMISS_KEY)) return;
  els.installBanner?.classList.remove("hidden");
  els.installAppTopBtn?.classList.remove("hidden");
}

function hideInstallPrompt(persistDismiss = false) {
  if (persistDismiss) localStorage.setItem(INSTALL_DISMISS_KEY, "1");
  els.installBanner?.classList.add("hidden");
}

async function registerPortalServiceWorker() {
  if (!("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register("/portal/sw.js");
  } catch {
    return null;
  }
}

async function installPortalApp() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    hideInstallPrompt(true);
    els.installAppTopBtn?.classList.add("hidden");
    showToast("OfferCare installed");
    return;
  }
  showToast("Use your browser menu to add OfferCare to your home screen");
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  showInstallPrompt();
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  hideInstallPrompt(true);
  els.installAppTopBtn?.classList.add("hidden");
});

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
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

function badge(status) {
  const token = String(status || "").toUpperCase();
  let cls = "pending";
  if (["VERIFIED", "SUBMITTED", "LOCKED", "BROADCASTING", "OPEN"].includes(token)) cls = "ok";
  if (["REJECTED", "FAILED", "EXPIRED"].includes(token)) cls = "fail";
  return `<span class="badge ${cls}">${token}</span>`;
}

function fmtShiftTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fmtPct(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

function renderPushStatus(subscriptions) {
  const enabled = subscriptions.length > 0;
  activePushEndpoint = enabled ? subscriptions[0].endpoint : null;
  els.enablePushBtn.classList.toggle("hidden", enabled);
  els.disablePushBtn.classList.toggle("hidden", !enabled);
  els.pushStatus.textContent = enabled
    ? `${subscriptions.length} device${subscriptions.length === 1 ? "" : "s"} subscribed`
    : "Push alerts not enabled on this device";
}

async function refreshPushStatus() {
  if (!getToken()) return;
  try {
    const subscriptions = await api("/api/clinicians/me/push/subscriptions");
    renderPushStatus(subscriptions);
  } catch {
    renderPushStatus([]);
  }
}

async function enablePushAlerts() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new Error("Push notifications are not supported in this browser");
  }
  const config = await api("/api/clinicians/me/push/config");
  if (!config.enabled || !config.public_key) {
    throw new Error("Push alerts are not available right now");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Notification permission denied");
  }
  const registration = await registerPortalServiceWorker();
  const pushRegistration = registration || (await navigator.serviceWorker.getRegistration("/portal/sw.js"));
  const subscription = await (pushRegistration || registration).pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.public_key),
  });
  const json = subscription.toJSON();
  await api("/api/clinicians/me/push/subscribe", {
    method: "POST",
    body: JSON.stringify({
      endpoint: json.endpoint,
      keys: json.keys,
      user_agent: navigator.userAgent,
    }),
  });
  await refreshPushStatus();
  showToast(config.dry_run ? "Push alerts enabled (dry-run mode)" : "Push alerts enabled");
}

async function disablePushAlerts() {
  if (!activePushEndpoint) {
    await refreshPushStatus();
    return;
  }
  const registration = await navigator.serviceWorker.getRegistration("/portal/sw.js");
  const subscription = await registration?.pushManager.getSubscription();
  await api("/api/clinicians/me/push/subscribe", {
    method: "DELETE",
    body: JSON.stringify({ endpoint: activePushEndpoint, keys: { p256dh: "x", auth: "x" } }),
  });
  if (subscription) await subscription.unsubscribe();
  await refreshPushStatus();
  showToast("Push alerts disabled");
}

function showGate() {
  els.gate.classList.remove("hidden");
  els.app.classList.add("hidden");
}

function showApp() {
  els.gate.classList.add("hidden");
  els.app.classList.remove("hidden");
}

function setAuthTab(mode) {
  const login = mode === "login";
  els.tabLogin.classList.toggle("active", login);
  els.tabApply.classList.toggle("active", !login);
  els.loginForm.classList.toggle("hidden", !login);
  els.applyForm.classList.toggle("hidden", login);
  els.gateError.classList.add("hidden");
  if (!login) initApplyForm().catch(() => refreshApplyCredentialOptions());
}

function parseServiceLines(value) {
  return String(value || "ALL")
    .split(",")
    .map((token) => token.trim().toUpperCase())
    .filter(Boolean);
}

function renderPreferencesForm(preferences) {
  if (!els.prefMinRate || !els.prefServiceLines) return;
  els.prefMinRate.value = Number(preferences.min_hourly_rate || 0).toFixed(2);
  const selected = new Set(parseServiceLines(preferences.service_lines));
  const options = preferences.service_line_options || [];
  els.prefServiceLines.innerHTML = options
    .map(
      (row) => `
        <label class="inline-check">
          <input type="checkbox" value="${row.code}" ${selected.has(row.code) ? "checked" : ""} />
          ${row.label}
        </label>`,
    )
    .join("");
}

function collectServiceLinesFromForm() {
  const checked = Array.from(els.prefServiceLines?.querySelectorAll("input:checked") || []).map(
    (input) => input.value,
  );
  if (!checked.length) {
    throw new Error("Select at least one care setting.");
  }
  if (checked.includes("ALL")) return "ALL";
  return checked.join(",");
}

async function loadPreferences() {
  return api("/api/clinicians/me/preferences");
}

async function savePreferences(event) {
  event.preventDefault();
  try {
    const payload = {
      min_hourly_rate: Number(els.prefMinRate.value),
      service_lines: collectServiceLinesFromForm(),
    };
    const preferences = await api("/api/clinicians/me/preferences", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    renderPreferencesForm(preferences);
    await refreshDashboard();
    showToast("Preferences saved");
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderStats(provider, placements, shifts) {
  const shiftLabel = showAllOpenShifts ? "Open shifts" : "Matched shifts";
  els.stats.innerHTML = `
    <div class="stat-card"><span class="muted">License</span>${badge(provider.license_status)}</div>
    <div class="stat-card"><span class="muted">Credential</span><strong>${provider.credential_type || "RN"}</strong></div>
    <div class="stat-card"><span class="muted">Min rate</span><strong>$${Number(provider.min_hourly_rate).toFixed(2)}/hr</strong></div>
    <div class="stat-card"><span class="muted">Response H</span><strong>${fmtPct(provider.response_propensity)}</strong></div>
    <div class="stat-card"><span class="muted">Fatigue T</span><strong>${Number(provider.fatigue_score).toFixed(2)}</strong></div>
    <div class="stat-card"><span class="muted">Placements</span><strong>${placements.length}</strong></div>
    <div class="stat-card"><span class="muted">${shiftLabel}</span><strong>${shifts.length}</strong></div>
  `;
}

function safetyBadge(status) {
  const key = String(status || "ACTION_NEEDED").toUpperCase();
  const cls =
    key === "CLEAR" ? "ok" : key === "EXPIRING" ? "pending" : key === "BLOCKED" ? "fail" : "pending";
  return `<span class="badge ${cls}">${key.replace(/_/g, " ")}</span>`;
}

function renderStatus(application, safety) {
  const provider = application.provider;
  const safetyBlock = safety
    ? `
    <div class="safety-banner">
      <p><strong>Credential safety:</strong> ${safetyBadge(safety.vetted_status)}</p>
      <p class="muted">${safety.message}</p>
      <p class="muted">Placement eligible: ${safety.dispatch_eligible ? "Yes" : "No — complete credential requirements"}</p>
    </div>`
    : "";
  els.statusCard.innerHTML = `
    ${safetyBlock}
    <strong>${provider.full_name}</strong>
    <p class="muted">${provider.email} · ${provider.phone_number}</p>
    <p class="muted">License ${provider.md_license_number} · NPI ${provider.npi_number}</p>
    <p class="muted">Portal ${application.portal_enabled ? "enabled" : "disabled"} · License status ${provider.license_status}</p>
  `;
  const history = application.verification_history || [];
  if (!history.length) {
    els.historyList.innerHTML = `<p class="empty">No verification events yet.</p>`;
    return;
  }
  els.historyList.innerHTML = history.map((row) => `
    <div class="history-item">
      <strong>${row.event_type}</strong>
      <span class="muted">${row.check_result || ""}${row.notes ? ` — ${row.notes}` : ""}</span>
    </div>`).join("");
}

function buildShiftQuery() {
  const params = new URLSearchParams({ limit: "50" });
  const state = els.shiftStateFilter?.value.trim();
  const county = els.shiftCountyFilter?.value.trim();
  const facilityType = els.shiftFacilityTypeFilter?.value.trim();
  const role = els.shiftRoleFilter?.value.trim();
  const minPay = els.shiftMinPayFilter?.value.trim();
  if (state) params.set("state", state);
  if (county) params.set("county", county);
  if (facilityType) params.set("facility_type", facilityType);
  if (role) params.set("shift_role", role);
  if (minPay) params.set("min_pay", minPay);
  if (showAllOpenShifts || !getToken()) {
    return `/api/shifts/open?${params.toString()}`;
  }
  return `/api/clinicians/me/matched-shifts?${params.toString()}`;
}

function buildShiftCalendarQuery() {
  const params = new URLSearchParams({ limit: "50" });
  const state = els.shiftStateFilter?.value.trim();
  const county = els.shiftCountyFilter?.value.trim();
  const facilityType = els.shiftFacilityTypeFilter?.value.trim();
  const role = els.shiftRoleFilter?.value.trim();
  const minPay = els.shiftMinPayFilter?.value.trim();
  if (state) params.set("state", state);
  if (county) params.set("county", county);
  if (facilityType) params.set("facility_type", facilityType);
  if (role) params.set("shift_role", role);
  if (minPay) params.set("min_pay", minPay);
  if (showAllOpenShifts || !getToken()) {
    return `/api/shifts/open/calendar.ics?${params.toString()}`;
  }
  return `/api/clinicians/me/matched-shifts/calendar.ics?${params.toString()}`;
}

function populateShiftFilters(options) {
  const stateValue = els.shiftStateFilter?.value || "";
  const countyValue = els.shiftCountyFilter?.value || "";
  const facilityTypeValue = els.shiftFacilityTypeFilter?.value || "";
  const roleValue = els.shiftRoleFilter?.value || "";
  if (els.shiftStateFilter) {
    els.shiftStateFilter.innerHTML =
      `<option value="">All states</option>` +
      (options.states || []).map((row) => `<option value="${row}">${row}</option>`).join("");
    els.shiftStateFilter.value = stateValue;
  }
  if (els.shiftCountyFilter) {
    els.shiftCountyFilter.innerHTML =
      `<option value="">All counties</option>` +
      (options.counties || []).map((row) => `<option value="${row}">${row}</option>`).join("");
    els.shiftCountyFilter.value = countyValue;
  }
  if (els.shiftFacilityTypeFilter) {
    els.shiftFacilityTypeFilter.innerHTML =
      `<option value="">All settings</option>` +
      (options.facility_types || []).map((row) => `<option value="${row}">${row.replaceAll("_", " ")}</option>`).join("");
    els.shiftFacilityTypeFilter.value = facilityTypeValue;
  }
  if (els.shiftRoleFilter) {
    els.shiftRoleFilter.innerHTML =
      `<option value="">All roles</option>` +
      (options.shift_roles || []).map((row) => `<option value="${row}">${row}</option>`).join("");
    els.shiftRoleFilter.value = roleValue;
  }
}

async function loadShifts() {
  return api(buildShiftQuery());
}

function renderShifts(rows) {
  if (!rows.length) {
    const emptyCopy = showAllOpenShifts
      ? "No open shifts in your selected filters right now."
      : "No matched shifts for your credential and minimum pay right now.";
    els.shiftsTable.innerHTML = `<p class="empty">${emptyCopy}</p>`;
    return;
  }
  const matchedView = !showAllOpenShifts && getToken();
  els.shiftsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Setting</th><th>State</th><th>County</th><th>Role</th><th>Starts</th><th>Pay</th>${matchedView ? "<th>+$ vs min</th>" : ""}<th>Status</th>${matchedView ? "<th></th>" : ""}</tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.facility_type_label || row.facility_type || ""}</td>
            <td>${row.state || "MD"}</td>
            <td>${row.county}</td>
            <td>${row.shift_role_label || row.shift_role}</td>
            <td>${fmtShiftTime(row.shift_starts_at)}</td>
            <td>$${Number(row.hourly_pay_rate).toFixed(2)}/hr</td>
            ${matchedView ? `<td>$${Number(row.rate_delta ?? 0).toFixed(2)}</td>` : ""}
            <td>${badge(row.compliance_lock_status)}</td>
            ${matchedView ? `<td>${row.compliance_lock_status === "BROADCASTING" ? `<button class="btn ghost lock-shift-btn" type="button" data-offer-id="${row.offer_id}">Lock</button>` : ""}</td>` : ""}
          </tr>`).join("")}
      </tbody>
    </table>`;
  if (matchedView) {
    els.shiftsTable.querySelectorAll(".lock-shift-btn").forEach((button) => {
      button.addEventListener("click", () => lockMatchedShift(button.dataset.offerId));
    });
  }
}

async function lockMatchedShift(offerId) {
  try {
    const data = await api(`/api/clinicians/me/matched-shifts/${offerId}/lock`, { method: "POST" });
    showToast(data.message || "Shift locked");
    await refreshDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderPlacements(rows) {
  if (!rows.length) {
    els.placementsTable.innerHTML = `<p class="empty">No locked shifts yet. Lock a matched shift above or reply YES to an SMS alert.</p>`;
    return;
  }
  els.placementsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Unit</th><th>Starts</th><th>Rate</th><th>VMS</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.clinical_unit}</td>
            <td>${fmtShiftTime(row.shift_starts_at)}</td>
            <td>$${Number(row.hourly_bill_rate).toFixed(2)}/hr</td>
            <td>${badge(row.vms_submission_status)} ${row.vms_external_ref ? `<br><span class="muted">${row.vms_external_ref}</span>` : ""}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

async function downloadFile(path, filename) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function getOfferIdFromQuery() {
  return new URLSearchParams(window.location.search).get("offer");
}

async function loadDemoHint() {
  const offerId = getOfferIdFromQuery();
  if (!offerId || !els.demoHintBanner) return;
  try {
    const hint = await api(`/api/portal/demo-hint?offer_id=${encodeURIComponent(offerId)}`);
    els.demoHintBanner.classList.remove("hidden");
    els.demoHintBanner.innerHTML = `
      <strong>Demo shift:</strong> ${hint.facility_name} (${hint.shift_role})<br />
      Sign in as <strong>${hint.clinician_email}</strong> / <strong>${hint.portal_password_hint}</strong>`;
    const loginEmail = document.getElementById("login-email");
    const loginPassword = document.getElementById("login-password");
    if (loginEmail && !loginEmail.value) loginEmail.value = hint.clinician_email;
    if (loginPassword && !loginPassword.value) loginPassword.value = hint.portal_password_hint;
    setAuthTab("login");
  } catch {
    els.demoHintBanner.classList.add("hidden");
  }
}

async function refreshDemoHintMismatch(provider) {
  const offerId = getOfferIdFromQuery();
  if (!offerId || !els.demoHintMismatchBanner) {
    els.demoHintMismatchBanner?.classList.add("hidden");
    return false;
  }
  try {
    const check = await api(`/api/portal/demo-hint/check?offer_id=${encodeURIComponent(offerId)}`);
    if (!check.matches) {
      els.demoHintMismatchBanner.classList.remove("hidden");
      els.demoHintMismatchBanner.innerHTML = `
        <strong>Wrong demo clinician:</strong> ${check.facility_name} (${check.shift_role})<br />
        You are signed in as <strong>${check.signed_in_email}</strong>. Sign out and sign in as <strong>${check.expected_clinician_email}</strong> to lock this shift.`;
      return false;
    }
    els.demoHintMismatchBanner.classList.add("hidden");
    return true;
  } catch {
    els.demoHintMismatchBanner?.classList.add("hidden");
    return true;
  }
}

function clearOfferQueryParam() {
  if (!window.location.search.includes("offer=")) return;
  window.history.replaceState({}, "", "/portal/");
}

function focusOfferFromAlert(offerId) {
  if (!offerId || !els.shiftsTable) return;
  const lockButton = els.shiftsTable.querySelector(`.lock-shift-btn[data-offer-id="${offerId}"]`);
  const row = lockButton?.closest("tr");
  if (!row) return;
  row.classList.add("shift-highlight");
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  showToast("Matched shift from your alert — tap Lock to accept.");
  clearOfferQueryParam();
}

async function refreshDashboard() {
  const [application, placements, shiftFilters, shifts, preferences, safety] = await Promise.all([
    api("/api/clinicians/me/application"),
    api("/api/clinicians/me/placements"),
    api("/api/shifts/filters"),
    loadShifts(),
    loadPreferences(),
    api("/api/clinicians/me/safety").catch(() => null),
  ]);
  populateShiftFilters(shiftFilters);
  const provider = application.provider;
  els.welcomeName.textContent = provider.full_name;
  renderPreferencesForm(preferences);
  renderStats(provider, placements, shifts);
  renderStatus(application, safety);
  renderShifts(shifts);
  renderPlacements(placements);
  await refreshPushStatus();
  const clinicianMatchesDemoOffer = await refreshDemoHintMismatch(provider);
  if (clinicianMatchesDemoOffer) {
    focusOfferFromAlert(getOfferIdFromQuery());
  }
}

async function login(email, password) {
  const data = await api("/api/clinicians/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  showApp();
  await refreshDashboard();
  showToast("Signed in");
}

async function apply(formData) {
  const data = await api("/api/clinicians/apply", {
    method: "POST",
    body: JSON.stringify(formData),
  });
  showToast(data.message || "Application submitted");
  setAuthTab("login");
  document.getElementById("login-email").value = formData.email;
}

async function bootstrap() {
  await registerPortalServiceWorker();
  initApplyForm().catch(() => {});
  await loadDemoHint();
  if (!getToken()) return;
  try {
    showApp();
    await refreshDashboard();
  } catch {
    setToken("");
    showGate();
  }
}

els.tabLogin.addEventListener("click", () => setAuthTab("login"));
els.tabApply.addEventListener("click", () => setAuthTab("apply"));
document.getElementById("apply-state")?.addEventListener("change", refreshApplyCredentialOptions);
document.getElementById("apply-credential")?.addEventListener("change", refreshNpiField);

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.gateError.classList.add("hidden");
  try {
    await login(
      document.getElementById("login-email").value.trim(),
      document.getElementById("login-password").value,
    );
  } catch (error) {
    els.gateError.textContent = error.message;
    els.gateError.classList.remove("hidden");
  }
});

els.applyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.gateError.classList.add("hidden");
  try {
    await apply({
      full_name: document.getElementById("apply-name").value.trim(),
      email: document.getElementById("apply-email").value.trim(),
      phone_number: document.getElementById("apply-phone").value.trim(),
      credential_type: document.getElementById("apply-credential").value,
      npi_number: document.getElementById("apply-npi").value.trim() || null,
      md_license_number: document.getElementById("apply-license").value.trim(),
      state: document.getElementById("apply-state").value,
      min_hourly_rate: Number(document.getElementById("apply-rate").value),
      password: document.getElementById("apply-password").value,
    });
  } catch (error) {
    els.gateError.textContent = error.message;
    els.gateError.classList.remove("hidden");
  }
});

els.preferencesForm?.addEventListener("submit", (event) => {
  savePreferences(event).catch((error) => showToast(error.message, true));
});
els.refreshBtn.addEventListener("click", () => refreshDashboard().catch((e) => showToast(e.message, true)));
els.applyShiftFiltersBtn?.addEventListener("click", async () => {
  try {
    await refreshDashboard();
    showToast(`Showing ${showAllOpenShifts ? "all open" : "matched"} shifts`);
  } catch (error) {
    showToast(error.message, true);
  }
});
els.showAllShiftsToggle?.addEventListener("change", async (event) => {
  showAllOpenShifts = Boolean(event.target.checked);
  try {
    await refreshDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadMatchedCalendarBtn?.addEventListener("click", async () => {
  try {
    const filename = showAllOpenShifts ? "offercare-open-shifts.ics" : "offercare-matched-shifts.ics";
    await downloadFile(buildShiftCalendarQuery(), filename);
    showToast("Shift calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadPlacementsCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/calendar.ics", "offercare-placements.ics");
    showToast("Placement calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.enablePushBtn?.addEventListener("click", () => {
  enablePushAlerts().catch((error) => showToast(error.message, true));
});
els.disablePushBtn?.addEventListener("click", () => {
  disablePushAlerts().catch((error) => showToast(error.message, true));
});
els.installAppBtn?.addEventListener("click", () => {
  installPortalApp().catch((error) => showToast(error.message, true));
});
els.installAppTopBtn?.addEventListener("click", () => {
  installPortalApp().catch((error) => showToast(error.message, true));
});
els.dismissInstallBtn?.addEventListener("click", () => hideInstallPrompt(true));
els.logoutBtn.addEventListener("click", () => {
  setToken("");
  els.demoHintMismatchBanner?.classList.add("hidden");
  showGate();
  showToast("Signed out");
});

bootstrap();

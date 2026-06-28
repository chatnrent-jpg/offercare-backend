const STORAGE_KEY = "vettedcare_clinician_token";
const INSTALL_DISMISS_KEY = "vettedcare_install_dismissed";
const PORTAL_VIEWS = ["overview", "shifts", "schedule", "placements"];
const FATIGUE_SOFT_THRESHOLD = 2.5;
const FATIGUE_HARD_THRESHOLD = 4.0;

const els = {
  gate: document.getElementById("gate"),
  app: document.getElementById("app"),
  portalSectionNav: document.getElementById("portal-section-nav"),
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
  downloadPlacementsCalendarBtn: document.getElementById("download-placements-calendar-btn"),
  downloadScheduleCalendarBtn: document.getElementById("download-schedule-calendar-btn"),
  downloadUnifiedCalendarBtn: document.getElementById("download-unified-calendar-btn"),
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
  dashboardAlert: document.getElementById("dashboard-alert"),
  blockForm: document.getElementById("block-form"),
  scheduleStats: document.getElementById("schedule-stats"),
  scheduleTable: document.getElementById("schedule-table"),
  fatigueBanner: document.getElementById("fatigue-banner"),
  shiftsAlert: document.getElementById("shifts-alert"),
  lockableOnlyToggle: document.getElementById("lockable-only-toggle"),
};

let openShiftsEnriched = false;
let showLockableOnly = false;

let activePushEndpoint = null;
let deferredInstallPrompt = null;
let careTaxonomy = null;
let activeView = "overview";

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
    hint.textContent = gnaStates.has(state)
      ? "Maryland and DC license GNA as a distinct credential."
      : "GNA is not licensed in this state — select CNA for skilled nursing shifts.";
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
    showToast("VettedCare installed");
    return;
  }
  showToast("Use your browser menu to add VettedCare to your home screen");
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

const API_TIMEOUT_MS = 20000;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(path, { ...options, headers, cache: "no-store", signal: controller.signal });
  } catch (error) {
    if (error?.name === "AbortError") {
      const timeoutError = new Error("Request timed out");
      timeoutError.name = "AbortError";
      throw timeoutError;
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    error.status = response.status;
    throw error;
  }
  return data;
}

function isAuthError(error) {
  if (!error) return false;
  if (error.status === 401) return true;
  const msg = String(error.message || "").toLowerCase();
  return ["not_authenticated", "invalid_token", "expired", "unauthorized"].some((token) =>
    msg.includes(token),
  );
}

function clearSessionAndShowGate(message) {
  setToken("");
  els.demoHintMismatchBanner?.classList.add("hidden");
  showDashboardAlert("");
  showGate();
  if (message && els.gateError) {
    els.gateError.textContent = message;
    els.gateError.classList.remove("hidden");
  }
}

function badge(status) {
  const token = String(status || "").toUpperCase();
  let cls = "pending";
  if (["VERIFIED", "SUBMITTED", "LOCKED", "BROADCASTING", "OPEN", "CLEAR"].includes(token)) cls = "ok";
  if (["REJECTED", "FAILED", "EXPIRED", "BLOCKED"].includes(token)) cls = "fail";
  return `<span class="badge ${cls}">${token.replace(/_/g, " ")}</span>`;
}

function fmtShiftTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fmtUtc(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
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

function setPortalView(view) {
  const safe = PORTAL_VIEWS.includes(view) ? view : "overview";
  activeView = safe;
  PORTAL_VIEWS.forEach((id) => {
    document.getElementById(`view-${id}`)?.classList.toggle("hidden", id !== safe);
  });
  els.portalSectionNav?.querySelectorAll(".section-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === safe);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (safe === "shifts") {
    refreshShiftsTab().catch(() => {});
  }
}

async function refreshShiftsTab() {
  const rows = await loadShifts();
  renderShifts(rows);
}

function initPortalSectionNav() {
  els.portalSectionNav?.querySelectorAll(".section-tab").forEach((btn) => {
    btn.addEventListener("click", () => setPortalView(btn.dataset.view));
  });
  setPortalView("overview");
}

function renderPushStatus(subscriptions) {
  const enabled = subscriptions.length > 0;
  activePushEndpoint = enabled ? subscriptions[0].endpoint : null;
  els.enablePushBtn?.classList.toggle("hidden", enabled);
  els.disablePushBtn?.classList.toggle("hidden", !enabled);
  if (els.pushStatus) {
    els.pushStatus.textContent = enabled
      ? `${subscriptions.length} device${subscriptions.length === 1 ? "" : "s"} subscribed`
      : "Push alerts not enabled on this device";
  }
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

function showDashboardAlert(message, isError = true) {
  const el = els.dashboardAlert;
  if (!el) return;
  if (!message) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
}

function showGate() {
  els.gate?.classList.remove("hidden");
  els.app?.classList.add("hidden");
}

function showApp() {
  els.gate?.classList.add("hidden");
  els.app?.classList.remove("hidden");
}

function setAuthTab(mode) {
  const login = mode === "login";
  els.tabLogin?.classList.toggle("active", login);
  els.tabApply?.classList.toggle("active", !login);
  els.loginForm?.classList.toggle("hidden", !login);
  els.applyForm?.classList.toggle("hidden", login);
  els.gateError?.classList.add("hidden");
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
  if (!checked.length) throw new Error("Select at least one care setting.");
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

function renderFatigueBanner(provider) {
  const el = els.fatigueBanner;
  if (!el) return;
  const score = Number(provider?.fatigue_score ?? 0);
  if (score >= FATIGUE_HARD_THRESHOLD) {
    el.className = "fatigue-banner fatigue-hard";
    el.innerHTML = `<strong>Fatigue cap reached (${score.toFixed(2)})</strong>
      <p class="muted">New shift locks may be blocked until you rest. Contact dispatch if urgent.</p>`;
    el.classList.remove("hidden");
    return;
  }
  if (score >= FATIGUE_SOFT_THRESHOLD) {
    el.className = "fatigue-banner fatigue-soft";
    el.innerHTML = `<strong>Elevated fatigue (${score.toFixed(2)})</strong>
      <p class="muted">You can still accept shifts, but consider rest before taking more.</p>`;
    el.classList.remove("hidden");
    return;
  }
  el.classList.add("hidden");
  el.innerHTML = "";
}

function renderStats(provider, placements, shifts) {
  if (!els.stats) return;
  const shiftLabel = "Open shifts";
  els.stats.innerHTML = `
    <div class="stat-card"><span class="muted">License</span>${badge(provider.license_status)}</div>
    <div class="stat-card"><span class="muted">Credential</span><strong>${provider.credential_type || "RN"}</strong></div>
    <div class="stat-card"><span class="muted">Min rate</span><strong>$${Number(provider.min_hourly_rate).toFixed(2)}/hr</strong></div>
    <div class="stat-card"><span class="muted">Response H</span><strong>${fmtPct(provider.response_propensity)}</strong></div>
    <div class="stat-card"><span class="muted">Fatigue T</span><strong>${Number(provider.fatigue_score).toFixed(2)}</strong></div>
    <div class="stat-card"><span class="muted">Placements</span><strong>${placements.length}</strong></div>
    <div class="stat-card"><span class="muted">${shiftLabel}</span><strong>${shifts.length}</strong></div>`;
}

function safetyBadge(status) {
  const key = String(status || "ACTION_NEEDED").toUpperCase();
  const cls =
    key === "CLEAR" ? "ok" : key === "EXPIRING" ? "pending" : key === "BLOCKED" ? "fail" : "pending";
  return `<span class="badge ${cls}">${key.replace(/_/g, " ")}</span>`;
}

function renderStatus(application, safety) {
  if (!els.statusCard) return;
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
    <p class="muted">License ${provider.md_license_number} · NPI ${provider.npi_number || "—"}</p>
    <p class="muted">Portal ${application.portal_enabled ? "enabled" : "disabled"} · License status ${provider.license_status}</p>`;
  if (!els.historyList) return;
  const history = application.verification_history || [];
  if (!history.length) {
    els.historyList.innerHTML = `<p class="empty">No verification events yet.</p>`;
    return;
  }
  els.historyList.innerHTML = history
    .map(
      (row) => `
    <div class="history-item">
      <strong>${row.event_type}</strong>
      <span class="muted">${row.check_result || ""}${row.notes ? ` — ${row.notes}` : ""}</span>
    </div>`,
    )
    .join("");
}

function buildShiftQueryParams(options = {}) {
  const includeLockableOnly = options.includeLockableOnly !== false;
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
  if (includeLockableOnly && showLockableOnly && getToken()) params.set("lockable_only", "true");
  return params.toString();
}

function enrichMatchedShiftRow(row) {
  return {
    ...row,
    lock_eligible: true,
    lock_preview: "Ready to lock",
    rate_delta: row.rate_delta ?? null,
    vault_review_recommended: false,
  };
}

function mergeOpenShiftsWithMatched(openRows, matchedRows) {
  const matchedById = new Map(matchedRows.map((row) => [String(row.offer_id), row]));
  return openRows.map((row) => {
    const matched = matchedById.get(String(row.offer_id));
    const broadcasting = String(row.compliance_lock_status || "").toUpperCase() === "BROADCASTING";
    if (!matched || !broadcasting) {
      return {
        ...row,
        lock_eligible: false,
        lock_preview: row.lock_preview ?? null,
        rate_delta: matched?.rate_delta ?? null,
        vault_review_recommended: false,
      };
    }
    return enrichMatchedShiftRow({ ...row, rate_delta: matched.rate_delta });
  }).sort((a, b) => {
    if (a.lock_eligible !== b.lock_eligible) return a.lock_eligible ? -1 : 1;
    return (Number(b.rate_delta) || -1) - (Number(a.rate_delta) || -1);
  });
}

function buildShiftQuery() {
  const base = getToken() ? "/api/clinicians/me/open-shifts" : "/api/shifts/open";
  return `${base}?${buildShiftQueryParams()}`;
}

function buildShiftCalendarQuery() {
  return `/api/shifts/open/calendar.ics?${buildShiftQueryParams()}`;
}

function showShiftsAlert(message, isError = false) {
  const el = els.shiftsAlert;
  if (!el) return;
  if (!message) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
}

async function enrichOpenShiftsWithMatched(openRows, query) {
  try {
    const matched = await api(`/api/clinicians/me/matched-shifts?${query}`);
    if (!matched.length || activeView !== "shifts") return;
    openShiftsEnriched = true;
    renderShifts(mergeOpenShiftsWithMatched(openRows, matched));
  } catch {
    // Keep the open-shift list visible even if matched enrichment fails or times out.
  }
}

function mapBasicOpenShiftRow(row) {
  return {
    ...row,
    lock_eligible: false,
    lock_preview: null,
    rate_delta: null,
    vault_review_recommended: false,
  };
}

async function loadShifts() {
  const baseQuery = buildShiftQueryParams({ includeLockableOnly: false });

  if (showLockableOnly && getToken()) {
    try {
      const matched = await api(`/api/clinicians/me/matched-shifts?${baseQuery}`);
      openShiftsEnriched = true;
      const rows = matched.map(enrichMatchedShiftRow);
      showShiftsAlert(
        rows.length
          ? ""
          : "No lockable shifts right now. Uncheck Lockable only to browse all open shifts.",
      );
      return rows;
    } catch (error) {
      const msg = error.name === "AbortError" ? "Lockable shifts request timed out." : error.message;
      showShiftsAlert(msg, true);
      return [];
    }
  }

  try {
    const openRows = await api(`/api/shifts/open?${baseQuery}`);
    openShiftsEnriched = Boolean(getToken());
    showShiftsAlert(
      openRows.length ? "" : "No open shifts are broadcasting right now. Try Admin demo setup or clear filters.",
    );
    if (getToken() && openRows.length) {
      enrichOpenShiftsWithMatched(openRows, baseQuery);
    }
    return openRows.map(mapBasicOpenShiftRow);
  } catch (error) {
    const msg = error.name === "AbortError" ? "Open shifts request timed out. Tap Refresh to retry." : error.message;
    showShiftsAlert(msg, true);
    return [];
  }
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
      (options.facility_types || [])
        .map((row) => `<option value="${row}">${row.replaceAll("_", " ")}</option>`)
        .join("");
    els.shiftFacilityTypeFilter.value = facilityTypeValue;
  }
  if (els.shiftRoleFilter) {
    els.shiftRoleFilter.innerHTML =
      `<option value="">All roles</option>` +
      (options.shift_roles || []).map((row) => `<option value="${row}">${row}</option>`).join("");
    els.shiftRoleFilter.value = roleValue;
  }
}

function renderLockCell(row) {
  if (row.lock_eligible) {
    return `<button class="btn ghost lock-shift-btn" type="button" data-offer-id="${row.offer_id}">Lock</button>`;
  }
  const parts = [];
  if (row.lock_preview) {
    parts.push(`<span class="lock-preview">${row.lock_preview}</span>`);
  }
  if (row.vault_review_recommended) {
    parts.push(
      `<button type="button" class="btn text lock-vault-btn" data-offer-id="${row.offer_id}">Review schedule</button>`,
    );
  }
  return parts.join("") || `<span class="lock-preview muted">—</span>`;
}

function renderShifts(rows) {
  if (!els.shiftsTable) return;
  if (!rows.length) {
    const emptyCopy = showLockableOnly
      ? "No lockable shifts right now. Uncheck Lockable only above to browse all open shifts."
      : "No open shifts in your selected filters right now.";
    els.shiftsTable.innerHTML = `<p class="empty">${emptyCopy}</p>`;
    return;
  }
  const showLockColumn = Boolean(getToken());
  els.shiftsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Setting</th><th>State</th><th>County</th><th>Role</th><th>Starts</th><th>Pay</th>${showLockColumn ? "<th>+$ vs min</th>" : ""}<th>Status</th>${showLockColumn ? "<th></th>" : ""}</tr></thead>
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr data-offer-id="${row.offer_id}">
            <td>${row.facility_name}</td>
            <td>${row.facility_type_label || row.facility_type || ""}</td>
            <td>${row.state || "MD"}</td>
            <td>${row.county}</td>
            <td>${row.shift_role_label || row.shift_role}</td>
            <td>${fmtShiftTime(row.shift_starts_at)}</td>
            <td>$${Number(row.hourly_pay_rate).toFixed(2)}/hr</td>
            ${showLockColumn ? `<td>${row.rate_delta != null ? `$${Number(row.rate_delta).toFixed(2)}` : "—"}</td>` : ""}
            <td>${badge(row.compliance_lock_status)}</td>
            ${showLockColumn ? `<td class="lock-cell">${renderLockCell(row)}</td>` : ""}
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
  if (showLockColumn) {
    els.shiftsTable.querySelectorAll(".lock-shift-btn").forEach((button) => {
      button.addEventListener("click", () => lockMatchedShift(button.dataset.offerId));
    });
    els.shiftsTable.querySelectorAll(".lock-vault-btn").forEach((button) => {
      button.addEventListener("click", () => setPortalView("schedule"));
    });
  }
}

function showLockError(offerId, message) {
  const row = els.shiftsTable?.querySelector(`tr[data-offer-id="${offerId}"]`);
  if (!row) return;
  let el = row.querySelector(".lock-error");
  const copy = /fatigue|schedule conflict/i.test(message)
    ? `${message} Open My schedule to adjust blocks.`
    : message;
  if (!el) {
    el = document.createElement("p");
    el.className = "lock-error";
    row.querySelector(".lock-cell")?.appendChild(el);
  }
  el.textContent = copy;
}

function clearLockError(offerId) {
  els.shiftsTable?.querySelector(`tr[data-offer-id="${offerId}"] .lock-error`)?.remove();
}

async function lockMatchedShift(offerId) {
  clearLockError(offerId);
  try {
    const data = await api(`/api/clinicians/me/matched-shifts/${offerId}/lock`, { method: "POST" });
    showToast(data.message || "Shift locked — see Placements and My schedule.");
    setPortalView("placements");
    await refreshDashboard();
  } catch (error) {
    showLockError(offerId, error.message);
    showToast(error.message, true);
  }
}

function renderPlacements(rows) {
  if (!els.placementsTable) return;
  if (!rows.length) {
    els.placementsTable.innerHTML = `<p class="empty">No locked shifts yet. Lock a matched shift above or reply YES to an SMS alert.</p>`;
    return;
  }
  els.placementsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Unit</th><th>Starts</th><th>Rate</th><th>VMS</th></tr></thead>
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.clinical_unit}</td>
            <td>${fmtShiftTime(row.shift_starts_at)}</td>
            <td>$${Number(row.hourly_bill_rate).toFixed(2)}/hr</td>
            <td>${badge(row.vms_submission_status)} ${row.vms_external_ref ? `<br><span class="muted">${row.vms_external_ref}</span>` : ""}</td>
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderSchedule(data) {
  const rows = data?.events || [];
  if (els.scheduleStats) {
    els.scheduleStats.innerHTML = `<div class="stat-card"><span class="muted">Upcoming</span><strong>${data?.total ?? rows.length}</strong></div>`;
  }
  if (!els.scheduleTable) return;
  if (!rows.length) {
    els.scheduleTable.innerHTML = `<p class="empty">No schedule events yet.</p>`;
    return;
  }
  els.scheduleTable.innerHTML = `
    <table>
      <thead><tr><th>Type</th><th>Facility</th><th>Start</th><th>End</th><th></th></tr></thead>
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr>
            <td>${badge(row.event_type)}</td>
            <td>${row.facility_name || "—"}</td>
            <td>${fmtUtc(row.start_time)}</td>
            <td>${fmtUtc(row.end_time)}</td>
            <td>${["BLACKOUT_UNAVAILABLE", "SOFT_BLOCK_PREFERENCE"].includes(row.event_type) ? `<button class="btn ghost del-block-btn" type="button" data-event-id="${row.event_id}">Remove</button>` : ""}</td>
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
  els.scheduleTable.querySelectorAll(".del-block-btn").forEach((button) => {
    button.addEventListener("click", () => deleteScheduleBlock(button.dataset.eventId));
  });
}

async function deleteScheduleBlock(eventId) {
  try {
    await api(`/api/clinicians/me/schedule/blocks/${encodeURIComponent(eventId)}`, { method: "DELETE" });
    showToast("Block removed");
    await refreshDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function addScheduleBlock(event) {
  event.preventDefault();
  const start = document.getElementById("block-start")?.value;
  const end = document.getElementById("block-end")?.value;
  if (!start || !end) {
    showToast("Start and end required.", true);
    return;
  }
  const startIso = new Date(`${start}:00Z`).toISOString();
  const endIso = new Date(`${end}:00Z`).toISOString();
  if (new Date(endIso) <= new Date(startIso)) {
    showToast("End must be after start.", true);
    return;
  }
  try {
    await api("/api/clinicians/me/schedule/blocks", {
      method: "POST",
      body: JSON.stringify({
        event_type: document.getElementById("block-type")?.value,
        start_time: startIso,
        end_time: endIso,
      }),
    });
    els.blockForm?.reset();
    showToast("Block added");
    await refreshDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
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
  if (!offerId) return;
  setPortalView("shifts");
  const lockButton = els.shiftsTable?.querySelector(`.lock-shift-btn[data-offer-id="${offerId}"]`);
  const row = lockButton?.closest("tr");
  if (!row) return;
  row.classList.add("shift-highlight");
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  showToast("Matched shift from your alert — tap Lock to accept.");
  clearOfferQueryParam();
}

async function refreshDashboard() {
  showDashboardAlert("");
  let application;
  try {
    application = await api("/api/clinicians/me/application");
  } catch (error) {
    if (isAuthError(error)) {
      clearSessionAndShowGate("Your session expired. Please sign in again.");
      return false;
    }
    showDashboardAlert(`Could not load your profile: ${error.message}`);
    throw error;
  }

  try {
    const [placements, shiftFilters, shifts, preferences, safety, schedule] = await Promise.all([
      api("/api/clinicians/me/placements").catch(() => []),
      api("/api/shifts/filters").catch(() => ({})),
      loadShifts().catch(() => []),
      loadPreferences().catch(() => ({})),
      api("/api/clinicians/me/safety").catch(() => null),
      api("/api/clinicians/me/schedule").catch(() => ({ total: 0, events: [] })),
    ]);

    populateShiftFilters(shiftFilters);
    const provider = application.provider;
    if (els.welcomeName) els.welcomeName.textContent = provider.full_name || "Welcome";
    renderFatigueBanner(provider);
    renderPreferencesForm(preferences);
    renderStats(provider, placements, shifts);
    renderStatus(application, safety);
    renderShifts(shifts);
    renderPlacements(placements);
    renderSchedule(schedule);
    await refreshPushStatus().catch(() => {});

    const clinicianMatchesDemoOffer = await refreshDemoHintMismatch(provider).catch(() => true);
    if (clinicianMatchesDemoOffer) {
      focusOfferFromAlert(getOfferIdFromQuery());
    }
  } catch (error) {
    console.error("refreshDashboard render", error);
    showDashboardAlert(
      `Profile loaded, but some sections failed: ${error.message}. Tap Refresh to retry.`,
    );
  }
  return true;
}

async function login(email, password) {
  const data = await api("/api/clinicians/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  showApp();
  setPortalView("overview");
  try {
    await refreshDashboard();
    showToast("Signed in");
  } catch (error) {
    showDashboardAlert(`Signed in, but dashboard data failed to load: ${error.message}`);
    showToast(error.message, true);
  }
}

async function apply(formData) {
  try {
    const data = await api("/api/clinicians/apply", {
      method: "POST",
      body: JSON.stringify(formData),
    });
    showToast(data.message || "Application submitted");
    setAuthTab("login");
    document.getElementById("login-email").value = formData.email;
  } catch (error) {
    if (String(error.message).includes("use_join_landing")) {
      window.location.href = "/join";
      return;
    }
    throw error;
  }
}

async function purgeStalePortalCache() {
  if ("serviceWorker" in navigator) {
    const regs = await navigator.serviceWorker.getRegistrations();
    await Promise.all(regs.map((r) => r.unregister()));
  }
  if ("caches" in window) {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
  }
}

async function bootstrap() {
  await purgeStalePortalCache();
  initPortalSectionNav();
  registerPortalServiceWorker().catch(() => {});
  initApplyForm().catch(() => {});
  loadDemoHint().catch(() => {});
  if (!getToken()) return;
  showApp();
  setPortalView("overview");
  try {
    const loaded = await refreshDashboard();
    if (loaded === false) return;
  } catch (error) {
    if (isAuthError(error)) {
      clearSessionAndShowGate("Your session expired. Please sign in again.");
      return;
    }
    showDashboardAlert(
      `Session restored but dashboard could not load: ${error.message}. Tap Refresh or sign out and back in.`,
    );
  }
}

els.tabLogin?.addEventListener("click", () => setAuthTab("login"));
els.tabApply?.addEventListener("click", () => setAuthTab("apply"));
document.getElementById("apply-state")?.addEventListener("change", refreshApplyCredentialOptions);
document.getElementById("apply-credential")?.addEventListener("change", refreshNpiField);

function loginErrorMessage(detail) {
  const msg = String(detail || "");
  if (msg === "demo_email_requires_local_part") {
    return "Enter the full demo email (not just @offercare.demo). Try nj.snf.cna.a@offercare.demo with password SecretPass1.";
  }
  if (msg === "demo_clinician_not_seeded") {
    return "Demo clinician not found in the database. Ask admin to run full demo setup, then try nj.snf.cna.a@offercare.demo / SecretPass1.";
  }
  if (msg === "invalid_credentials") {
    return "Wrong email or password. Demo: nj.snf.cna.a@offercare.demo / SecretPass1";
  }
  return msg || "Sign in failed.";
}

els.loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.gateError?.classList.add("hidden");
  try {
    await login(
      document.getElementById("login-email").value.trim(),
      document.getElementById("login-password").value,
    );
  } catch (error) {
    els.gateError.textContent = loginErrorMessage(error.message);
    els.gateError.classList.remove("hidden");
  }
});

els.applyForm?.addEventListener("submit", async (event) => {
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
els.blockForm?.addEventListener("submit", (event) => {
  addScheduleBlock(event).catch((error) => showToast(error.message, true));
});
els.refreshBtn?.addEventListener("click", () => refreshDashboard().catch((e) => showToast(e.message, true)));
els.applyShiftFiltersBtn?.addEventListener("click", async () => {
  try {
    await refreshDashboard();
    showToast("Open shifts updated");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.lockableOnlyToggle?.addEventListener("change", async (event) => {
  showLockableOnly = Boolean(event.target.checked);
  try {
    await refreshDashboard();
    showToast(showLockableOnly ? "Showing lockable shifts only" : "Showing all open shifts");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadMatchedCalendarBtn?.addEventListener("click", async () => {
  try {
    const filename = "vettedcare-open-shifts.ics";
    await downloadFile(buildShiftCalendarQuery(), filename);
    showToast("Shift calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadPlacementsCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/calendar.ics", "vettedcare-placements.ics");
    showToast("Placement calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadScheduleCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/schedule/calendar.ics", "vettedcare-schedule.ics");
    showToast("Schedule calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadUnifiedCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/unified/calendar.ics", "vettedcare-full-calendar.ics");
    showToast("Full calendar downloaded");
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
els.logoutBtn?.addEventListener("click", () => {
  setToken("");
  showLockableOnly = false;
  if (els.lockableOnlyToggle) els.lockableOnlyToggle.checked = false;
  els.demoHintMismatchBanner?.classList.add("hidden");
  showGate();
  showToast("Signed out");
});

bootstrap();

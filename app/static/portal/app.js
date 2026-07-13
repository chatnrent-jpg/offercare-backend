const STORAGE_KEY = "vettedme_clinician_token";
const INSTALL_DISMISS_KEY = "vettedme_install_dismissed";
const PAYOUT_TOAST_KEY = "vettedme_notified_payouts";
const PORTAL_VIEWS = ["overview", "shifts", "schedule", "placements", "payments", "alerts"];
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
  portalAedtMount: document.getElementById("portal-aedt-disclosure-mount"),
  aedtConsentStatus: document.getElementById("aedt-consent-status"),
  gateError: document.getElementById("gate-error"),
  welcomeName: document.getElementById("welcome-name"),
  refreshBtn: document.getElementById("refresh-btn"),
  logoutBtn: document.getElementById("logout-btn"),
  stats: document.getElementById("stats"),
  earningsStrip: document.getElementById("earnings-strip"),
  demoToolsPanel: document.getElementById("demo-tools-panel"),
  pipelineStrip: document.getElementById("pipeline-strip"),
  journeyCompleteBanner: document.getElementById("journey-complete-banner"),
  nextShiftDesk: document.getElementById("next-shift-desk"),
  shiftsNextBanner: document.getElementById("shifts-next-banner"),
  activityFeed: document.getElementById("activity-feed"),
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
  placementsVmsSummary: document.getElementById("placements-vms-summary"),
  paymentsTable: document.getElementById("payments-table"),
  paymentsSummary: document.getElementById("payments-summary"),
  alertsFeed: document.getElementById("alerts-feed"),
  alertsSummary: document.getElementById("alerts-summary"),
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
  lockConfirmModal: document.getElementById("lock-confirm-modal"),
  lockConfirmDetails: document.getElementById("lock-confirm-details"),
  lockConfirmMessage: document.getElementById("lock-confirm-message"),
  lockConfirmPipeline: document.getElementById("lock-confirm-pipeline"),
  lockConfirmPlacementsBtn: document.getElementById("lock-confirm-placements-btn"),
  lockConfirmOverviewBtn: document.getElementById("lock-confirm-overview-btn"),
  lockConfirmCloseBtn: document.getElementById("lock-confirm-close-btn"),
  lockPrecheckModal: document.getElementById("lock-precheck-modal"),
  lockPrecheckDetails: document.getElementById("lock-precheck-details"),
  lockPrecheckConfirmBtn: document.getElementById("lock-precheck-confirm-btn"),
  lockPrecheckCancelBtn: document.getElementById("lock-precheck-cancel-btn"),
};

let openShiftsEnriched = false;
let showLockableOnly = false;
let lastOpenShiftRows = [];
let lastProviderProfile = null;
let portalAedtDisclosure = null;
let lastLockedPlacementId = null;
let lastPlacements = [];
let lastActivity = [];
let lastPayments = [];
let lastAlerts = [];
let lastJourneyStatus = null;
let paymentsUsingFallback = false;
let pendingLockOfferId = null;

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
    showToast("VettedMe installed");
    return;
  }
  showToast("Use your browser menu to add VettedMe to your home screen");
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
  if (safe === "payments") {
    refreshPaymentsTab().catch(() => {});
  }
  if (safe === "alerts") {
    refreshAlertsTab().catch(() => {});
  }
}

async function refreshAlertsTab() {
  try {
    const rows = await api("/api/clinicians/me/alerts");
    renderAlerts(rows);
  } catch (error) {
    console.error("alerts load failed", error);
    const missing = error.status === 404 || String(error.message).includes("Not Found");
    if (missing && (lastPlacements.length || lastActivity.length)) {
      renderAlerts(buildAlertsFallbackFromActivity(lastActivity, lastPlacements));
      return;
    }
    renderAlerts([]);
    if (missing) {
      showToast("Alerts API unavailable — restart API and hard refresh.", true);
    }
  }
}

async function refreshPaymentsTab() {
  let provider = lastProviderProfile;
  if (!provider) {
    try {
      provider = await api("/api/clinicians/me");
      lastProviderProfile = provider;
    } catch {
      // keep going with cached profile
    }
  }
  try {
    let rows = await api("/api/clinicians/me/payments");
    paymentsUsingFallback = false;
    rows = await ensureDemoPayoutsFinalized(rows, provider);
    renderPayments(rows, provider);
    lastPayments = rows;
  } catch (error) {
    console.error("payments load failed", error);
    const missing = error.status === 404 || String(error.message).includes("Not Found");
    if (missing) {
      let fallback = buildPaymentsFallbackFromPlacements(lastPlacements);
      fallback = normalizeDemoPayments(fallback, provider);
      if (fallback.length) {
        paymentsUsingFallback = true;
        renderPayments(fallback, provider);
        lastPayments = fallback;
        return;
      }
      renderPayments([]);
      showToast("Payments API unavailable — restart API (start-api.bat) and hard refresh.", true);
      return;
    }
    renderPayments([]);
    showToast(error.message, true);
  }
}

async function refreshShiftsTab() {
  const rows = await loadShifts();
  renderShifts(rows);
  renderShiftsNextBanner(lastJourneyStatus);
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

function isDemoWalkthroughProvider(provider) {
  const email = String(provider?.email || "").trim().toLowerCase();
  if (email.endsWith("@offercare.demo")) return true;
  return Boolean(window.PortalShifts?.isDemoProvider?.(provider));
}

function updateDemoToolsVisibility(provider) {
  if (!els.demoToolsPanel) return;
  if (isDemoWalkthroughProvider(provider)) {
    els.demoToolsPanel.classList.remove("hidden");
  } else {
    els.demoToolsPanel.classList.add("hidden");
  }
}

function initDemoToolsPanel() {
  document.getElementById("demo-autopilot-btn")?.addEventListener("click", () => {
    runDemoAutopilot().catch((err) => showToast(err.message, true));
  });
  document.getElementById("demo-export-journey-btn")?.addEventListener("click", () => {
    downloadJourneyExport().catch((err) => showToast(err.message, true));
  });
}

async function runDemoAutopilot() {
  try {
    const result = await api("/api/clinicians/me/demo-autopilot", { method: "POST", body: "{}" });
    showToast(result.message || "Demo autopilot complete");
    await refreshDashboard();
    return;
  } catch (error) {
    console.error("demo autopilot failed", error);
  }
  try {
    await api("/api/clinicians/me/demo-finalize-payouts", { method: "POST", body: "{}" });
  } catch {
    // stale API — client normalize handles payouts on refresh
  }
  try {
    await api("/api/clinicians/me/demo-shift-bootstrap", { method: "POST", body: "{}" });
  } catch {
    // legacy bootstrap optional
  }
  await refreshDashboard();
  showToast("Demo autopilot complete — dashboard refreshed");
}

async function downloadJourneyExport() {
  try {
    const data = await api("/api/clinicians/me/journey-export");
    downloadTextFile(data.filename, data.export_text);
    showToast("Journey export downloaded");
  } catch (error) {
    console.error("journey export failed", error);
    const lines = [
      "VettedMe.ai — Clinician Journey Export (offline)",
      `Clinician: ${lastProviderProfile?.full_name || "Demo"}`,
      `Phase: ${lastJourneyStatus?.phase_label || "—"}`,
      `Lifetime paid: ${formatPayAmountPlain(lastJourneyStatus?.lifetime_paid_amount || 0)}`,
      `Lockable shifts: ${lastJourneyStatus?.lockable_count ?? 0}`,
      "",
      "Placements:",
      ...(lastPlacements || []).map(
        (row) => `- ${row.facility_name} · ${row.clinical_unit} · VMS ${row.vms_submission_status}`,
      ),
      "",
      "Payments:",
      ...(lastPayments || []).map(
        (row) => `- ${formatPayAmountPlain(row.gross_pay_amount)} · ${row.payout_status}`,
      ),
    ];
    downloadTextFile("vettedme-journey-offline.txt", lines.join("\n"));
    showToast("Journey export downloaded (offline copy)");
  }
}

function renderDemoToolsPanel(provider) {
  updateDemoToolsVisibility(provider);
}

function downloadTextFile(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function buildReceiptFallbackFromPayment(row, provider) {
  const token = String(row.payout_id || "").replace(/-/g, "").slice(0, 8).toUpperCase();
  const receiptId = `VC-PAY-${token}`;
  const clinicianName = provider?.full_name || "Clinician";
  const clinicianEmail = provider?.email || "";
  const text = [
    "VettedMe.ai — Instant Pay Receipt",
    "=".repeat(42),
    `Receipt ID: ${receiptId}`,
    `Clinician: ${clinicianName}`,
    `Email: ${clinicianEmail}`,
    "",
    `Facility: ${row.facility_name || "Shift payout"}`,
    `Role: ${row.shift_role || "—"}`,
    `Shift start: ${row.shift_starts_at ? fmtShiftTime(row.shift_starts_at) : "—"}`,
    "",
    `Gross pay: ${formatPayAmountPlain(row.gross_pay_amount)}`,
    `Status: ${row.payout_status_label || row.payout_status || "PAID"}`,
    `Paid at: ${row.paid_at ? fmtShiftTime(row.paid_at) : "—"}`,
    `Stripe ref: ${row.stripe_payout_id || "—"}`,
    "",
    "Demo dry-run receipt — no live bank transfer.",
  ].join("\n");
  return {
    receipt_filename: `vettedme-receipt-${token.toLowerCase()}.txt`,
    receipt_text: text,
  };
}

async function downloadPaymentReceipt(payoutId) {
  const row = lastPayments.find((item) => String(item.payout_id) === String(payoutId));
  const provider = lastProviderProfile;
  try {
    const data = await api(`/api/clinicians/me/payments/${payoutId}/receipt`);
    downloadTextFile(data.receipt_filename, data.receipt_text);
    showToast("Pay receipt downloaded");
  } catch (error) {
    const receiptRow = row ? normalizeDemoPayments([row], provider)[0] : null;
    if (receiptRow) {
      const fallback = buildReceiptFallbackFromPayment(receiptRow, provider);
      downloadTextFile(fallback.receipt_filename, fallback.receipt_text);
      showToast("Pay receipt downloaded");
      return;
    }
    showToast(error.message || "Could not download receipt", true);
  }
}

function formatPayAmountPlain(amount) {
  return `$${Number(amount || 0).toFixed(2)}`;
}

function buildEarningsFallbackFromPayments(payments) {
  const rows = payments || [];
  let lifetimePaid = 0;
  let pendingPayroll = 0;
  let shiftsPaid = 0;
  let lastPaidAt = null;
  const weekStart = new Date();
  weekStart.setUTCHours(0, 0, 0, 0);
  weekStart.setUTCDate(weekStart.getUTCDate() - ((weekStart.getUTCDay() + 6) % 7));
  let weekPaid = 0;

  for (const row of rows) {
    const gross = Number(row.gross_pay_amount || 0);
    const status = String(row.payout_status || "").toUpperCase();
    if (status === "PAID") {
      lifetimePaid += gross;
      shiftsPaid += 1;
      const paidAt = row.paid_at ? new Date(row.paid_at) : null;
      if (paidAt && !Number.isNaN(paidAt.getTime())) {
        if (paidAt >= weekStart) weekPaid += gross;
        if (!lastPaidAt || paidAt > lastPaidAt) lastPaidAt = paidAt;
      }
    } else if (status === "SUBMITTED" || status === "PROCESSING") {
      pendingPayroll += gross;
    }
  }

  return {
    week_paid_amount: weekPaid,
    lifetime_paid_amount: lifetimePaid,
    pending_payroll_amount: pendingPayroll,
    shifts_paid_count: shiftsPaid,
    last_paid_at: lastPaidAt ? lastPaidAt.toISOString() : null,
    currency: "USD",
  };
}

function renderEarningsSummary(earnings) {
  if (!els.earningsStrip || !earnings) return;
  const hasData =
    Number(earnings.lifetime_paid_amount) > 0 ||
    Number(earnings.pending_payroll_amount) > 0 ||
    Number(earnings.shifts_paid_count) > 0;
  if (!hasData) {
    els.earningsStrip.innerHTML = "";
    return;
  }
  const lastPaid = earnings.last_paid_at ? fmtShiftTime(earnings.last_paid_at) : "—";
  const latestPaid = (lastPayments || []).find(
    (row) => String(row.payout_status).toUpperCase() === "PAID",
  );
  const receiptBtn = latestPaid
    ? `<button type="button" class="btn ghost earnings-receipt-btn" data-payout-id="${latestPaid.payout_id}">Download latest receipt</button>`
    : "";
  els.earningsStrip.innerHTML = `
    <div class="earnings-head">
      <strong>Earnings</strong>
      <div class="earnings-head-actions">
        <span class="muted">Instant pay · ${earnings.currency || "USD"}</span>
        ${receiptBtn}
      </div>
    </div>
    <div class="earnings-grid">
      <div class="earnings-card highlight">
        <span class="muted">This week</span>
        <strong class="pay-amount">${formatPayAmountPlain(earnings.week_paid_amount)}</strong>
      </div>
      <div class="earnings-card">
        <span class="muted">Lifetime paid</span>
        <strong>${formatPayAmountPlain(earnings.lifetime_paid_amount)}</strong>
      </div>
      <div class="earnings-card">
        <span class="muted">Pending payroll</span>
        <strong>${formatPayAmountPlain(earnings.pending_payroll_amount)}</strong>
      </div>
      <div class="earnings-card">
        <span class="muted">Shifts paid</span>
        <strong>${Number(earnings.shifts_paid_count || 0)}</strong>
        <span class="status-meta">Last ${lastPaid}</span>
      </div>
    </div>`;
  els.earningsStrip.querySelector(".earnings-receipt-btn")?.addEventListener("click", (event) => {
    const payoutId = event.currentTarget?.dataset?.payoutId;
    if (payoutId) downloadPaymentReceipt(payoutId).catch((err) => showToast(err.message, true));
  });
}

function notifyInstantPayDeposits(payments) {
  const paidRows = (payments || []).filter(
    (row) => String(row.payout_status).toUpperCase() === "PAID",
  );
  if (!paidRows.length) return;

  let seen = [];
  try {
    seen = JSON.parse(sessionStorage.getItem(PAYOUT_TOAST_KEY) || "[]");
  } catch {
    seen = [];
  }
  const seenSet = new Set(seen.map(String));
  let updated = false;

  for (const row of paidRows) {
    const payoutId = String(row.payout_id);
    if (seenSet.has(payoutId)) continue;
    const amount = formatPayAmountPlain(row.gross_pay_amount);
    const ref = row.stripe_payout_id ? ` · ${row.stripe_payout_id}` : "";
    showToast(`Instant pay ${amount} deposited${ref}`);
    seenSet.add(payoutId);
    updated = true;
  }

  if (updated) {
    sessionStorage.setItem(PAYOUT_TOAST_KEY, JSON.stringify([...seenSet]));
  }
}

function renderStats(provider, placements, shifts, payments = []) {
  if (!els.stats) return;
  const shiftLabel = "Open shifts";
  const paidTotal = payments
    .filter((row) => String(row.payout_status).toUpperCase() === "PAID")
    .reduce((sum, row) => sum + Number(row.gross_pay_amount || 0), 0);
  const paidCard = paidTotal > 0
    ? `<div class="stat-card stat-paid"><span class="muted">Paid out</span><strong>${formatPayAmountPlain(paidTotal)}</strong></div>`
    : "";
  els.stats.innerHTML = `
    <div class="stat-card"><span class="muted">License</span>${badge(provider.license_status)}</div>
    <div class="stat-card"><span class="muted">Credential</span><strong>${provider.credential_type || "RN"}</strong></div>
    <div class="stat-card"><span class="muted">Min rate</span><strong>$${Number(provider.min_hourly_rate).toFixed(2)}/hr</strong></div>
    <div class="stat-card"><span class="muted">Response H</span><strong>${fmtPct(provider.response_propensity)}</strong></div>
    <div class="stat-card"><span class="muted">Fatigue T</span><strong>${Number(provider.fatigue_score).toFixed(2)}</strong></div>
    <div class="stat-card"><span class="muted">Placements</span><strong>${placements.length}</strong></div>
    <div class="stat-card"><span class="muted">${shiftLabel}</span><strong>${shifts.length}</strong></div>
    ${paidCard}`;
}

function renderPipelineStrip(placements, payments) {
  if (!els.pipelineStrip) return;
  const locked = placements.length > 0;
  const vmsDone = placements.some((row) => String(row.vms_submission_status).toUpperCase() === "SUBMITTED");
  const payrollDone = payments.some((row) =>
    ["SUBMITTED", "PROCESSING", "PAID"].includes(String(row.payout_status).toUpperCase()),
  );
  const paidDone = payments.some((row) => String(row.payout_status).toUpperCase() === "PAID");
  const steps = [
    { label: "Locked", done: locked },
    { label: "VMS confirmed", done: vmsDone },
    { label: "Payroll", done: payrollDone },
    { label: "Paid", done: paidDone },
  ];
  els.pipelineStrip.innerHTML = `
    <div class="pipeline-head">
      <strong>Shift → pay pipeline</strong>
      <span class="muted">${paidDone ? "Instant pay complete" : payrollDone ? "Awaiting payout" : vmsDone ? "Payroll queued" : locked ? "Dispatch in progress" : "Lock a shift to begin"}</span>
    </div>
    <ol class="pipeline-steps">
      ${steps
        .map(
          (step, index) => `
        <li class="pipeline-step ${step.done ? "done" : ""}">
          <span class="pipeline-dot" aria-hidden="true">${step.done ? "✓" : index + 1}</span>
          <span class="pipeline-label">${step.label}</span>
        </li>`,
        )
        .join("")}
    </ol>`;
}

function buildActivityFallbackFromPlacementsPayments(placements, payments, shifts = []) {
  const events = [];
  const paymentByPlacement = new Map(
    (payments || []).map((row) => [String(row.placement_id), row]),
  );
  const lockable = (shifts || []).some((row) => row.lock_eligible);
  let hasPaid = false;

  const appendPaymentEvents = (placementId, facility, payout, fallbackAt) => {
    const status = String(payout?.payout_status || "").toUpperCase();
    const payrollAt = payout?.payout_eligible_at || payout?.paid_at || fallbackAt;
    if (["SUBMITTED", "PROCESSING", "PAID"].includes(status)) {
      events.push({
        event_id: `${placementId}:payroll`,
        event_type: "PAYROLL_SUBMITTED",
        label: "Submitted to payroll",
        detail: facility,
        amount: Number(payout.gross_pay_amount || 0),
        occurred_at: payrollAt,
      });
    }
    if (status === "PAID") {
      hasPaid = true;
      events.push({
        event_id: `${placementId}:paid`,
        event_type: "INSTANT_PAYOUT_PAID",
        label: "Instant pay deposited",
        detail: facility,
        amount: Number(payout.gross_pay_amount || 0),
        reference: payout.stripe_payout_id,
        occurred_at: payout.paid_at || payrollAt,
      });
    }
  };

  for (const row of placements || []) {
    const placementId = String(row.placement_id);
    const facility = row.facility_name || "Facility";
    const role = row.clinical_unit || "CNA";
    const lockedAt = row.outbound_payload_timestamp || row.shift_starts_at || row.vms_submitted_at;
    events.push({
      event_id: `${placementId}:locked`,
      event_type: "SHIFT_LOCKED",
      label: "Shift locked",
      detail: `${facility} · ${role}`,
      occurred_at: lockedAt,
    });
    const vmsStatus = String(row.vms_submission_status || "").toUpperCase();
    if (vmsStatus === "SUBMITTED" || vmsStatus === "ESCROW_LOCKED") {
      events.push({
        event_id: `${placementId}:vms`,
        event_type: "VMS_SUBMITTED",
        label: "Confirmed with facility",
        detail: facility,
        reference: row.vms_external_ref,
        occurred_at: row.vms_submitted_at || lockedAt,
      });
    }
    const payout = paymentByPlacement.get(placementId);
    if (payout) appendPaymentEvents(placementId, facility, payout, lockedAt);
  }

  for (const payout of payments || []) {
    const placementId = String(payout.placement_id);
    if (events.some((row) => String(row.event_id).startsWith(`${placementId}:`))) continue;
    appendPaymentEvents(placementId, payout.facility_name || "Shift payout", payout, payout.shift_starts_at);
  }

  if (hasPaid && lockable) {
    events.push({
      event_id: "demo:next-shift",
      event_type: "NEXT_SHIFT_AVAILABLE",
      label: "Next shift available",
      detail: "Open shifts tab — lock your next assignment",
      occurred_at: new Date().toISOString(),
    });
  }

  return events.sort(
    (a, b) => new Date(a.occurred_at || 0).getTime() - new Date(b.occurred_at || 0).getTime(),
  );
}

function activityEventClass(eventType) {
  const key = String(eventType || "").toUpperCase();
  if (key === "INSTANT_PAYOUT_PAID") return "paid";
  if (key === "PAYROLL_SUBMITTED") return "submitted";
  if (key === "VMS_SUBMITTED") return "ok";
  if (key === "NEXT_SHIFT_AVAILABLE") return "next";
  return "locked";
}

function renderActivityFeed(events) {
  if (!els.activityFeed) return;
  if (!events.length) {
    els.activityFeed.innerHTML = `<p class="empty">Lock a shift to start your journey timeline.</p>`;
    return;
  }
  els.activityFeed.innerHTML = `
    <ol class="activity-timeline">
      ${events
        .map(
          (row) => `
        <li class="activity-item ${activityEventClass(row.event_type)}">
          <span class="activity-dot" aria-hidden="true"></span>
          <div class="activity-body">
            <strong>${row.label}</strong>
            ${row.detail ? `<p class="muted">${row.detail}</p>` : ""}
            <div class="activity-meta">
              ${row.amount != null ? `<span class="pay-amount">${formatPayAmountPlain(row.amount)}</span>` : ""}
              ${row.reference ? `<span class="status-meta">${row.reference}</span>` : ""}
              ${row.occurred_at ? `<span class="status-meta">${fmtShiftTime(row.occurred_at)}</span>` : ""}
            </div>
          </div>
        </li>`,
        )
        .join("")}
    </ol>`;
}

function renderJourneyCompleteBanner(placements, payments, shifts) {
  if (!els.journeyCompleteBanner) return;
  const paid = payments.some((row) => String(row.payout_status).toUpperCase() === "PAID");
  const lockable = shifts.some((row) => row.lock_eligible);
  if (!paid || !lockable) {
    els.journeyCompleteBanner.classList.add("hidden");
    els.journeyCompleteBanner.innerHTML = "";
    return;
  }
  const totalPaid = payments
    .filter((row) => String(row.payout_status).toUpperCase() === "PAID")
    .reduce((sum, row) => sum + Number(row.gross_pay_amount || 0), 0);
  els.journeyCompleteBanner.className = "journey-complete-banner";
  els.journeyCompleteBanner.innerHTML = `
    <div>
      <strong>Journey complete — ${formatPayAmountPlain(totalPaid)} deposited</strong>
      <p class="muted">Your next lockable shift is ready. Keep the momentum going.</p>
    </div>
    <button type="button" class="btn primary" id="journey-next-shift-btn">View open shifts</button>`;
  document.getElementById("journey-next-shift-btn")?.addEventListener("click", () => focusNextLockableShift());
}

function buildJourneyStatusFallback(placements, payments, shifts) {
  const paid = (payments || []).filter((row) => String(row.payout_status).toUpperCase() === "PAID");
  const lockable = (shifts || []).filter((row) => row.lock_eligible);
  const lifetimePaid = paid.reduce((sum, row) => sum + Number(row.gross_pay_amount || 0), 0);
  const next = lockable[0]
    ? {
        offer_id: lockable[0].offer_id,
        facility_name: lockable[0].facility_name,
        shift_role: lockable[0].shift_role,
        hourly_pay_rate: lockable[0].hourly_pay_rate,
        shift_starts_at: lockable[0].shift_starts_at,
        shift_ends_at: lockable[0].shift_ends_at,
      }
    : null;
  let phase = "GET_STARTED";
  let nextAction = "Lock a matched shift to begin";
  if (paid.length && lockable.length) {
    phase = "READY_FOR_NEXT_SHIFT";
    nextAction = "Lock your next shift to run the journey again";
  } else if (paid.length) {
    phase = "JOURNEY_COMPLETE";
    nextAction = "Instant pay complete — next shift loading";
  } else if ((placements || []).length) {
    phase = "IN_PROGRESS";
    nextAction = "Complete dispatch and payroll";
  }
  return {
    phase,
    phase_label: phase.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    next_action: nextAction,
    lockable_count: lockable.length,
    paid_shifts_count: paid.length,
    lifetime_paid_amount: lifetimePaid,
    can_repeat_journey: paid.length > 0 && lockable.length > 0,
    next_lockable_shift: next,
  };
}

function renderNextShiftDesk(status) {
  if (!els.nextShiftDesk) return;
  if (!status?.can_repeat_journey || !status.next_lockable_shift) {
    els.nextShiftDesk.classList.add("hidden");
    els.nextShiftDesk.innerHTML = "";
    return;
  }
  const shift = status.next_lockable_shift;
  const rate = Number(shift.hourly_pay_rate || 0);
  els.nextShiftDesk.className = "next-shift-desk";
  els.nextShiftDesk.innerHTML = `
    <div>
      <p class="eyebrow">Next shift desk</p>
      <strong>Ready to run the journey again</strong>
      <p class="muted">${status.next_action}</p>
      <p class="next-shift-preview">
        <span class="role-chip">${shift.shift_role || "CNA"}</span>
        ${shift.facility_name || "Facility"}
        ${rate ? ` · $${rate.toFixed(2)}/hr` : ""}
        ${shift.shift_starts_at ? ` · ${fmtShiftTime(shift.shift_starts_at)}` : ""}
      </p>
    </div>
    <div class="next-shift-desk-actions">
      <button type="button" class="btn primary" id="next-shift-lock-btn">Lock next shift</button>
      <button type="button" class="btn ghost" id="next-shift-browse-btn">Browse open shifts</button>
    </div>`;
  document.getElementById("next-shift-lock-btn")?.addEventListener("click", () => {
    focusNextLockableShift(shift.offer_id);
  });
  document.getElementById("next-shift-browse-btn")?.addEventListener("click", () => setPortalView("shifts"));
}

function renderShiftsNextBanner(status) {
  if (!els.shiftsNextBanner) return;
  if (!status?.can_repeat_journey) {
    els.shiftsNextBanner.classList.add("hidden");
    els.shiftsNextBanner.innerHTML = "";
    return;
  }
  const shift = status.next_lockable_shift;
  els.shiftsNextBanner.className = "shifts-next-banner";
  els.shiftsNextBanner.innerHTML = `
    <strong>Next demo shift ready</strong>
    <p class="muted">${shift?.facility_name || "Lockable shift"} — tap Lock below to start a fresh journey.</p>`;
}

async function focusNextLockableShift(preferredOfferId = null) {
  showLockableOnly = true;
  if (els.lockableOnlyToggle) els.lockableOnlyToggle.checked = true;
  setPortalView("shifts");
  const rows = await loadShifts();
  renderShifts(rows);
  renderShiftsNextBanner(lastJourneyStatus);
  const targetId =
    preferredOfferId ||
    lastJourneyStatus?.next_lockable_shift?.offer_id ||
    rows.find((row) => row.lock_eligible)?.offer_id;
  if (!targetId) {
    showToast("No lockable shift found — try Refresh.", true);
    return;
  }
  const row = els.shiftsTable?.querySelector(`tr[data-offer-id="${targetId}"]`);
  if (row) {
    row.classList.add("shift-highlight");
    row.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  showToast("Next shift ready — tap Lock to begin again.");
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
  const lockableQuery = `${baseQuery}${showLockableOnly ? "&lockable_only=true" : ""}`;

  if (getToken()) {
    try {
      const enriched = await api(`/api/clinicians/me/open-shifts?${lockableQuery}`);
      openShiftsEnriched = true;
      let rows = enriched;
      if (lastProviderProfile && window.PortalShifts?.isDemoProvider(lastProviderProfile)) {
        rows = window.PortalShifts.applyDemoClientLockHints(rows, lastProviderProfile);
      }
      if (showLockableOnly) rows = rows.filter((row) => row.lock_eligible);
      showShiftsAlert(
        rows.length
          ? ""
          : "No lockable shifts right now. Uncheck Lockable only to browse all open shifts.",
      );
      return rows;
    } catch (error) {
      const missing = error.status === 404 || String(error.message).includes("Not Found");
      if (!missing) {
        const msg = error.name === "AbortError" ? "Shifts request timed out." : error.message;
        showShiftsAlert(msg, true);
        return [];
      }
    }
  }

  try {
    const openRows = await api(`/api/shifts/open?${baseQuery}`);
    let rows = openRows.map(mapBasicOpenShiftRow);
    if (getToken()) {
      try {
        const matched = await api(`/api/clinicians/me/matched-shifts?${baseQuery}`);
        rows = mergeOpenShiftsWithMatched(rows, matched);
      } catch {
        // matched-shifts optional on legacy API builds
      }
      if (lastProviderProfile && window.PortalShifts?.isDemoProvider(lastProviderProfile)) {
        rows = window.PortalShifts.applyDemoClientLockHints(rows, lastProviderProfile);
      }
    }
    openShiftsEnriched = Boolean(getToken());
    if (showLockableOnly) rows = rows.filter((row) => row.lock_eligible);
    showShiftsAlert(
      rows.length
        ? ""
        : showLockableOnly
          ? "No lockable shifts right now. Uncheck Lockable only to browse all open shifts."
          : "No open shifts are broadcasting right now. Try Admin demo setup or clear filters.",
    );
    return rows;
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

function opsConsoleBaseUrl() {
  return document.querySelector('meta[name="ops-console-url"]')?.content?.trim() || "http://127.0.0.1:8503";
}

function findShiftRowByOfferId(offerId) {
  return lastOpenShiftRows.find((row) => String(row.offer_id) === String(offerId)) || null;
}

function buildOpsConsoleConflictLink(row, provider) {
  const license = provider?.md_license_number || row?.provider_license || "";
  if (!license) return null;
  const params = new URLSearchParams({ provider_id: license, desk: "calendar" });
  if (row?.shift_starts_at) params.set("shift_start", row.shift_starts_at);
  if (row?.shift_ends_at) params.set("shift_end", row.shift_ends_at);
  return `${opsConsoleBaseUrl().replace(/\/$/, "")}/?${params.toString()}`;
}

function lockConfirmDetailRows(payload, row) {
  const facility = payload?.facility_name || row?.facility_name || "—";
  const role = payload?.shift_role || row?.shift_role_label || row?.shift_role || "—";
  const start = fmtShiftTime(payload?.shift_starts_at || row?.shift_starts_at);
  const end = fmtShiftTime(payload?.shift_ends_at || row?.shift_ends_at);
  const pay = payload?.hourly_pay_rate ?? row?.hourly_pay_rate;
  return [
    ["Facility", facility],
    ["Role", role],
    ["Starts", start],
    ["Ends", end],
    ["Pay", pay != null ? `$${Number(pay).toFixed(2)}/hr` : "—"],
  ];
}

function renderLockHandoffPipeline(steps) {
  if (!els.lockConfirmPipeline) return;
  const rows = Array.isArray(steps) && steps.length
    ? steps
    : [
        { label: "Locked", done: true },
        { label: "VMS confirmed", done: false },
        { label: "Payroll", done: false },
        { label: "Paid", done: false },
      ];
  els.lockConfirmPipeline.innerHTML = `
    <p class="eyebrow">What happens next</p>
    <ol class="pipeline-steps lock-handoff-steps">
      ${rows
        .map(
          (step, index) => `
        <li class="pipeline-step ${step.done ? "done" : ""}">
          <span class="pipeline-dot" aria-hidden="true">${step.done ? "✓" : index + 1}</span>
          <span class="pipeline-label">${step.label}</span>
        </li>`,
        )
        .join("")}
    </ol>`;
}

function showLockConfirmModal(payload, row) {
  if (!els.lockConfirmModal || !els.lockConfirmDetails) return;
  els.lockConfirmDetails.innerHTML = lockConfirmDetailRows(payload, row)
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
  renderLockHandoffPipeline(payload?.journey_steps);
  if (els.lockConfirmMessage) {
    els.lockConfirmMessage.textContent =
      payload?.message || "Placement saved — VMS dispatch and payroll are next.";
  }
  els.lockConfirmModal.classList.remove("hidden");
}

function hideLockConfirmModal() {
  els.lockConfirmModal?.classList.add("hidden");
}

function showLockPrecheckModal(row) {
  if (!els.lockPrecheckModal || !els.lockPrecheckDetails || !row) return;
  pendingLockOfferId = row.offer_id;
  els.lockPrecheckDetails.innerHTML = lockConfirmDetailRows({}, row)
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
  els.lockPrecheckModal.classList.remove("hidden");
}

function hideLockPrecheckModal() {
  pendingLockOfferId = null;
  els.lockPrecheckModal?.classList.add("hidden");
}

function beginLockShift(offerId) {
  clearLockError(offerId);
  const row = findShiftRowByOfferId(offerId);
  if (!row) {
    showToast("Shift row not found — refresh and try again.", true);
    return;
  }
  showLockPrecheckModal(row);
}

function renderShifts(rows) {
  lastOpenShiftRows = rows || [];
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
      button.addEventListener("click", () => beginLockShift(button.dataset.offerId));
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
  const isConflict = /fatigue|schedule conflict/i.test(message);
  const shiftRow = findShiftRowByOfferId(offerId);
  const opsLink = isConflict ? buildOpsConsoleConflictLink(shiftRow, lastProviderProfile) : null;
  const copy = isConflict ? `${message} Open My schedule to adjust blocks.` : message;
  if (!el) {
    el = document.createElement("p");
    el.className = "lock-error";
    row.querySelector(".lock-cell")?.appendChild(el);
  }
  el.replaceChildren();
  el.append(document.createTextNode(copy));
  if (opsLink) {
    el.append(document.createElement("br"));
    const link = document.createElement("a");
    link.className = "ops-conflict-link";
    link.href = opsLink;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open ops conflict desk";
    el.append(link);
  }
}

function clearLockError(offerId) {
  els.shiftsTable?.querySelector(`tr[data-offer-id="${offerId}"] .lock-error`)?.remove();
}

async function lockMatchedShift(offerId) {
  clearLockError(offerId);
  const row = findShiftRowByOfferId(offerId);
  try {
    const data = await api(`/api/clinicians/me/matched-shifts/${offerId}/lock`, { method: "POST" });
    if (!data.journey_steps?.length && window.PortalShifts?.isDemoProvider(lastProviderProfile)) {
      data.journey_steps = [
        { label: "Locked", done: true },
        { label: "VMS confirmed", done: true },
        { label: "Payroll", done: false },
        { label: "Paid", done: false },
      ];
      data.message = `${data.message || "Shift locked."} VMS dispatch confirmed — payroll and instant pay are next.`;
    }
    if (data?.placement_id) lastLockedPlacementId = String(data.placement_id);
    await refreshDashboard();
    showLockConfirmModal(data, row);
    showToast(data?.journey_steps?.[1]?.done ? "Locked — VMS confirmed" : "Shift locked — journey started");
  } catch (error) {
    showLockError(offerId, error.message);
    showToast(error.message, true);
  }
}

function focusLatestPlacement() {
  if (!lastLockedPlacementId || !els.placementsTable) return;
  const row = els.placementsTable.querySelector(`tr[data-placement-id="${lastLockedPlacementId}"]`);
  if (!row) return;
  row.classList.add("placement-highlight");
  row.scrollIntoView({ behavior: "smooth", block: "center" });
}

function statusBadgeClass(status) {
  const key = String(status || "PENDING").toUpperCase();
  if (key === "PAID") return "paid";
  if (key === "SUBMITTED" || key === "ESCROW_LOCKED") return "submitted";
  if (key === "FAILED") return "fail";
  if (key === "PROCESSING") return "processing";
  if (["VERIFIED", "LOCKED", "BROADCASTING", "OPEN", "CLEAR"].includes(key)) return "ok";
  return "pending";
}

function formatPayAmount(amount) {
  return `<span class="pay-amount">$${Number(amount || 0).toFixed(2)}</span>`;
}

function formatHourlyRate(amount) {
  return `<span class="pay-rate">${formatPayAmount(amount)}<span class="pay-rate-suffix">/hr</span></span>`;
}

function renderSummaryChips(container, chips) {
  if (!container) return;
  if (!chips.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `<div class="portal-summary-chips">${chips
    .map((chip) => `<span class="summary-chip ${chip.cls || ""}">${chip.label}</span>`)
    .join("")}</div>`;
}

function vmsStatusBadge(row) {
  const key = String(row?.vms_submission_status || "PENDING").toUpperCase();
  const labels = {
    PENDING: "Queued for VMS dispatch",
    SUBMITTED: "Confirmed with facility",
    FAILED: "Dispatch review needed",
    ESCROW_LOCKED: "Pay escrow locked",
  };
  const label = row?.vms_status_label || labels[key] || key.replace(/_/g, " ");
  const cls = statusBadgeClass(key);
  const ref = row?.vms_external_ref
    ? `<span class="status-meta">Ref ${row.vms_external_ref}</span>`
    : "";
  const submitted = row?.vms_submitted_at
    ? `<span class="status-meta">Dispatched ${fmtShiftTime(row.vms_submitted_at)}</span>`
    : "";
  return `<span class="badge ${cls}">${label}</span>${ref}${submitted}`;
}

function renderPlacements(rows) {
  if (!els.placementsTable) return;
  if (els.placementsVmsSummary) {
    const pending = rows.filter((row) => String(row.vms_submission_status).toUpperCase() === "PENDING").length;
    const submitted = rows.filter((row) => String(row.vms_submission_status).toUpperCase() === "SUBMITTED").length;
    renderSummaryChips(els.placementsVmsSummary, rows.length
      ? [
          { cls: "submitted", label: `${submitted} confirmed` },
          { cls: "pending", label: `${pending} queued` },
        ]
      : []);
  }
  if (!rows.length) {
    els.placementsTable.innerHTML = `<p class="empty">No locked shifts yet. Lock a matched shift above or reply YES to an SMS alert.</p>`;
    return;
  }
  els.placementsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Role</th><th>Starts</th><th>Ends</th><th>Rate</th><th>Dispatch</th><th></th></tr></thead>
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr data-placement-id="${row.placement_id}" class="${String(row.placement_id) === String(lastLockedPlacementId) ? "placement-highlight" : ""}">
            <td>${row.facility_name}</td>
            <td><span class="role-chip">${row.clinical_unit || "—"}</span></td>
            <td>${fmtShiftTime(row.shift_starts_at)}</td>
            <td>${fmtShiftTime(row.shift_ends_at)}</td>
            <td>${formatHourlyRate(row.hourly_bill_rate)}</td>
            <td>${vmsStatusBadge(row)}</td>
            <td class="placement-actions">
              <button class="btn ghost placement-schedule-btn" type="button">My schedule</button>
              ${String(row.vms_submission_status).toUpperCase() === "SUBMITTED" ? `<button class="btn ghost placement-payments-btn" type="button">Instant pay</button>` : ""}
            </td>
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
  els.placementsTable.querySelectorAll(".placement-schedule-btn").forEach((button) => {
    button.addEventListener("click", () => setPortalView("schedule"));
  });
  els.placementsTable.querySelectorAll(".placement-payments-btn").forEach((button) => {
    button.addEventListener("click", () => setPortalView("payments"));
  });
  focusLatestPlacement();
}

function estimateGrossPayFromPlacement(row) {
  const hourly = Number(row?.hourly_bill_rate || 0);
  if (!hourly) return 0;
  const start = row?.shift_starts_at ? new Date(row.shift_starts_at).getTime() : NaN;
  const end = row?.shift_ends_at ? new Date(row.shift_ends_at).getTime() : NaN;
  if (!Number.isNaN(start) && !Number.isNaN(end) && end > start) {
    return Number((((end - start) / 3600000) * hourly).toFixed(2));
  }
  return Number((hourly * 12).toFixed(2));
}

function buildPaymentsFallbackFromPlacements(placements) {
  if (!Array.isArray(placements)) return [];
  return placements
    .filter((row) => String(row.vms_submission_status || "").toUpperCase() === "SUBMITTED")
    .map((row) => {
      const token = String(row.placement_id || "").replace(/-/g, "").slice(0, 8).toUpperCase();
      const paidAt = row.vms_submitted_at || row.shift_starts_at;
      return {
        payout_id: row.placement_id,
        placement_id: row.placement_id,
        facility_name: row.facility_name,
        shift_role: row.clinical_unit,
        shift_starts_at: row.shift_starts_at,
        shift_ends_at: row.shift_ends_at,
        gross_pay_amount: estimateGrossPayFromPlacement(row),
        payout_status: "PAID",
        payout_status_label: "Paid",
        payout_eligible_at: paidAt,
        paid_at: paidAt,
        stripe_payout_id: `DRYRUN-PAY-${token}`,
      };
    });
}

async function ensureDemoPayoutsFinalized(payments, provider = lastProviderProfile) {
  if (!window.PortalShifts?.isDemoProvider(provider)) return payments;
  const hasSubmitted = payments.some((row) =>
    ["SUBMITTED", "PROCESSING"].includes(String(row.payout_status).toUpperCase()),
  );
  const hasPaid = payments.some((row) => String(row.payout_status).toUpperCase() === "PAID");
  if (!hasSubmitted || hasPaid) return normalizeDemoPayments(payments, provider);

  try {
    const result = await api("/api/clinicians/me/demo-finalize-payouts", { method: "POST", body: "{}" });
    if (Array.isArray(result.payments) && result.payments.length) {
      paymentsUsingFallback = false;
      if (Number(result.payouts_completed) > 0) {
        showToast("Instant pay deposited — download your receipt");
      }
      return normalizeDemoPayments(result.payments, provider);
    }
  } catch (error) {
    console.error("demo finalize payouts failed", error);
    try {
      await api("/api/clinicians/me/demo-shift-bootstrap", { method: "POST", body: "{}" });
      const rows = await api("/api/clinicians/me/payments");
      paymentsUsingFallback = false;
      return normalizeDemoPayments(rows, provider);
    } catch (bootstrapError) {
      console.error("demo bootstrap fallback failed", bootstrapError);
    }
  }
  return normalizeDemoPayments(payments, provider);
}

function normalizeDemoPayments(payments, provider = lastProviderProfile) {
  if (!window.PortalShifts?.isDemoProvider(provider) || !Array.isArray(payments)) return payments;
  return payments.map((row) => {
    const status = String(row.payout_status || "").toUpperCase();
    if (status === "PAID") return row;
    if (status !== "SUBMITTED" && status !== "PROCESSING") return row;
    const token = String(row.payout_id || row.placement_id || "")
      .replace(/-/g, "")
      .slice(0, 8)
      .toUpperCase();
    const paidAt = row.paid_at || row.payout_eligible_at || new Date().toISOString();
    return {
      ...row,
      payout_status: "PAID",
      payout_status_label: "Paid",
      paid_at: paidAt,
      stripe_payout_id: row.stripe_payout_id || `DRYRUN-PAY-${token}`,
    };
  });
}

function paymentStatusBadge(row) {
  const key = String(row?.payout_status || "PENDING").toUpperCase();
  const labels = {
    PENDING: "Queued for instant pay",
    SUBMITTED: "Submitted to payroll",
    PROCESSING: "Processing payout",
    PAID: "Paid",
    FAILED: "Payout review needed",
  };
  const label = row?.payout_status_label || labels[key] || key.replace(/_/g, " ");
  const cls = statusBadgeClass(key);
  const eligible = row?.payout_eligible_at
    ? `<span class="status-meta">Eligible ${fmtShiftTime(row.payout_eligible_at)}</span>`
    : "";
  const paid = row?.paid_at ? `<span class="status-meta">Paid ${fmtShiftTime(row.paid_at)}</span>` : "";
  const stripe = row?.stripe_payout_id ? `<span class="status-meta">${row.stripe_payout_id}</span>` : "";
  return `<span class="badge ${cls}">${label}</span>${eligible}${paid}${stripe}`;
}

function renderPayments(rows, provider = lastProviderProfile) {
  if (!els.paymentsTable) return;
  const demoProvider = window.PortalShifts?.isDemoProvider(provider);
  if (els.paymentsSummary) {
    const submitted = rows.filter((row) => String(row.payout_status).toUpperCase() === "SUBMITTED").length;
    const paid = rows.filter((row) => String(row.payout_status).toUpperCase() === "PAID").length;
    const chips = [];
    if (paymentsUsingFallback) {
      chips.push({ cls: "fallback", label: "Demo payroll from placements" });
    }
    if (rows.length) {
      chips.push({ cls: "submitted", label: `${submitted} submitted` });
      chips.push({ cls: "paid", label: `${paid} paid` });
      if (paid > 0) {
        chips.push({ cls: "paid", label: "Receipt ready" });
      } else {
        chips.push({ cls: "pending", label: "30-min instant pay window" });
      }
    }
    renderSummaryChips(els.paymentsSummary, chips);
  }
  if (!rows.length) {
    els.paymentsTable.innerHTML = `<p class="empty">No payroll entries yet. Open Placements — confirmed shifts appear here after supervisor sign-off.</p>`;
    return;
  }
  els.paymentsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Role</th><th>Shift</th><th>Gross pay</th><th>Status</th><th></th></tr></thead>
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr data-payout-id="${row.payout_id}" class="${String(row.payout_status).toUpperCase() === "PAID" ? "payment-paid-row" : ""}">
            <td>${row.facility_name}</td>
            <td><span class="role-chip">${row.shift_role || "—"}</span></td>
            <td>${fmtShiftTime(row.shift_starts_at)}</td>
            <td class="pay-cell ${String(row.payout_status).toUpperCase() === "PAID" ? "paid" : ""}">${formatPayAmount(row.gross_pay_amount)}</td>
            <td>${paymentStatusBadge(row)}</td>
            <td class="payment-actions">
              ${String(row.payout_status).toUpperCase() === "PAID" || demoProvider ? `<button type="button" class="btn ghost payment-receipt-btn" data-payout-id="${row.payout_id}">Receipt</button>` : ""}
            </td>
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
  els.paymentsTable.querySelectorAll(".payment-receipt-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const payoutId = button.dataset.payoutId;
      if (payoutId) downloadPaymentReceipt(payoutId).catch((err) => showToast(err.message, true));
    });
  });
}

const ALERT_CHANNEL_LABELS = { SMS: "SMS", PUSH: "Push", PORTAL: "Portal", EMAIL: "Email" };

function alertChannelClass(channel) {
  const key = String(channel || "PORTAL").toUpperCase();
  if (key === "SMS") return "sms";
  if (key === "PUSH") return "push";
  if (key === "EMAIL") return "email";
  return "portal";
}

function buildAlertsFallbackFromActivity(activity, placements = []) {
  const alerts = [];
  if (placements.length) {
    const row = placements[0];
    const rate = Number(row.hourly_bill_rate || 0);
    alerts.push({
      alert_id: `${row.placement_id}:match`,
      alert_type: "SHIFT_MATCH",
      channel: "SMS",
      title: "Matched shift alert",
      body: `VettedMe: ${row.clinical_unit || "CNA"} at ${row.facility_name}${rate ? ` · $${rate.toFixed(2)}/hr` : ""} — reply YES or lock in portal.`,
      reference: row.offer_id,
      sent_at: row.outbound_payload_timestamp || row.shift_starts_at,
      status: "DELIVERED",
    });
  }
  const channelMap = {
    SHIFT_LOCKED: "PORTAL",
    VMS_SUBMITTED: "SMS",
    PAYROLL_SUBMITTED: "PORTAL",
    INSTANT_PAYOUT_PAID: "PUSH",
    NEXT_SHIFT_AVAILABLE: "PUSH",
  };
  for (const event of activity || []) {
    alerts.push({
      alert_id: `alert:${event.event_id}`,
      alert_type: event.event_type,
      channel: channelMap[event.event_type] || "PORTAL",
      title: event.label,
      body: event.detail,
      reference: event.reference,
      amount: event.amount,
      sent_at: event.occurred_at,
      status: "DELIVERED",
    });
  }
  return alerts.sort(
    (a, b) => new Date(b.sent_at || 0).getTime() - new Date(a.sent_at || 0).getTime(),
  );
}

function renderAlerts(rows) {
  if (!els.alertsFeed) return;
  lastAlerts = rows || [];
  if (els.alertsSummary) {
    const sms = rows.filter((row) => String(row.channel).toUpperCase() === "SMS").length;
    const push = rows.filter((row) => String(row.channel).toUpperCase() === "PUSH").length;
    const portal = rows.filter((row) => String(row.channel).toUpperCase() === "PORTAL").length;
    renderSummaryChips(
      els.alertsSummary,
      rows.length
        ? [
            { cls: "submitted", label: `${sms} SMS` },
            { cls: "paid", label: `${push} push` },
            { cls: "pending", label: `${portal} portal` },
          ]
        : [],
    );
  }
  if (!rows.length) {
    els.alertsFeed.innerHTML = `<p class="empty">No alerts yet. Matched shifts and payout updates appear here.</p>`;
    return;
  }
  els.alertsFeed.innerHTML = rows
    .map(
      (row) => `
    <article class="alert-card ${alertChannelClass(row.channel)}" data-alert-id="${row.alert_id}">
      <div class="alert-card-head">
        <span class="channel-chip ${alertChannelClass(row.channel)}">${ALERT_CHANNEL_LABELS[String(row.channel).toUpperCase()] || row.channel}</span>
        <span class="status-meta">${row.sent_at ? fmtShiftTime(row.sent_at) : ""}</span>
      </div>
      <strong>${row.title}</strong>
      ${row.body ? `<p class="muted">${row.body}</p>` : ""}
      <div class="alert-card-meta">
        ${row.amount != null ? formatPayAmount(row.amount) : ""}
        ${row.reference ? `<span class="status-meta">${row.reference}</span>` : ""}
        <span class="badge ok">${String(row.status || "DELIVERED").replace(/_/g, " ")}</span>
      </div>
    </article>`,
    )
    .join("");
}

function scheduleEventBadge(eventType) {
  const key = String(eventType || "").toUpperCase();
  if (key === "SHIFT_COMMITMENT") return `<span class="badge ok">Locked shift</span>`;
  return badge(key);
}

function renderSchedule(data) {
  const rows = data?.events || [];
  if (els.scheduleStats) {
    const commitments = rows.filter((row) => String(row.event_type).toUpperCase() === "SHIFT_COMMITMENT").length;
    els.scheduleStats.innerHTML = `
      <div class="stat-card"><span class="muted">Upcoming</span><strong>${data?.total ?? rows.length}</strong></div>
      <div class="stat-card"><span class="muted">Locked shifts</span><strong>${commitments}</strong></div>`;
  }
  if (!els.scheduleTable) return;
  if (!rows.length) {
    els.scheduleTable.innerHTML = `<p class="empty">No schedule events yet. Lock a shift to add a commitment here.</p>`;
    return;
  }
  els.scheduleTable.innerHTML = `
    <table>
      <thead><tr><th>Type</th><th>Facility</th><th>Start</th><th>End</th><th></th></tr></thead>
      <tbody>
        ${rows
          .map(
            (row) => `
          <tr class="${String(row.event_type).toUpperCase() === "SHIFT_COMMITMENT" ? "shift-commitment-row" : ""}">
            <td>${scheduleEventBadge(row.event_type)}</td>
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
    const provider = application.provider;
    lastProviderProfile = provider;
    renderAedtConsentStatus(provider.consent_signed_at);
    if (isDemoWalkthroughProvider(provider)) {
      await window.PortalShifts?.bootstrapDemoShifts?.(api).catch(() => {});
    }

    const [placements, shiftFilters, shifts, preferences, safety, schedule] = await Promise.all([
      api("/api/clinicians/me/placements").catch((error) => {
        console.error("placements load failed", error);
        return [];
      }),
      api("/api/shifts/filters").catch(() => ({})),
      loadShifts().catch(() => []),
      loadPreferences().catch(() => ({})),
      api("/api/clinicians/me/safety").catch(() => null),
      api("/api/clinicians/me/schedule").catch(() => ({ total: 0, events: [] })),
    ]);

    let payments = [];
    try {
      payments = await api("/api/clinicians/me/payments");
      paymentsUsingFallback = false;
      payments = await ensureDemoPayoutsFinalized(payments, provider);
    } catch (error) {
      console.error("payments load failed", error);
      const missing = error.status === 404 || String(error.message).includes("Not Found");
      if (missing) {
        payments = normalizeDemoPayments(buildPaymentsFallbackFromPlacements(placements), provider);
        paymentsUsingFallback = payments.length > 0;
      }
    }
    if (payments.length && isDemoWalkthroughProvider(provider)) {
      payments = normalizeDemoPayments(payments, provider);
    }

    let activity = [];
    try {
      activity = await api("/api/clinicians/me/activity");
    } catch (error) {
      console.error("activity load failed", error);
      const missing = error.status === 404 || String(error.message).includes("Not Found");
      if (missing) {
        activity = buildActivityFallbackFromPlacementsPayments(placements, payments, shifts);
      }
    }
    if (!activity.length && (placements.length || payments.length)) {
      activity = buildActivityFallbackFromPlacementsPayments(placements, payments, shifts);
    }

    let earnings = null;
    try {
      earnings = await api("/api/clinicians/me/earnings");
    } catch (error) {
      console.error("earnings load failed", error);
      if (payments.length) earnings = buildEarningsFallbackFromPayments(payments);
    }
    if (!earnings && payments.length) {
      earnings = buildEarningsFallbackFromPayments(payments);
    }

    lastPlacements = placements;
    lastActivity = activity;
    lastPayments = payments;

    let alerts = [];
    try {
      alerts = await api("/api/clinicians/me/alerts");
    } catch (error) {
      console.error("alerts load failed", error);
      if (placements.length || activity.length) {
        alerts = buildAlertsFallbackFromActivity(activity, placements);
      }
    }
    if (!alerts.length && (placements.length || activity.length)) {
      alerts = buildAlertsFallbackFromActivity(activity, placements);
    }

    let journeyStatus = null;
    try {
      journeyStatus = await api("/api/clinicians/me/journey-status");
    } catch (error) {
      console.error("journey status load failed", error);
      journeyStatus = buildJourneyStatusFallback(placements, payments, shifts);
    }
    if (!journeyStatus) {
      journeyStatus = buildJourneyStatusFallback(placements, payments, shifts);
    }
    lastJourneyStatus = journeyStatus;

    populateShiftFilters(shiftFilters);
    if (els.welcomeName) els.welcomeName.textContent = provider.full_name || "Welcome";
    renderFatigueBanner(provider);
    renderPreferencesForm(preferences);
    renderStats(provider, placements, shifts, payments);
    renderEarningsSummary(earnings);
    renderDemoToolsPanel(provider);
    renderPipelineStrip(placements, payments);
    renderJourneyCompleteBanner(placements, payments, shifts);
    renderNextShiftDesk(journeyStatus);
    renderShiftsNextBanner(journeyStatus);
    renderActivityFeed(activity);
    notifyInstantPayDeposits(payments);
    renderStatus(application, safety);
    renderShifts(shifts);
    renderPlacements(placements);
    renderPayments(payments, provider);
    renderAlerts(alerts);
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

async function apply(formData) {
  if (portalAedtDisclosure && !portalAedtDisclosure.validate()) {
    throw new Error("Maryland AEDT disclosure acceptance is required.");
  }
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
  purgeStalePortalCache().catch(() => {});
  initPortalSectionNav();
  initDemoToolsPanel();
  registerPortalServiceWorker().catch(() => {});
  initApplyForm().catch(() => {});
  mountPortalAedtDisclosure();
  loadDemoHint().catch(() => {});

  await PortalAuth.setup(async (loginData) => {
    showApp();
    setPortalView("overview");
    try {
      const loaded = await refreshDashboard();
      if (loaded === false) return;
      showToast(loginData ? "Signed in" : "Welcome back");
    } catch (error) {
      if (isAuthError(error)) {
        clearSessionAndShowGate("Your session expired. Please sign in again.");
        return;
      }
      showDashboardAlert(
        `Signed in, but dashboard could not load: ${error.message}. Tap Refresh or sign out and back in.`,
      );
    }
  });
}

els.tabLogin?.addEventListener("click", () => setAuthTab("login"));
els.tabApply?.addEventListener("click", () => setAuthTab("apply"));
document.getElementById("apply-state")?.addEventListener("change", refreshApplyCredentialOptions);
document.getElementById("apply-credential")?.addEventListener("change", refreshNpiField);

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
    const filename = "vettedme-open-shifts.ics";
    await downloadFile(buildShiftCalendarQuery(), filename);
    showToast("Shift calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadPlacementsCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/calendar.ics", "vettedme-placements.ics");
    showToast("Placement calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadScheduleCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/schedule/calendar.ics", "vettedme-schedule.ics");
    showToast("Schedule calendar downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadUnifiedCalendarBtn?.addEventListener("click", async () => {
  try {
    await downloadFile("/api/clinicians/me/unified/calendar.ics", "vettedme-full-calendar.ics");
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
els.lockConfirmPlacementsBtn?.addEventListener("click", () => {
  hideLockConfirmModal();
  setPortalView("placements");
  focusLatestPlacement();
});
els.lockConfirmOverviewBtn?.addEventListener("click", () => {
  hideLockConfirmModal();
  setPortalView("overview");
});
els.lockConfirmCloseBtn?.addEventListener("click", hideLockConfirmModal);
els.lockPrecheckConfirmBtn?.addEventListener("click", async () => {
  const offerId = pendingLockOfferId;
  hideLockPrecheckModal();
  if (!offerId) return;
  await lockMatchedShift(offerId);
});
els.lockPrecheckCancelBtn?.addEventListener("click", hideLockPrecheckModal);

function renderAedtConsentStatus(signedAtIso) {
  if (!els.aedtConsentStatus || !window.VettedMeAedtDisclosure) return;
  els.aedtConsentStatus.classList.remove("hidden");
  window.VettedMeAedtDisclosure.renderAedtConsentStatus(els.aedtConsentStatus, signedAtIso);
}

function mountPortalAedtDisclosure() {
  if (!els.portalAedtMount || !window.VettedMeAedtDisclosure) return;
  els.portalAedtMount.innerHTML = "";
  portalAedtDisclosure = window.VettedMeAedtDisclosure.createAedtDisclosureBox();
  els.portalAedtMount.appendChild(portalAedtDisclosure.element);
}

els.logoutBtn?.addEventListener("click", () => {
  setToken("");
  showLockableOnly = false;
  if (els.lockableOnlyToggle) els.lockableOnlyToggle.checked = false;
  lastLockedPlacementId = null;
  lastProviderProfile = null;
  portalAedtDisclosure?.reset();
  hideLockConfirmModal();
  hideLockPrecheckModal();
  els.demoHintMismatchBanner?.classList.add("hidden");
  showGate();
  showToast("Signed out");
});

bootstrap();

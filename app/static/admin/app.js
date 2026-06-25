const STORAGE_KEY = "offercare_admin_key";

let lastDemoHealth = null;

const els = {
  gate: document.getElementById("gate"),
  app: document.getElementById("app"),
  apiKeyInput: document.getElementById("api-key-input"),
  connectBtn: document.getElementById("connect-btn"),
  gateError: document.getElementById("gate-error"),
  disconnectBtn: document.getElementById("disconnect-btn"),
  connectionStatus: document.getElementById("connection-status"),
  refreshBtn: document.getElementById("refresh-btn"),
  stats: document.getElementById("stats"),
  vettedTagline: document.getElementById("vetted-tagline"),
  vettedSummary: document.getElementById("vetted-summary"),
  vettedProvidersTable: document.getElementById("vetted-providers-table"),
  vettedAuditTable: document.getElementById("vetted-audit-table"),
  vettedAlertsTable: document.getElementById("vetted-alerts-table"),
  vettedManusHint: document.getElementById("vetted-manus-hint"),
  infraSummary: document.getElementById("infra-summary"),
  infraChecks: document.getElementById("infra-checks"),
  refreshInfraBtn: document.getElementById("refresh-infra-btn"),
  runVettedSafetyBtn: document.getElementById("run-vetted-safety-btn"),
  syncVettedStatusBtn: document.getElementById("sync-vetted-status-btn"),
  refreshVettedBtn: document.getElementById("refresh-vetted-btn"),
  pendingTable: document.getElementById("pending-table"),
  shiftsTable: document.getElementById("shifts-table"),
  placementsTable: document.getElementById("placements-table"),
  opsLog: document.getElementById("ops-log"),
  scrapeBtn: document.getElementById("scrape-btn"),
  scrapePaBtn: document.getElementById("scrape-pa-btn"),
  scrapeDeBtn: document.getElementById("scrape-de-btn"),
  scrapeNjBtn: document.getElementById("scrape-nj-btn"),
  scrapeExpansionBtn: document.getElementById("scrape-expansion-btn"),
  scrapeNursingHomesBtn: document.getElementById("scrape-nursing-homes-btn"),
  scrapeHomeHealthBtn: document.getElementById("scrape-home-health-btn"),
  scrapePostAcuteBtn: document.getElementById("scrape-post-acute-btn"),
  autoShiftsBtn: document.getElementById("auto-shifts-btn"),
  seedMidAtlanticDemosBtn: document.getElementById("seed-mid-atlantic-demos-btn"),
  seedPostAcuteDemosBtn: document.getElementById("seed-post-acute-demos-btn"),
  seedHospitalDemosBtn: document.getElementById("seed-hospital-demos-btn"),
  seedDemoBtn: document.getElementById("seed-demo-btn"),
  seedInovaBtn: document.getElementById("seed-inova-btn"),
  seedVaNursingHomeBtn: document.getElementById("seed-va-nursing-home-btn"),
  seedDcNursingHomeBtn: document.getElementById("seed-dc-nursing-home-btn"),
  seedPaNursingHomeBtn: document.getElementById("seed-pa-nursing-home-btn"),
  seedDeNursingHomeBtn: document.getElementById("seed-de-nursing-home-btn"),
  seedNjNursingHomeBtn: document.getElementById("seed-nj-nursing-home-btn"),
  seedHackensackBtn: document.getElementById("seed-hackensack-btn"),
  seedNursingHomeBtn: document.getElementById("seed-nursing-home-btn"),
  seedHomeHealthBtn: document.getElementById("seed-home-health-btn"),
  demoSummary: document.getElementById("demo-summary"),
  demoHealthBadge: document.getElementById("demo-health-badge"),
  demoDemoGates: document.getElementById("demo-demo-gates"),
  demoOffersTable: document.getElementById("demo-offers-table"),
  demoCliniciansTable: document.getElementById("demo-clinicians-table"),
  demoNextSteps: document.getElementById("demo-next-steps"),
  runDemoSetupBtn: document.getElementById("run-demo-setup-btn"),
  resetDemoBtn: document.getElementById("reset-demo-btn"),
  copyDemoLinksBtn: document.getElementById("copy-demo-links-btn"),
  copyDemoWalkthroughBtn: document.getElementById("copy-demo-walkthrough-btn"),
  downloadDemoWalkthroughBtn: document.getElementById("download-demo-walkthrough-btn"),
  downloadDemoStatusJsonBtn: document.getElementById("download-demo-status-json-btn"),
  downloadDemoStatusCsvBtn: document.getElementById("download-demo-status-csv-btn"),
  downloadDemoGatesJsonBtn: document.getElementById("download-demo-gates-json-btn"),
  downloadDemoGatesTxtBtn: document.getElementById("download-demo-gates-txt-btn"),
  copyDemoGatesBtn: document.getElementById("copy-demo-gates-btn"),
  downloadDemoBundleBtn: document.getElementById("download-demo-bundle-btn"),
  ensureDemoPortalBtn: document.getElementById("ensure-demo-portal-btn"),
  ensureDemoPushBtn: document.getElementById("ensure-demo-push-btn"),
  notifyMatchedDemosBtn: document.getElementById("notify-matched-demos-btn"),
  demoLockSmokeBtn: document.getElementById("demo-lock-smoke-btn"),
  refreshDemoStatusBtn: document.getElementById("refresh-demo-status-btn"),
  submitPendingVmsBtn: document.getElementById("submit-pending-vms-btn"),
  integrationsGrid: document.getElementById("integrations-grid"),
  twilioSmsProductionSummary: document.getElementById("twilio-sms-production-summary"),
  twilioSmsProductionSteps: document.getElementById("twilio-sms-production-steps"),
  testTwilioSmsBtn: document.getElementById("test-twilio-sms-btn"),
  twilioLockReplySmokeBtn: document.getElementById("twilio-lock-reply-smoke-btn"),
  copyTwilioGoLiveEnvBtn: document.getElementById("copy-twilio-go-live-env-btn"),
  liveScrapersGrid: document.getElementById("live-scrapers-grid"),
  probeLiveScrapersBtn: document.getElementById("probe-live-scrapers-btn"),
  copyLiveScrapersEnvBtn: document.getElementById("copy-live-scrapers-env-btn"),
  refreshIntegrationsBtn: document.getElementById("refresh-integrations-btn"),
  deploySummary: document.getElementById("deploy-summary"),
  deployChecklist: document.getElementById("deploy-checklist"),
  deployDemoGates: document.getElementById("deploy-demo-gates"),
  deployExportSteps: document.getElementById("deploy-export-steps"),
  deployTwilioSteps: document.getElementById("deploy-twilio-steps"),
  deployDemoSteps: document.getElementById("deploy-demo-steps"),
  deployMarylandSteps: document.getElementById("deploy-maryland-steps"),
  deployMarylandProductionSummary: document.getElementById("deploy-maryland-production-summary"),
  deployMarylandProductionSteps: document.getElementById("deploy-maryland-production-steps"),
  deployLiveSmsSteps: document.getElementById("deploy-live-sms-steps"),
  deployMarylandLaunchSummary: document.getElementById("deploy-maryland-launch-summary"),
  deployMarylandLaunchSteps: document.getElementById("deploy-maryland-launch-steps"),
  runMarylandLaunchSmokeBtn: document.getElementById("run-maryland-launch-smoke-btn"),
  copyMarylandLaunchEnvBtn: document.getElementById("copy-maryland-launch-env-btn"),
  downloadMarylandLaunchCapstoneBtn: document.getElementById("download-maryland-launch-capstone-btn"),
  copyMarylandProductionEnvBtn: document.getElementById("copy-maryland-production-env-btn"),
  copyDeployLiveSmsEnvBtn: document.getElementById("copy-deploy-live-sms-env-btn"),
  downloadMarylandProductionRunbookBtn: document.getElementById("download-maryland-production-runbook-btn"),
  refreshDeployBtn: document.getElementById("refresh-deploy-btn"),
  downloadDeployChecklistJsonBtn: document.getElementById("download-deploy-checklist-json-btn"),
  downloadDeployChecklistCsvBtn: document.getElementById("download-deploy-checklist-csv-btn"),
  downloadDeployBundleBtn: document.getElementById("download-deploy-bundle-btn"),
  copyDeployGatesBtn: document.getElementById("copy-deploy-gates-btn"),
  downloadDeployGatesTxtBtn: document.getElementById("download-deploy-gates-txt-btn"),
  downloadDeployGatesJsonBtn: document.getElementById("download-deploy-gates-json-btn"),
  relearnScoresBtn: document.getElementById("relearn-scores-btn"),
  sniperTable: document.getElementById("sniper-table"),
  shiftStateFilter: document.getElementById("shift-state-filter"),
  shiftCountyFilter: document.getElementById("shift-county-filter"),
  shiftFacilityTypeFilter: document.getElementById("shift-facility-type-filter"),
  shiftRoleFilter: document.getElementById("shift-role-filter"),
  shiftMinPayFilter: document.getElementById("shift-min-pay-filter"),
  applyShiftFiltersBtn: document.getElementById("apply-shift-filters-btn"),
  opsMetrics: document.getElementById("ops-metrics"),
  productionOpsSummary: document.getElementById("production-ops-summary"),
  productionOpsChecks: document.getElementById("production-ops-checks"),
  productionOpsScraperProbes: document.getElementById("production-ops-scraper-probes"),
  productionOpsSteps: document.getElementById("production-ops-steps"),
  refreshProductionOpsBtn: document.getElementById("refresh-production-ops-btn"),
  downloadProductionOpsDashboardBtn: document.getElementById("download-production-ops-dashboard-btn"),
  productionPerfectionSummary: document.getElementById("production-perfection-summary"),
  productionPerfectionSteps: document.getElementById("production-perfection-steps"),
  runProductionPerfectionCheckBtn: document.getElementById("run-production-perfection-check-btn"),
  copyProductionPerfectionEnvBtn: document.getElementById("copy-production-perfection-env-btn"),
  downloadProductionPerfectionCapstoneBtn: document.getElementById("download-production-perfection-capstone-btn"),
  productionLaunchCeremonySummary: document.getElementById("production-launch-ceremony-summary"),
  productionLaunchCeremonySteps: document.getElementById("production-launch-ceremony-steps"),
  runProductionLaunchCeremonyBtn: document.getElementById("run-production-launch-ceremony-btn"),
  downloadProductionLaunchCeremonyMdBtn: document.getElementById("download-production-launch-ceremony-md-btn"),
  downloadProductionLaunchCeremonyJsonBtn: document.getElementById("download-production-launch-ceremony-json-btn"),
  productionGoLiveRecordSummary: document.getElementById("production-go-live-record-summary"),
  productionGoLiveRecordSteps: document.getElementById("production-go-live-record-steps"),
  sealProductionGoLiveRecordBtn: document.getElementById("seal-production-go-live-record-btn"),
  downloadProductionGoLiveRecordJsonBtn: document.getElementById("download-production-go-live-record-json-btn"),
  productionLaunchAttestationSummary: document.getElementById("production-launch-attestation-summary"),
  productionLaunchAttestationSteps: document.getElementById("production-launch-attestation-steps"),
  attestProductionLaunchBtn: document.getElementById("attest-production-launch-btn"),
  downloadProductionLaunchAttestationMdBtn: document.getElementById("download-production-launch-attestation-md-btn"),
  downloadProductionLaunchAttestationJsonBtn: document.getElementById("download-production-launch-attestation-json-btn"),
  productionLaunchPerfectionSealSummary: document.getElementById("production-launch-perfection-seal-summary"),
  productionLaunchPerfectionSealSteps: document.getElementById("production-launch-perfection-seal-steps"),
  sealProductionLaunchPerfectionBtn: document.getElementById("seal-production-launch-perfection-btn"),
  downloadProductionLaunchPerfectionSealJsonBtn: document.getElementById("download-production-launch-perfection-seal-json-btn"),
  productionLaunchArchiveSummary: document.getElementById("production-launch-archive-summary"),
  productionLaunchArchiveSteps: document.getElementById("production-launch-archive-steps"),
  archiveProductionLaunchBtn: document.getElementById("archive-production-launch-btn"),
  downloadProductionLaunchArchiveJsonBtn: document.getElementById("download-production-launch-archive-json-btn"),
  productionLaunchFinaleSummary: document.getElementById("production-launch-finale-summary"),
  productionLaunchFinaleSteps: document.getElementById("production-launch-finale-steps"),
  runProductionLaunchFinaleBtn: document.getElementById("run-production-launch-finale-btn"),
  downloadProductionLaunchFinaleJsonBtn: document.getElementById("download-production-launch-finale-json-btn"),
  productionLaunchBundleVerificationSummary: document.getElementById("production-launch-bundle-verification-summary"),
  productionLaunchBundleVerificationSteps: document.getElementById("production-launch-bundle-verification-steps"),
  verifyProductionLaunchBundleBtn: document.getElementById("verify-production-launch-bundle-btn"),
  downloadProductionLaunchPerfectionManifestJsonBtn: document.getElementById("download-production-launch-perfection-manifest-json-btn"),
  cascadeWorkerStatus: document.getElementById("cascade-worker-status"),
  staffingSchedulerStatus: document.getElementById("staffing-scheduler-status"),
  complianceSchedulerStatus: document.getElementById("compliance-scheduler-status"),
  cascadeWorkerTickBtn: document.getElementById("cascade-worker-tick-btn"),
  staffingVmsTickBtn: document.getElementById("staffing-vms-tick-btn"),
  staffingJobBoardTickBtn: document.getElementById("staffing-job-board-tick-btn"),
  complianceSchedulerTickBtn: document.getElementById("compliance-scheduler-tick-btn"),
  auditTable: document.getElementById("audit-table"),
  toast: document.getElementById("toast"),
  rankDialog: document.getElementById("rank-dialog"),
  rankBody: document.getElementById("rank-body"),
  closeRankDialog: document.getElementById("close-rank-dialog"),
  scheduleDialog: document.getElementById("schedule-dialog"),
  scheduleDialogMeta: document.getElementById("schedule-dialog-meta"),
  scheduleForm: document.getElementById("schedule-form"),
  scheduleStartInput: document.getElementById("schedule-start-input"),
  scheduleEndInput: document.getElementById("schedule-end-input"),
  closeScheduleDialog: document.getElementById("close-schedule-dialog"),
  complianceSummary: document.getElementById("compliance-summary"),
  complianceFlags: document.getElementById("compliance-flags"),
  complianceCrisisTable: document.getElementById("compliance-crisis-table"),
  complianceJobBoardTable: document.getElementById("compliance-job-board-table"),
  complianceVmsIngestTable: document.getElementById("compliance-vms-ingest-table"),
  complianceProvidersTable: document.getElementById("compliance-providers-table"),
  runComplianceMonitorBtn: document.getElementById("run-compliance-monitor-btn"),
  scanCrisisSignalsBtn: document.getElementById("scan-crisis-signals-btn"),
  scanJobBoardsBtn: document.getElementById("scan-job-boards-btn"),
  ingestVmsShiftsBtn: document.getElementById("ingest-vms-shifts-btn"),
  refreshComplianceBtn: document.getElementById("refresh-compliance-btn"),
  complianceDialog: document.getElementById("compliance-dialog"),
  complianceBody: document.getElementById("compliance-body"),
  closeComplianceDialog: document.getElementById("close-compliance-dialog"),
  outreachTargetsTable: document.getElementById("outreach-targets-table"),
  outreachEmailTable: document.getElementById("outreach-email-table"),
  runOutreachCampaignBtn: document.getElementById("run-outreach-campaign-btn"),
  sendOutreachCampaignBtn: document.getElementById("send-outreach-campaign-btn"),
  refreshOutreachBtn: document.getElementById("refresh-outreach-btn"),
  workerInflowSummary: document.getElementById("worker-inflow-summary"),
  workerInflowPlaybook: document.getElementById("worker-inflow-playbook"),
  workerInflowJoinLink: document.getElementById("worker-inflow-join-link"),
  copyWorkerInflowLinkBtn: document.getElementById("copy-worker-inflow-link-btn"),
  refreshWorkerInflowBtn: document.getElementById("refresh-worker-inflow-btn"),
};

function getKey() {
  if (typeof window.offercareAdminGetKey === "function") {
    return window.offercareAdminGetKey();
  }
  return localStorage.getItem(STORAGE_KEY) || "";
}

function setKey(value) {
  if (typeof window.offercareAdminSetKey === "function") {
    window.offercareAdminSetKey(value);
    return;
  }
  if (value) localStorage.setItem(STORAGE_KEY, value);
  else localStorage.removeItem(STORAGE_KEY);
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.style.borderColor = isError ? "#7f1d1d" : "#243049";
  els.toast.classList.remove("hidden");
  window.clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => els.toast.classList.add("hidden"), 3500);
}

async function api(path, options = {}) {
  const headers = {
    "X-Admin-Key": getKey(),
    ...(options.headers || {}),
  };
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

async function downloadAdminFile(path, filename) {
  const response = await fetch(path, { headers: { "X-Admin-Key": getKey() } });
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

async function confirmDemoReadyExport(actionLabel) {
  let health = lastDemoHealth;
  if (!health) {
    const gate = await api("/api/seed/demo-ready-gate");
    if (gate.ready) return true;
    health = {
      status: gate.health_status,
      label: gate.health_label,
      summary: gate.summary,
      issues: gate.issues || [],
    };
  }
  if (health.status === "green") return true;
  const issues = (health.issues || []).slice(0, 3).join("; ");
  const issueSuffix = issues ? ` Issues: ${issues}` : "";
  const message = `Demo health is ${health.label} (${health.status}) — ${health.summary}${issueSuffix}. ${actionLabel} anyway?`;
  return window.confirm(message);
}

async function confirmDemoReadyReset(actionLabel) {
  let health = lastDemoHealth;
  if (!health) {
    const gate = await api("/api/seed/demo-ready-gate");
    if (!gate.ready) return true;
    health = {
      status: gate.health_status,
      label: gate.health_label,
      summary: gate.summary,
      issues: gate.issues || [],
    };
  }
  if (health.status !== "green") return true;
  const facilityLine =
    health.present_facility_count != null && health.expected_facility_count != null
      ? ` (${health.present_facility_count}/${health.expected_facility_count} present, ${health.broadcasting_facility_count ?? health.expected_facility_count}/${health.expected_facility_count} broadcasting)`
      : "";
  const message = `Demo health is ${health.label} (green) — ${health.summary}${facilityLine}. ${actionLabel} will unlock all shifts and clear placements. Continue?`;
  return window.confirm(message);
}

function demoWalkthroughIntact(health) {
  if (!health) return false;
  if (health.status === "green") return true;
  if (
    health.present_facility_count != null &&
    health.expected_facility_count != null &&
    health.present_facility_count !== health.expected_facility_count
  ) {
    return false;
  }
  const issues = health.issues || [];
  return issues.length > 0 && issues.every((issue) => issue.toLowerCase().includes("locked"));
}

async function confirmDemoReadyResetOffer(facilityName) {
  let health = lastDemoHealth;
  if (!health) {
    const status = await api("/api/seed/demo-status");
    health = status.health;
  }
  if (!demoWalkthroughIntact(health)) return true;
  const facilityLine =
    health.present_facility_count != null && health.expected_facility_count != null
      ? ` (${health.present_facility_count}/${health.expected_facility_count} present, ${health.broadcasting_facility_count ?? health.expected_facility_count}/${health.expected_facility_count} broadcasting)`
      : "";
  const message = `Demo walkthrough is intact${facilityLine}. Reset ${facilityName} will unlock this shift and clear its placement. Continue?`;
  return window.confirm(message);
}

async function confirmDemoReadyLockTest(facilityName) {
  let health = lastDemoHealth;
  if (!health) {
    const status = await api("/api/seed/demo-status");
    health = status.health;
  }
  if (!demoWalkthroughIntact(health)) return true;
  const facilityLine =
    health.present_facility_count != null && health.expected_facility_count != null
      ? ` (${health.present_facility_count}/${health.expected_facility_count} present, ${health.broadcasting_facility_count ?? health.expected_facility_count}/${health.expected_facility_count} broadcasting)`
      : "";
  const message = `Demo walkthrough is intact${facilityLine}. Lock test on ${facilityName} will lock this shift and create a placement. Continue?`;
  return window.confirm(message);
}

async function confirmDemoReadyNotifyMatched(facilityName) {
  let health = lastDemoHealth;
  if (!health) {
    const status = await api("/api/seed/demo-status");
    health = status.health;
  }
  if (!demoWalkthroughIntact(health)) return true;
  const facilityLine =
    health.present_facility_count != null && health.expected_facility_count != null
      ? ` (${health.present_facility_count}/${health.expected_facility_count} present, ${health.broadcasting_facility_count ?? health.expected_facility_count}/${health.expected_facility_count} broadcasting)`
      : "";
  const message = `Demo walkthrough is intact${facilityLine}. Notify matched on ${facilityName} will send push alerts to matched clinicians. Continue?`;
  return window.confirm(message);
}

async function confirmDemoReadyEnsurePortal() {
  let health = lastDemoHealth;
  if (!health) {
    const status = await api("/api/seed/demo-status");
    health = status.health;
  }
  if (!demoWalkthroughIntact(health)) return true;
  const facilityLine =
    health.present_facility_count != null && health.expected_facility_count != null
      ? ` (${health.present_facility_count}/${health.expected_facility_count} present, ${health.broadcasting_facility_count ?? health.expected_facility_count}/${health.expected_facility_count} broadcasting)`
      : "";
  const message = `Demo walkthrough is intact${facilityLine}. Ensure demo portal logins will reset all @offercare.demo passwords to SecretPass1. Continue?`;
  return window.confirm(message);
}

async function confirmDemoReadyEnsurePush() {
  let health = lastDemoHealth;
  if (!health) {
    const status = await api("/api/seed/demo-status");
    health = status.health;
  }
  if (!demoWalkthroughIntact(health)) return true;
  const facilityLine =
    health.present_facility_count != null && health.expected_facility_count != null
      ? ` (${health.present_facility_count}/${health.expected_facility_count} present, ${health.broadcasting_facility_count ?? health.expected_facility_count}/${health.expected_facility_count} broadcasting)`
      : "";
  const message = `Demo walkthrough is intact${facilityLine}. Ensure demo push subscriptions will register synthetic push endpoints for all @offercare.demo clinicians. Continue?`;
  return window.confirm(message);
}

async function copyDemoGatesToClipboard() {
  const data = await api("/api/seed/demo-gates");
  await navigator.clipboard.writeText(data.clipboard_text);
  const activeCount = (data.active_gates || []).length;
  const adminActionCount = (data.demo_admin_actions || []).length;
  logOps(
    `Copied demo gate matrix — ${activeCount} active / ${data.gate_count} total · ${adminActionCount} admin actions`
  );
  showToast(
    `Copied gate matrix + admin actions (${activeCount} active / ${data.gate_count} gates · ${adminActionCount} actions)`
  );
}

async function downloadDemoGatesTxtFile() {
  const data = await api("/api/seed/demo-gates");
  await downloadAdminFile("/api/seed/demo-gates.txt", "offercare-demo-gates.txt");
  const adminActionCount = data.demo_admin_action_count ?? (data.demo_admin_actions || []).length;
  logOps(
    `Downloaded demo gates (.txt) — ${data.gate_count} gates · ${adminActionCount} admin actions`
  );
  showToast(`Downloaded gates (.txt) + admin actions (${adminActionCount} actions)`);
}

async function downloadDemoGatesJsonFile() {
  const data = await api("/api/seed/demo-gates");
  await downloadAdminFile("/api/seed/demo-gates.json", "offercare-demo-gates.json");
  const adminActionCount = data.demo_admin_action_count ?? (data.demo_admin_actions || []).length;
  logOps(
    `Exported demo gates (.json) — ${data.gate_count} gates · ${adminActionCount} admin actions`
  );
  showToast(`Exported gates (.json) + admin actions (${adminActionCount} actions)`);
}

function fmtShiftTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function toDatetimeLocalValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDatetimeLocalValue(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

let scheduleEditOfferId = null;

function badge(status) {
  const token = String(status || "").toUpperCase();
  let cls = "pending";
  if (["VERIFIED", "SUBMITTED", "LOCKED", "ACTIVE", "CLEAR"].includes(token)) cls = "ok";
  if (["REJECTED", "FAILED", "EXPIRED", "SUSPENDED", "EXCLUDED", "FLAGGED"].includes(token)) cls = "fail";
  return `<span class="badge ${cls}">${token}</span>`;
}

function renderComplianceSummary(overview) {
  if (!overview) {
    els.complianceSummary.innerHTML = `<p class="empty">Compliance overview unavailable.</p>`;
    return;
  }
  els.complianceSummary.innerHTML = `
    <div class="stat-card"><span class="muted">Total clinicians</span><strong>${overview.total_providers}</strong></div>
    <div class="stat-card"><span class="muted">Dispatch active</span><strong>${overview.dispatch_active}</strong></div>
    <div class="stat-card"><span class="muted">Suspended</span><strong>${overview.dispatch_suspended}</strong></div>
    <div class="stat-card"><span class="muted">Expiring docs</span><strong>${overview.expiring_document_alerts}</strong></div>
    <div class="stat-card"><span class="muted">Crisis signals</span><strong>${overview.crisis_signal_count}</strong></div>
    <div class="stat-card"><span class="muted">Geo radius (mi)</span><strong>${overview.geo_match_radius_miles}</strong></div>
    <div class="stat-card"><span class="muted">PostGIS</span><strong>${overview.postgis_enabled ? "ON" : "Haversine"}</strong></div>
  `;
  const flags = overview.dry_run_flags || {};
  els.complianceFlags.innerHTML = `
    <span class="compliance-flag ${flags.mbon ? "dry" : "live"}">MBON ${flags.mbon ? "dry-run" : "live"}</span>
    <span class="compliance-flag ${flags.oig ? "dry" : "live"}">OIG ${flags.oig ? "dry-run" : "live"}</span>
    <span class="compliance-flag ${flags.judiciary ? "dry" : "live"}">Judiciary ${flags.judiciary ? "dry-run" : "live"}</span>
    <span class="compliance-flag ${flags.job_board ? "dry" : "live"}">Job board ${flags.job_board ? "dry-run" : "live"}</span>
    <span class="compliance-flag ${flags.vms_ingest ? "dry" : "live"}">VMS ingest ${flags.vms_ingest ? "dry-run" : "live"}</span>
  `;
}

function renderComplianceCrisis(rows) {
  if (!rows?.length) {
    els.complianceCrisisTable.innerHTML = `<p class="empty">No crisis signals yet — run a scan after seeding open shifts.</p>`;
    return;
  }
  els.complianceCrisisTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>County</th><th>Severity</th><th>Score</th><th>Summary</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.county || "—"}</td>
            <td>${badge(row.severity)}</td>
            <td>${row.score}</td>
            <td>${row.summary}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function wireComplianceProviderActions() {
  els.complianceProvidersTable.querySelectorAll("[data-compliance-screen]").forEach((btn) => {
    btn.addEventListener("click", () => screenProviderCredentials(btn.dataset.complianceScreen));
  });
  els.complianceProvidersTable.querySelectorAll("[data-compliance-status]").forEach((btn) => {
    btn.addEventListener("click", () => viewComplianceStatus(btn.dataset.complianceStatus));
  });
  els.complianceProvidersTable.querySelectorAll("[data-compliance-audit]").forEach((btn) => {
    btn.addEventListener("click", () => downloadComplianceAudit(btn.dataset.complianceAudit));
  });
}

function renderComplianceProviders(rows) {
  if (!rows?.length) {
    els.complianceProvidersTable.innerHTML = `<p class="empty">No clinicians in compliance roster.</p>`;
    return;
  }
  els.complianceProvidersTable.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Credential</th><th>License</th><th>Dispatch</th><th>Eligible</th><th>Expiring</th><th>Actions</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.full_name}</td>
            <td>${row.credential_type || "—"}</td>
            <td>${badge(row.license_status)}</td>
            <td>${badge(row.dispatch_status)}</td>
            <td>${row.dispatch_eligible ? badge("CLEAR") : badge("SUSPENDED")}</td>
            <td>${row.expiring_documents}</td>
            <td>
              <button class="btn small" data-compliance-screen="${row.provider_id}">Screen</button>
              <button class="btn small ghost" data-compliance-status="${row.provider_id}">Status</button>
              <button class="btn small ghost" data-compliance-audit="${row.provider_id}">Audit ZIP</button>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  wireComplianceProviderActions();
}

function renderComplianceJobBoards(rows) {
  if (!rows?.length) {
    els.complianceJobBoardTable.innerHTML = `<p class="empty">No job board listings yet — run an Indeed / ZipRecruiter scan.</p>`;
    return;
  }
  els.complianceJobBoardTable.innerHTML = `
    <table>
      <thead><tr><th>Source</th><th>Facility</th><th>Role</th><th>Days open</th><th>Crisis</th><th>Matched facility</th><th>Title</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.source}</td>
            <td>${row.facility_name}</td>
            <td>${row.shift_role}</td>
            <td>${row.days_open}</td>
            <td>${row.is_crisis ? badge("FLAGGED") : badge("CLEAR")}</td>
            <td>${row.matched_facility_name || "—"}</td>
            <td>${row.job_url ? `<a href="${row.job_url}" target="_blank" rel="noopener">${row.job_title}</a>` : row.job_title}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderComplianceVmsIngest(rows) {
  if (!rows?.length) {
    els.complianceVmsIngestTable.innerHTML = `<p class="empty">No VMS ingestions yet — poll ShiftWise / Fieldglass.</p>`;
    return;
  }
  els.complianceVmsIngestTable.innerHTML = `
    <table>
      <thead><tr><th>Source</th><th>Status</th><th>Facility</th><th>Role</th><th>Pay</th><th>Offer</th><th>Ingested</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.source}</td>
            <td>${badge(row.status)}</td>
            <td>${row.facility_name || "—"}</td>
            <td>${row.shift_role || "—"}</td>
            <td>${row.hourly_pay_rate != null ? `$${row.hourly_pay_rate}` : "—"}</td>
            <td>${row.offer_id ? row.offer_id.slice(0, 8) : "—"}</td>
            <td>${row.ingested_at ? new Date(row.ingested_at).toLocaleString() : "—"}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

async function loadOutreachDashboard() {
  const [targets, emails] = await Promise.all([
    api("/api/outreach/targets?limit=25"),
    api("/api/outreach/emails/log?limit=25"),
  ]);
  renderOutreachTargets(targets);
  renderOutreachEmails(emails);
}

function renderWorkerInflowSummary(data) {
  if (!els.workerInflowSummary) return;
  const joinUrl = data.join_url || "/join";
  const absoluteJoin = joinUrl.startsWith("http") ? joinUrl : `${window.location.origin}${joinUrl}`;
  if (els.workerInflowJoinLink) els.workerInflowJoinLink.href = absoluteJoin;
  els.workerInflowSummary.innerHTML = `
    <div class="stat-card"><span class="muted">Opt-in applicants</span><strong>${data.opt_in_applicants ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Pending review</span><strong>${data.pending_review ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Verified workers</span><strong>${data.verified_workers ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">SMS consent recorded</span><strong>${data.sms_consent_recorded ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Terms accepted</span><strong>${data.terms_accepted ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Privacy accepted</span><strong>${data.privacy_accepted ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">SMS opt-outs</span><strong>${data.sms_opt_out_count ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Consent / ToS version</span><strong>${data.consent_version || "—"}</strong></div>`;
  if (els.workerInflowPlaybook) {
    els.workerInflowPlaybook.innerHTML = (data.playbook || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
  els.workerInflowSummary.dataset.joinUrl = absoluteJoin;
}

async function loadWorkerInflowDashboard() {
  const data = await api("/api/landing/maryland/inflow-summary");
  renderWorkerInflowSummary(data);
  return data;
}

async function copyWorkerInflowLink() {
  const url = els.workerInflowSummary?.dataset.joinUrl || `${window.location.origin}/join`;
  try {
    await navigator.clipboard.writeText(url);
    showToast("Join URL copied — share with Maryland CNAs/LPNs");
  } catch {
    showToast("Could not copy join URL", true);
  }
}

function renderOutreachTargets(rows) {
  if (!rows?.length) {
    els.outreachTargetsTable.innerHTML = `<p class="empty">No crisis targets yet — run job board + internal crisis scans first.</p>`;
    return;
  }
  els.outreachTargetsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>County</th><th>Contacts</th><th>Crisis summary</th><th>Actions</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.county || "—"}</td>
            <td>${row.contact_count}</td>
            <td>${row.crisis_summary}</td>
            <td><button class="btn small ghost" data-enrich-facility="${row.facility_id}">Enrich</button></td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  els.outreachTargetsTable.querySelectorAll("[data-enrich-facility]").forEach((btn) => {
    btn.addEventListener("click", () => enrichOutreachFacility(btn.dataset.enrichFacility));
  });
}

function renderOutreachEmails(rows) {
  if (!rows?.length) {
    els.outreachEmailTable.innerHTML = `<p class="empty">No outreach emails drafted yet.</p>`;
    return;
  }
  els.outreachEmailTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Recipient</th><th>Subject</th><th>Status</th><th>Mode</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.recipient_name}<br><span class="muted">${row.recipient_email}</span></td>
            <td>${row.subject}</td>
            <td>${badge(row.status)}</td>
            <td>${row.mode}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

async function enrichOutreachFacility(facilityId) {
  try {
    const data = await api(`/api/outreach/facilities/${facilityId}/enrich`, { method: "POST" });
    showToast(`Enriched ${data.contacts_enriched} contact(s) for ${data.facility_name}`);
    await loadOutreachDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function runOutreachCampaign(send = false) {
  try {
    const data = await api(`/api/outreach/campaign/run?limit=10&send=${send}`, { method: "POST" });
    showToast(
      `Outreach — ${data.targets} targets, ${data.emails_drafted} drafted, ${data.emails_sent} sent`,
    );
    await loadOutreachDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderInfraChecks(data) {
  if (!els.infraChecks) return;
  if (els.infraSummary) {
    els.infraSummary.textContent = `${data.summary} (${data.required_pass}/${data.required_total} required checks pass)`;
  }
  const icon = { pass: "✓", warn: "!", fail: "✗" };
  els.infraChecks.innerHTML = (data.checks || [])
    .map(
      (row) => `
    <div class="deploy-check ${row.status}">
      <strong>${icon[row.status] || "?"} ${row.name.replace(/_/g, " ")}</strong>
      <span class="muted">${row.detail}</span>
    </div>`,
    )
    .join("");
}

async function loadInfrastructureReadiness() {
  const data = await api("/api/vettedcare/infrastructure");
  renderInfraChecks(data);
  return data;
}

function vettedBadge(status) {
  const key = String(status || "ACTION_NEEDED").toUpperCase();
  const cls =
    key === "CLEAR"
      ? "vetted-clear"
      : key === "EXPIRING"
        ? "vetted-expiring"
        : key === "BLOCKED"
          ? "vetted-blocked"
          : "vetted-action";
  return `<span class="vetted-badge ${cls}">${key.replace("_", " ")}</span>`;
}

function renderVettedSummary(data) {
  if (!els.vettedSummary) return;
  const counts = data.status_counts || {};
  els.vettedSummary.innerHTML = `
    <div class="stat-card"><span class="muted">CLEAR</span><strong>${counts.CLEAR ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">EXPIRING</span><strong>${counts.EXPIRING ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">ACTION NEEDED</span><strong>${counts.ACTION_NEEDED ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">BLOCKED</span><strong>${counts.BLOCKED ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Clear rate</span><strong>${data.clear_rate_percent ?? 0}%</strong></div>
    <div class="stat-card"><span class="muted">Manus runs</span><strong>${data.manus_runs_applied ?? 0}/${data.manus_runs_total ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Safety alerts</span><strong>${data.alerts_sent_total ?? 0}</strong></div>
    <div class="stat-card"><span class="muted">Audit events</span><strong>${data.audit_events_total ?? 0}</strong></div>`;
  if (els.vettedTagline) els.vettedTagline.textContent = data.tagline || els.vettedTagline.textContent;
  if (els.vettedManusHint) {
    els.vettedManusHint.textContent =
      "Manus worker: GET /api/vettedcare/manus/work-queue → run checks → POST /api/vettedcare/manus/run (header X-Manus-Key)";
  }
}

function renderVettedProviders(rows) {
  if (!els.vettedProvidersTable) return;
  if (!rows?.length) {
    els.vettedProvidersTable.innerHTML = `<p class="empty">No clinicians yet — worker opt-in or seed demo data first.</p>`;
    return;
  }
  els.vettedProvidersTable.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Role</th><th>Safety status</th><th>License</th><th>Dispatch</th><th>Updated</th><th>Actions</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.full_name}</td>
            <td>${row.credential_type || "—"}</td>
            <td>${vettedBadge(row.vetted_status)}</td>
            <td>${badge(row.license_status)}</td>
            <td>${badge(row.dispatch_status)}</td>
            <td>${row.vetted_status_updated_at ? new Date(row.vetted_status_updated_at).toLocaleString() : "—"}</td>
            <td>
              <button class="btn small ghost" data-vetted-profile="${row.provider_id}">Profile</button>
              <button class="btn small ghost" data-compliance-screen="${row.provider_id}">Screen</button>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  els.vettedProvidersTable.querySelectorAll("[data-vetted-profile]").forEach((btn) => {
    btn.addEventListener("click", () => viewVettedProfile(btn.dataset.vettedProfile));
  });
  els.vettedProvidersTable.querySelectorAll("[data-compliance-screen]").forEach((btn) => {
    btn.addEventListener("click", () => screenProviderCredentials(btn.dataset.complianceScreen));
  });
}

function renderVettedAudit(rows) {
  if (!els.vettedAuditTable) return;
  if (!rows?.length) {
    els.vettedAuditTable.innerHTML = `<p class="empty">No safety audit events yet.</p>`;
    return;
  }
  els.vettedAuditTable.innerHTML = `
    <table>
      <thead><tr><th>When</th><th>Event</th><th>Actor</th><th>Status change</th><th>Summary</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.created_at ? new Date(row.created_at).toLocaleString() : "—"}</td>
            <td>${row.event_type}</td>
            <td>${row.actor || "—"}</td>
            <td>${row.previous_status ? `${row.previous_status} → ${row.new_status}` : row.new_status || "—"}</td>
            <td>${row.summary}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderVettedAlerts(rows) {
  if (!els.vettedAlertsTable) return;
  if (!rows?.length) {
    els.vettedAlertsTable.innerHTML = `<p class="empty">No credential safety alerts sent yet.</p>`;
    return;
  }
  els.vettedAlertsTable.innerHTML = `
    <table>
      <thead><tr><th>When</th><th>Channel</th><th>Status</th><th>Type</th><th>Delivery</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.sent_at ? new Date(row.sent_at).toLocaleString() : "—"}</td>
            <td>${row.channel}</td>
            <td>${vettedBadge(row.vetted_status)}</td>
            <td>${row.alert_type}</td>
            <td>${badge(row.delivery_status)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

async function loadVettedCareDashboard() {
  const data = await api("/api/vettedcare/dashboard?limit=100");
  renderVettedSummary(data);
  renderVettedProviders(data.providers || []);
  renderVettedAudit(data.recent_audit || []);
  renderVettedAlerts(data.recent_alerts || []);
  return data;
}

async function viewVettedProfile(providerId) {
  try {
    const data = await api(`/api/vettedcare/providers/${providerId}`);
    els.complianceBody.textContent = JSON.stringify(data, null, 2);
    els.complianceDialog.showModal();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function runVettedSafetyCycle() {
  try {
    const data = await api("/api/vettedcare/monitor/run", { method: "POST" });
    const changes = data.vetted_sync?.status_changes?.length || 0;
    const alerts = data.alerts_sent?.length || 0;
    showToast(`Safety cycle — ${changes} status change(s), ${alerts} alert(s) sent`);
    await loadVettedCareDashboard();
    await loadComplianceDashboard();
    await refreshPendingAndStats();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function syncVettedStatuses() {
  try {
    const data = await api("/api/vettedcare/sync", { method: "POST" });
    const changes = data.status_changes?.length || 0;
    showToast(`Synced ${data.providers_synced} clinician(s) — ${changes} status change(s)`);
    await loadVettedCareDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadComplianceDashboard() {
  const [overview, crisisSignals, jobBoardListings, vmsIngestLog] = await Promise.all([
    api("/api/compliance/overview?limit=100"),
    api("/api/compliance/crisis/signals?limit=25"),
    api("/api/compliance/crisis/job-boards/listings?limit=25"),
    api("/api/vms/shifts/ingest/log?limit=25"),
  ]);
  renderComplianceSummary(overview);
  renderComplianceCrisis(crisisSignals);
  renderComplianceJobBoards(jobBoardListings);
  renderComplianceVmsIngest(vmsIngestLog);
  renderComplianceProviders(overview.providers || []);
  return overview;
}

async function screenProviderCredentials(providerId) {
  try {
    const data = await api(`/api/compliance/providers/${providerId}/screen`, { method: "POST" });
    const label = data.blocked ? "blocked" : "passed";
    showToast(`Credentialing ${label} — MBON ${data.mbon_status}, OIG ${data.oig_status}`);
    await loadComplianceDashboard();
    await refreshPendingAndStats();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function viewComplianceStatus(providerId) {
  try {
    const data = await api(`/api/compliance/providers/${providerId}/status`);
    els.complianceBody.textContent = JSON.stringify(data, null, 2);
    els.complianceDialog.showModal();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function downloadComplianceAudit(providerId) {
  try {
    await downloadAdminFile(`/api/compliance/providers/${providerId}/audit-packet`, `offercare-audit-${providerId}.zip`);
    showToast("Audit packet downloaded");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function runComplianceMonitor() {
  try {
    const data = await api("/api/compliance/monitor/run", { method: "POST" });
    const suspended = data.suspended_provider_ids?.length || 0;
    showToast(`Monitor complete — ${data.documents_checked} docs checked, ${suspended} suspended`);
    await loadComplianceDashboard();
    await refreshPendingAndStats();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function scanCrisisSignals() {
  try {
    const data = await api("/api/compliance/crisis/scan", { method: "POST" });
    showToast(`Internal crisis scan created ${data.signals_created} signal(s)`);
    await loadComplianceDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function scanJobBoardCrisis() {
  try {
    const data = await api("/api/compliance/crisis/job-boards/scan", { method: "POST" });
    showToast(
      `Job boards — ${data.listings_scraped} scraped, ${data.crisis_listings} crisis, ${data.signals_created} facility signal(s)`,
    );
    await loadComplianceDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function ingestVmsShifts() {
  try {
    const data = await api("/api/vms/shifts/ingest?persist=true", { method: "POST" });
    showToast(
      `VMS ingest — ${data.shifts_fetched} fetched, ${data.offers_created} offers created, ${data.offers_skipped} skipped`,
    );
    await loadComplianceDashboard();
    await refreshPendingAndStats();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshPendingAndStats() {
  const [pending, shifts, placements, opsMetrics] = await Promise.all([
    api("/api/clinicians/pending"),
    loadShifts(),
    api("/api/vms/placements?limit=50"),
    api("/api/ops/metrics"),
  ]);
  renderStats(pending, shifts, placements, opsMetrics);
  renderPending(pending);
}

function renderProductionOpsDashboard(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionOpsSummary) {
    els.productionOpsSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Production ops</span>
        <strong>${data.production_ops_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">MD launch</span>
        <strong>${summary.maryland_launch_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Workers running</span>
        <strong>${summary.workers_running_count ?? "—"} / 4</strong>
      </div>
      <div class="stat-card">
        <span class="label">Live scrapers</span>
        <strong>${summary.live_scrapers_live_count ?? "—"} / ${summary.live_scrapers_total ?? 5}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Lock rate</span>
        <strong>${summary.lock_rate == null ? "—" : `${(summary.lock_rate * 100).toFixed(1)}%`}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Audit (24h)</span>
        <strong>${summary.audit_events_24h ?? "—"}</strong>
      </div>`;
  }
  if (els.productionOpsChecks) {
    els.productionOpsChecks.innerHTML = (data.checks || []).map((row) => `
      <div class="deploy-item">
        <strong>${row.title}</strong>${badge(row.status.toUpperCase())}
        <p>${row.detail}</p>
        ${row.action ? `<p><em>Action:</em> ${row.action}</p>` : ""}
      </div>`).join("");
  }
  if (els.productionOpsScraperProbes) {
    const probes = data.scraper_probes || [];
    els.productionOpsScraperProbes.innerHTML = probes.length
      ? probes.map((row) => `
        <div class="integration-card">
          <strong>${row.channel_id}</strong>
          ${badge(row.status)}
          <p class="meta">${row.message}</p>
          <p class="meta">${row.latency_ms == null ? "—" : `${row.latency_ms}ms`}</p>
        </div>`).join("")
      : `<p class="muted">Run Refresh all production signals to probe live scrapers.</p>`;
  }
  if (els.productionOpsSteps) {
    els.productionOpsSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
  if (data.workers?.cascade) {
    renderCascadeWorker(data.workers.cascade);
  }
  if (data.workers?.staffing) {
    renderStaffingScheduler(data.workers.staffing);
  }
  if (data.workers?.compliance) {
    renderComplianceScheduler(data.workers.compliance);
  }
  if (data.audit_events?.length) {
    renderAuditLog(data.audit_events);
  }
}

async function loadProductionOpsDashboard() {
  const data = await api("/api/ops/production-dashboard");
  renderProductionOpsDashboard(data);
  return data;
}

async function refreshProductionOpsDashboard() {
  const data = await api("/api/ops/production-dashboard/refresh", {
    method: "POST",
    body: JSON.stringify({ probe_scrapers: true }),
  });
  renderProductionOpsDashboard(data);
  const liveOk = (data.scraper_probes || []).filter((row) => row.status === "LIVE_OK").length;
  showToast(
    `Production ops refreshed — ${data.production_ops_ready ? "READY" : "NOT YET"}`
      + (data.scraper_probes?.length ? ` · probes ${liveOk}/${data.scraper_probes.length} LIVE_OK` : ""),
  );
  logOps(`Production ops refresh — workers ${data.summary?.workers_running_count ?? "—"}/4 running`);
  return data;
}

function renderProductionPerfectionCapstone(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionPerfectionSummary) {
    els.productionPerfectionSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Perfection</span>
        <strong>${data.production_perfection_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Ops dashboard</span>
        <strong>${data.production_ops_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">MD launch</span>
        <strong>${data.maryland_launch_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Workers enabled</span>
        <strong>${summary.workers_enabled_count ?? "—"} / 4</strong>
      </div>`;
  }
  if (els.productionPerfectionSteps) {
    els.productionPerfectionSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionPerfectionCapstone() {
  const data = await api("/api/deploy/production-perfection-capstone");
  renderProductionPerfectionCapstone(data);
  return data;
}

async function runProductionPerfectionCheck() {
  const data = await api("/api/deploy/production-perfection-check", {
    method: "POST",
    body: JSON.stringify({ probe_scrapers: false }),
  });
  if (data.ok) {
    showToast(`Production perfection OK — ${data.facility_name || "demo shift"} locked`);
    logOps(
      `Production perfection check — ops ${data.ops_refresh_ok ? "OK" : "FAIL"}, `
        + `launch smoke ${data.launch_smoke_ok ? "OK" : "FAIL"} · placement ${data.placement_id || "—"}`,
    );
  } else {
    showToast(data.message || "Production perfection check failed", true);
    logOps(`Production perfection check failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionPerfectionCapstone();
  return data;
}

function renderProductionLaunchCeremony(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionLaunchCeremonySummary) {
    els.productionLaunchCeremonySummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Launch ceremony</span>
        <strong>${data.launch_ceremony_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Perfection</span>
        <strong>${data.production_perfection_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? "—"} files</strong>
      </div>
      <div class="stat-card">
        <span class="label">Sign-off doc</span>
        <strong>${data.signoff_markdown ? "READY" : "—"}</strong>
      </div>`;
  }
  if (els.productionLaunchCeremonySteps) {
    els.productionLaunchCeremonySteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionLaunchCeremony() {
  const data = await api("/api/deploy/production-launch-ceremony");
  renderProductionLaunchCeremony(data);
  return data;
}

async function runProductionLaunchCeremony() {
  const data = await api("/api/deploy/production-launch-ceremony/run", {
    method: "POST",
    body: JSON.stringify({ probe_scrapers: false }),
  });
  if (data.ok) {
    showToast(`Launch ceremony OK — ${data.deploy_bundle_file_count}-file bundle ready`);
    logOps(
      `Production launch ceremony — perfection ${data.perfection_check_ok ? "OK" : "FAIL"} · `
        + `placement ${data.placement_id || "—"}`,
    );
  } else {
    showToast(data.message || "Production launch ceremony failed", true);
    logOps(`Production launch ceremony failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionLaunchCeremony();
  return data;
}

function renderProductionGoLiveRecord(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionGoLiveRecordSummary) {
    els.productionGoLiveRecordSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Go-live record</span>
        <strong>${data.production_go_live_record_ready ? "SEALED" : data.sealed ? "FAILED" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Ceremony</span>
        <strong>${data.launch_ceremony_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Record ID</span>
        <strong>${data.record_id ? data.record_id.slice(0, 8) + "…" : "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? "—"} files</strong>
      </div>`;
  }
  if (els.productionGoLiveRecordSteps) {
    els.productionGoLiveRecordSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionGoLiveRecord() {
  const data = await api("/api/deploy/production-go-live-record");
  renderProductionGoLiveRecord(data);
  return data;
}

async function sealProductionGoLiveRecord() {
  const data = await api("/api/deploy/production-go-live-record/seal", {
    method: "POST",
    body: JSON.stringify({ probe_scrapers: false }),
  });
  if (data.ok) {
    const label = data.already_sealed ? "already sealed" : "sealed";
    showToast(`Go-live record ${label} — ${data.deploy_bundle_file_count}-file bundle ready`);
    logOps(
      `Production go-live record ${label} — record ${data.record_id || "—"} · `
        + `placement ${data.placement_id || "—"}`,
    );
  } else {
    showToast(data.message || "Seal launch record failed", true);
    logOps(`Seal launch record failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionGoLiveRecord();
  return data;
}

function renderProductionLaunchAttestation(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionLaunchAttestationSummary) {
    els.productionLaunchAttestationSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Attestation</span>
        <strong>${data.production_launch_attestation_ready ? "ATTESTED" : data.attested ? "INVALID" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Go-live</span>
        <strong>${data.production_go_live_record_ready ? "SEALED" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">SHA-256</span>
        <strong>${data.digest_sha256 ? data.digest_sha256.slice(0, 12) + "…" : "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? "—"} files</strong>
      </div>`;
  }
  if (els.productionLaunchAttestationSteps) {
    els.productionLaunchAttestationSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionLaunchAttestation() {
  const data = await api("/api/deploy/production-launch-attestation");
  renderProductionLaunchAttestation(data);
  return data;
}

async function attestProductionLaunch() {
  const data = await api("/api/deploy/production-launch-attestation/attest", {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (data.ok) {
    const label = data.already_attested ? "already attested" : "attested";
    showToast(`Launch ${label} — digest ${(data.digest_sha256 || "").slice(0, 12)}…`);
    logOps(
      `Production launch attestation ${label} — attestation ${data.attestation_id || "—"} · `
        + `record ${data.record_id || "—"}`,
    );
  } else {
    showToast(data.message || "Attest launch failed", true);
    logOps(`Attest launch failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionLaunchAttestation();
  return data;
}

function renderProductionLaunchPerfectionSeal(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionLaunchPerfectionSealSummary) {
    els.productionLaunchPerfectionSealSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Perfection seal</span>
        <strong>${data.production_launch_perfection_ready ? "SEALED" : data.sealed ? "FAILED" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Perfection</span>
        <strong>${data.production_perfection_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Attestation</span>
        <strong>${data.production_launch_attestation_ready ? "ATTESTED" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? "—"} files</strong>
      </div>`;
  }
  if (els.productionLaunchPerfectionSealSteps) {
    els.productionLaunchPerfectionSealSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionLaunchPerfectionSeal() {
  const data = await api("/api/deploy/production-launch-perfection-seal");
  renderProductionLaunchPerfectionSeal(data);
  return data;
}

async function sealProductionLaunchPerfection() {
  const data = await api("/api/deploy/production-launch-perfection-seal/seal", {
    method: "POST",
    body: JSON.stringify({ probe_scrapers: false }),
  });
  if (data.ok) {
    const label = data.already_sealed ? "already sealed" : "sealed";
    showToast(`Launch perfection ${label} — ${data.deploy_bundle_file_count}-file bundle ready`);
    logOps(
      `Production launch perfection seal ${label} — seal ${data.seal_id || "—"} · `
        + `digest ${(data.digest_sha256 || "").slice(0, 12)}…`,
    );
  } else {
    showToast(data.message || "Seal launch perfection failed", true);
    logOps(`Seal launch perfection failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionLaunchPerfectionSeal();
  return data;
}

function renderProductionLaunchArchive(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionLaunchArchiveSummary) {
    els.productionLaunchArchiveSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Archive</span>
        <strong>${data.production_launch_archive_ready ? "ARCHIVED" : data.archived ? "INVALID" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Artifacts</span>
        <strong>${data.artifact_count ?? summary.artifact_count ?? "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Manifest</span>
        <strong>${data.manifest_digest ? data.manifest_digest.slice(0, 12) + "…" : "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? "—"} files</strong>
      </div>`;
  }
  if (els.productionLaunchArchiveSteps) {
    els.productionLaunchArchiveSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionLaunchArchive() {
  const data = await api("/api/deploy/production-launch-archive");
  renderProductionLaunchArchive(data);
  return data;
}

async function archiveProductionLaunch() {
  const data = await api("/api/deploy/production-launch-archive/archive", {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (data.ok) {
    const label = data.already_archived ? "already archived" : "archived";
    showToast(`Launch ${label} — ${data.artifact_count} artifacts · ${data.deploy_bundle_file_count}-file bundle`);
    logOps(
      `Production launch archive ${label} — archive ${data.archive_id || "—"} · `
        + `digest ${(data.manifest_digest || "").slice(0, 12)}…`,
    );
  } else {
    showToast(data.message || "Archive launch failed", true);
    logOps(`Archive launch failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionLaunchArchive();
  return data;
}

function renderProductionLaunchFinale(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionLaunchFinaleSummary) {
    els.productionLaunchFinaleSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Finale</span>
        <strong>${data.production_launch_finale_ready ? "COMPLETE" : data.completed ? "INVALID" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Archive</span>
        <strong>${data.production_launch_archive_ready ? "ARCHIVED" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Perfection seal</span>
        <strong>${data.production_launch_perfection_ready ? "SEALED" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? "—"} files</strong>
      </div>`;
  }
  if (els.productionLaunchFinaleSteps) {
    els.productionLaunchFinaleSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionLaunchFinale() {
  const data = await api("/api/deploy/production-launch-finale");
  renderProductionLaunchFinale(data);
  return data;
}

async function runProductionLaunchFinale() {
  const data = await api("/api/deploy/production-launch-finale/run", {
    method: "POST",
    body: JSON.stringify({ probe_scrapers: false }),
  });
  if (data.ok) {
    const label = data.already_completed ? "already completed" : "complete";
    showToast(`Launch finale ${label} — ${data.deploy_bundle_file_count}-file bundle ready`);
    logOps(
      `Production launch perfection finale ${label} — finale ${data.finale_id || "—"} · `
        + `digest ${(data.manifest_digest || "").slice(0, 12)}…`,
    );
  } else {
    showToast(data.message || "Run launch finale failed", true);
    logOps(`Run launch finale failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionLaunchFinale();
  return data;
}

function renderProductionLaunchBundleVerification(data) {
  if (!data) return;
  const summary = data.summary || {};
  if (els.productionLaunchBundleVerificationSummary) {
    els.productionLaunchBundleVerificationSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Verified</span>
        <strong>${data.production_launch_bundle_verified_ready ? "VERIFIED" : data.verified ? "STALE" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Matched</span>
        <strong>${data.matched_count ?? "—"} / ${data.matched_count != null ? (data.matched_count + (data.supplemental_count || 0)) : "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Manifest</span>
        <strong>${data.manifest_digest ? data.manifest_digest.slice(0, 12) + "…" : "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Deploy bundle</span>
        <strong>${summary.deploy_bundle_file_count ?? data.bundle_file_count ?? "—"} files</strong>
      </div>`;
  }
  if (els.productionLaunchBundleVerificationSteps) {
    els.productionLaunchBundleVerificationSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
}

async function loadProductionLaunchBundleVerification() {
  const data = await api("/api/deploy/production-launch-perfection-manifest");
  renderProductionLaunchBundleVerification(data);
  return data;
}

async function verifyProductionLaunchBundle() {
  const data = await api("/api/deploy/production-launch-perfection-manifest/verify", {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (data.ok) {
    const label = data.already_verified ? "already verified" : "verified";
    showToast(`Launch bundle ${label} — ${data.matched_count} archived + ${data.supplemental_count} capstone files`);
    logOps(
      `Production launch bundle ${label} — verification ${data.verification_id || "—"} · `
        + `digest ${(data.manifest_digest || "").slice(0, 12)}…`,
    );
  } else {
    showToast(data.message || "Verify launch bundle failed", true);
    logOps(`Verify launch bundle failed — ${data.message}`);
  }
  await refreshPendingAndStats();
  await loadProductionLaunchBundleVerification();
  return data;
}

function renderStats(pending, shifts, placements, ops) {
  const pendingVms = placements.filter((p) => p.vms_submission_status === "PENDING").length;
  els.stats.innerHTML = `
    <div class="stat-card"><span class="muted">Pending clinicians</span><strong>${pending.length}</strong></div>
    <div class="stat-card"><span class="muted">Open shifts</span><strong>${shifts.length}</strong></div>
    <div class="stat-card"><span class="muted">Placements</span><strong>${placements.length}</strong></div>
    <div class="stat-card"><span class="muted">VMS pending</span><strong>${pendingVms}</strong></div>
  `;
  if (ops) {
    els.opsMetrics.innerHTML = `
      <div class="stat-card"><span class="muted">Verified clinicians</span><strong>${ops.verified_clinicians}</strong></div>
      <div class="stat-card"><span class="muted">Locked shifts</span><strong>${ops.locked_shifts}</strong></div>
      <div class="stat-card"><span class="muted">SMS sent</span><strong>${ops.total_sms_sent}</strong></div>
      <div class="stat-card"><span class="muted">Emails sent</span><strong>${ops.total_emails_sent ?? 0}</strong></div>
      <div class="stat-card"><span class="muted">Lock rate</span><strong>${(ops.lock_rate * 100).toFixed(1)}%</strong></div>
      <div class="stat-card"><span class="muted">Facilities</span><strong>${ops.facilities}</strong></div>
      <div class="stat-card"><span class="muted">Audit (24h)</span><strong>${ops.audit_events_24h}</strong></div>
    `;
  }
}

function renderCascadeWorker(status) {
  if (!status) return;
  const mode = status.running ? "running" : "stopped";
  els.cascadeWorkerStatus.textContent =
    `Cascade worker ${mode} · interval ${status.interval_seconds}s · timeout ${status.timeout_seconds}s` +
    (status.enabled ? "" : " (disabled in config)");
}

function renderStaffingScheduler(status) {
  if (!status || !els.staffingSchedulerStatus) return;
  const vmsMode = status.vms_running ? "running" : "stopped";
  const boardMode = status.job_board_running ? "running" : "stopped";
  const vmsLast = status.vms_last_run_at
    ? new Date(status.vms_last_run_at).toLocaleString()
    : "never";
  const boardLast = status.job_board_last_run_at
    ? new Date(status.job_board_last_run_at).toLocaleString()
    : "never";
  els.staffingSchedulerStatus.textContent =
    `VMS poll ${vmsMode} · every ${Math.round(status.vms_interval_seconds / 60)}m · last ${vmsLast}` +
    (status.vms_enabled ? "" : " (VMS disabled)") +
    ` · Job board ${boardMode} · every ${Math.round(status.job_board_interval_seconds / 3600)}h · last ${boardLast}` +
    (status.job_board_enabled ? "" : " (job board disabled)");
}

function renderComplianceScheduler(status) {
  if (!status || !els.complianceSchedulerStatus) return;
  const mode = status.running ? "running" : "stopped";
  const last = status.last_run_at
    ? new Date(status.last_run_at).toLocaleString()
    : "never";
  const checked = status.last_documents_checked ?? "—";
  const suspended = status.last_suspended_count ?? "—";
  els.complianceSchedulerStatus.textContent =
    `Compliance monitor ${mode} · every ${Math.round(status.interval_seconds / 3600)}h · last ${last}` +
    (status.enabled ? "" : " (disabled)") +
    ` · docs checked ${checked} · suspended ${suspended}`;
}

async function refreshSchedulerPanels() {
  const [cascadeWorker, staffingScheduler, complianceScheduler, auditEvents] = await Promise.all([
    api("/api/ops/cascade-worker/status"),
    api("/api/ops/staffing-scheduler/status"),
    api("/api/ops/compliance-scheduler/status"),
    api("/api/ops/audit?limit=25"),
  ]);
  renderCascadeWorker(cascadeWorker);
  renderStaffingScheduler(staffingScheduler);
  renderComplianceScheduler(complianceScheduler);
  renderAuditLog(auditEvents);
}

async function runCascadeWorkerTick() {
  const data = await api("/api/ops/cascade-worker/tick", { method: "POST" });
  showToast(`Cascade tick — ${data.advanced} offer(s) advanced`);
  await refreshSchedulerPanels();
}

async function runStaffingVmsTick() {
  const data = await api("/api/ops/staffing-scheduler/vms-tick", { method: "POST" });
  showToast(
    `VMS poll tick — ${data.shifts_fetched} fetched, ${data.offers_created} created, ${data.offers_skipped} skipped`,
  );
  await refreshSchedulerPanels();
  await refreshPendingAndStats();
}

async function runStaffingJobBoardTick() {
  const data = await api("/api/ops/staffing-scheduler/job-board-tick", { method: "POST" });
  showToast(
    `Job board tick — ${data.listings_scraped} scraped, ${data.crisis_listings} crisis, ${data.signals_created} signal(s)`,
  );
  await refreshSchedulerPanels();
}

async function runComplianceSchedulerTick() {
  const data = await api("/api/ops/compliance-scheduler/tick", { method: "POST" });
  const suspended = data.suspended_provider_ids?.length || 0;
  showToast(`Compliance tick — ${data.documents_checked} docs checked, ${suspended} suspended`);
  await refreshSchedulerPanels();
  await loadComplianceDashboard();
}

function renderLiveScrapers(data) {
  if (!data || !els.liveScrapersGrid) return;
  const channels = Object.entries(data.channels || {});
  if (!channels.length) {
    els.liveScrapersGrid.innerHTML = `<p class="empty">No live scraper channels configured.</p>`;
    return;
  }
  els.liveScrapersGrid.innerHTML = channels.map(([id, row]) => {
    const status = row.live_ready ? "LIVE READY" : row.dry_run ? "DRY RUN" : "OFFLINE";
    return `
      <div class="integration-card" data-live-scraper-id="${id}">
        <strong>${row.name}</strong>
        ${badge(status.replace(" ", "_"))}
        <p class="meta">${row.detail}</p>
        ${row.endpoint ? `<p class="meta">Endpoint: ${row.endpoint}</p>` : ""}
        <p class="meta">${row.config_hint || id}</p>
        <button class="btn ghost live-scraper-probe-btn" data-channel-id="${id}">Probe channel</button>
      </div>`;
  }).join("");
  els.liveScrapersGrid.querySelectorAll(".live-scraper-probe-btn").forEach((button) => {
    button.addEventListener("click", () => {
      probeLiveScraperChannel(button.dataset.channelId).catch((error) => showToast(error.message, true));
    });
  });
}

async function probeLiveScraperChannel(channelId) {
  const data = await api(`/api/integrations/live-scrapers/${encodeURIComponent(channelId)}/probe`, {
    method: "POST",
  });
  const latency = data.latency_ms == null ? "—" : `${data.latency_ms}ms`;
  showToast(`${channelId} — ${data.status} (${latency})`);
}

async function probeAllLiveScrapers() {
  const data = await api("/api/integrations/live-scrapers/probe", { method: "POST" });
  const liveOk = data.probes.filter((row) => row.status === "LIVE_OK").length;
  showToast(`Live scraper probes — ${liveOk}/${data.probes.length} LIVE_OK`);
}

async function copyLiveScrapersGoLiveEnv() {
  const data = await api("/api/integrations/live-scrapers/go-live-profile");
  await navigator.clipboard.writeText(data.env_snippet);
  showToast(`Copied go-live .env snippet (${data.live_ready_count}/${data.total_channels} live-ready now)`);
}

function renderAuditLog(rows) {
  if (!rows.length) {
    els.auditTable.innerHTML = `<p class="empty">No audit events yet.</p>`;
    return;
  }
  els.auditTable.innerHTML = `
    <table>
      <thead><tr><th>When</th><th>Event</th><th>Actor</th><th>Summary</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.created_at ? new Date(row.created_at).toLocaleString() : ""}</td>
            <td>${badge(row.event_type)}</td>
            <td>${row.actor || "—"}</td>
            <td>${row.summary}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderPending(rows) {
  if (!rows.length) {
    els.pendingTable.innerHTML = `<p class="empty">No pending clinician applications.</p>`;
    return;
  }
  els.pendingTable.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Credential</th><th>Email</th><th>License</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.full_name}</td>
            <td>${row.credential_type || "RN"}</td>
            <td>${row.email}</td>
            <td>${row.md_license_number}</td>
            <td>${badge(row.license_status)}</td>
            <td>
              <button class="btn small" data-screen="${row.provider_id}">Screen</button>
              <button class="btn small" data-verify="${row.provider_id}">Verify</button>
              <button class="btn small danger" data-reject="${row.provider_id}">Reject</button>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  els.pendingTable.querySelectorAll("[data-screen]").forEach((btn) => {
    btn.addEventListener("click", () => screenProviderCredentials(btn.dataset.screen));
  });
  els.pendingTable.querySelectorAll("[data-verify]").forEach((btn) => {
    btn.addEventListener("click", () => verifyClinician(btn.dataset.verify, "VERIFY"));
  });
  els.pendingTable.querySelectorAll("[data-reject]").forEach((btn) => {
    btn.addEventListener("click", () => verifyClinician(btn.dataset.reject, "REJECT"));
  });
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
  return `/api/shifts/open?${params.toString()}`;
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

async function loadShiftFilters() {
  const options = await api("/api/shifts/filters");
  populateShiftFilters(options);
  return options;
}

async function loadShifts() {
  return api(buildShiftQuery());
}

function renderShifts(rows) {
  if (!rows.length) {
    els.shiftsTable.innerHTML = `<p class="empty">No open shifts. Run auto-create or seed demo.</p>`;
    return;
  }
  els.shiftsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Setting</th><th>State</th><th>County</th><th>Role</th><th>Starts</th><th>Pay</th><th>Actions</th></tr></thead>
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
            <td>
              <button class="btn small" data-rank="${row.offer_id}">Rank</button>
              <button class="btn small" data-schedule="${row.offer_id}">Edit schedule</button>
              <button class="btn small" data-notify="${row.offer_id}">Notify top</button>
              <button class="btn small" data-notify-matched="${row.offer_id}">Notify matched</button>
              <button class="btn small" data-cascade="${row.offer_id}">Cascade next</button>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  els.shiftsTable.querySelectorAll("[data-rank]").forEach((btn) => {
    btn.addEventListener("click", () => previewRank(btn.dataset.rank));
  });
  els.shiftsTable.querySelectorAll("[data-schedule]").forEach((btn) => {
    btn.addEventListener("click", () => openScheduleEditor(btn.dataset.schedule));
  });
  els.shiftsTable.querySelectorAll("[data-notify]").forEach((btn) => {
    btn.addEventListener("click", () => notifyOffer(btn.dataset.notify));
  });
  els.shiftsTable.querySelectorAll("[data-notify-matched]").forEach((btn) => {
    btn.addEventListener("click", () => notifyMatchedOffer(btn.dataset.notifyMatched));
  });
  els.shiftsTable.querySelectorAll("[data-cascade]").forEach((btn) => {
    btn.addEventListener("click", () => cascadeOffer(btn.dataset.cascade));
  });
}

function fmtPct(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function demoOfferStatusLabel(row) {
  if (row.compliance_lock_status && row.compliance_lock_status !== "BROADCASTING") {
    return row.compliance_lock_status;
  }
  if (row.loaded) return row.compliance_lock_status || "LOADED";
  return "MISSING";
}

function demoOfferLockTestable(row) {
  return Boolean(row.offer_id && row.loaded && row.compliance_lock_status === "BROADCASTING");
}

function demoOfferResettable(row) {
  return Boolean(row.resettable || (row.offer_id && row.compliance_lock_status && row.compliance_lock_status !== "BROADCASTING"));
}

function resolveDemoAdminActions(demoGates, adminActionsOverride) {
  if (Array.isArray(adminActionsOverride) && adminActionsOverride.length) {
    return adminActionsOverride;
  }
  return demoGates?.demo_admin_actions || [];
}

function renderDemoGatesPanel(container, demoGates, listClassName, adminActionsOverride) {
  if (!container) return;
  if (!demoGates) {
    container.innerHTML = "";
    container.classList.add("hidden");
    return;
  }
  const activeLine = (demoGates.active_gates || []).length
    ? demoGates.active_gates.join(", ")
    : "none";
  const adminActions = resolveDemoAdminActions(demoGates, adminActionsOverride);
  const adminActionCount = demoGates.demo_admin_action_count ?? adminActions.length ?? 0;
  const adminActionsListClass = String(listClassName || "").replace(
    "-gates-list",
    "-admin-actions-list"
  );
  const adminActionsHtml = adminActions.length
    ? `
    <div class="panel-subhead">
      <h4>Demo admin actions</h4>
      <p class="muted">${adminActionCount} cataloged actions return embedded demo_gates on the response field shown.</p>
    </div>
    <ul class="demo-admin-actions-list ${adminActionsListClass}">
      ${adminActions.map((row) => `
        <li>
          <strong>${row.action}</strong> — ${row.endpoint} → ${row.field}
        </li>`).join("")}
    </ul>`
    : "";
  container.innerHTML = `
    <div class="panel-head">
      <h3>Demo confirmation gates</h3>
      <p class="muted">${demoGates.health_label} (${demoGates.health_status}) · ${demoGates.gate_count} gates · ${adminActionCount} admin actions · active: ${activeLine}</p>
    </div>
    <ul class="${listClassName}">
      ${(demoGates.gates || []).map((row) => `
        <li class="${row.active ? "active" : "inactive"}">
          <strong>${row.action}</strong> (${row.id}) — ${String(row.confirm_when || "").replace(/_/g, " ")} — ${row.active ? "active now" : "inactive"}
        </li>`).join("")}
    </ul>${adminActionsHtml}`;
  container.classList.remove("hidden");
}

function renderDeployDemoGates(demoGates, adminActions) {
  renderDemoGatesPanel(els.deployDemoGates, demoGates, "deploy-demo-gates-list", adminActions);
}

function renderDemoGates(demoGates, adminActions) {
  renderDemoGatesPanel(els.demoDemoGates, demoGates, "demo-demo-gates-list", adminActions);
}

function renderDeployChecklist(data) {
  const summary = data.summary;
  els.deploySummary.innerHTML = `
    <div class="stat-card">
      <span class="label">Ready</span>
      <strong>${summary.ready}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Warnings</span>
      <strong>${summary.warnings}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Blocked</span>
      <strong>${summary.blocked}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Live SMS</span>
      <strong>${summary.live_sms_ready ? "READY" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">MD launch</span>
      <strong>${summary.maryland_launch_ready ? "READY" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Perfection</span>
      <strong>${summary.production_perfection_ready ? "READY" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Ceremony</span>
      <strong>${summary.production_launch_ceremony_ready ? "READY" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Go-live</span>
      <strong>${summary.production_go_live_record_ready ? "SEALED" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Attestation</span>
      <strong>${summary.production_launch_attestation_ready ? "ATTESTED" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Perfection seal</span>
      <strong>${summary.production_launch_perfection_ready ? "SEALED" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Archive</span>
      <strong>${summary.production_launch_archive_ready ? "ARCHIVED" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Finale</span>
      <strong>${summary.production_launch_finale_ready ? "COMPLETE" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Verified</span>
      <strong>${summary.production_launch_bundle_verified_ready ? "VERIFIED" : "NOT YET"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Demo health</span>
      <strong>${summary.demo_health_label || "—"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Demo present</span>
      <strong>${summary.demo_present_facility_count ?? "—"} / ${summary.demo_expected_facility_count ?? "—"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Demo broadcasting</span>
      <strong>${summary.demo_broadcasting_count ?? "—"} / ${summary.demo_expected_facility_count ?? "—"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Walkthrough intact</span>
      <strong>${summary.demo_walkthrough_intact == null ? "—" : summary.demo_walkthrough_intact ? "YES" : "NO"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Active gates</span>
      <strong>${(summary.demo_active_gates || []).length ? summary.demo_active_gates.join(", ") : summary.demo_walkthrough_intact == null ? "—" : "none"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Demo gates</span>
      <strong>${summary.demo_gate_count ?? "—"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Admin actions</span>
      <strong>${summary.demo_admin_action_count ?? "—"}</strong>
    </div>`;

  els.deployTwilioSteps.innerHTML = (data.twilio_console_steps || [])
    .map((step) => `<li>${step}</li>`)
    .join("");

  els.deployDemoSteps.innerHTML = (data.demo_steps || [])
    .map((step) => `<li>${step}</li>`)
    .join("");

  if (els.deployMarylandSteps) {
    els.deployMarylandSteps.innerHTML = (data.maryland_platform_steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }

  const mdProduction = data.maryland_production_runbook;
  if (els.deployMarylandProductionSummary && mdProduction) {
    const mdSummary = mdProduction.summary || {};
    els.deployMarylandProductionSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">MD production</span>
        <strong>${mdProduction.production_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Checks ready</span>
        <strong>${mdSummary.ready ?? "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Warnings</span>
        <strong>${mdSummary.warnings ?? "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Blocked</span>
        <strong>${mdSummary.blocked ?? "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Live scrapers</span>
        <strong>${mdSummary.live_scrapers_live_count ?? "—"} / 5</strong>
      </div>`;
  }
  if (els.deployMarylandProductionSteps) {
    els.deployMarylandProductionSteps.innerHTML = (data.maryland_production_steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }

  if (els.deployLiveSmsSteps) {
    els.deployLiveSmsSteps.innerHTML = (data.live_sms_production_steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }

  const launchCapstone = data.maryland_launch_capstone;
  if (els.deployMarylandLaunchSummary && launchCapstone) {
    const launchSummary = launchCapstone.summary || {};
    els.deployMarylandLaunchSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Launch capstone</span>
        <strong>${launchCapstone.launch_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">MD production</span>
        <strong>${launchCapstone.maryland_production_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Live SMS</span>
        <strong>${launchCapstone.twilio_sms_production_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Live scrapers</span>
        <strong>${launchSummary.live_scrapers_live_count ?? "—"} / 5</strong>
      </div>`;
  }
  if (els.deployMarylandLaunchSteps) {
    els.deployMarylandLaunchSteps.innerHTML = (data.maryland_launch_capstone_steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }

  renderProductionPerfectionCapstone(data.production_perfection_capstone);
  renderProductionLaunchCeremony(data.production_launch_ceremony);
  renderProductionGoLiveRecord(data.production_go_live_record);
  renderProductionLaunchAttestation(data.production_launch_attestation);
  renderProductionLaunchPerfectionSeal(data.production_launch_perfection_seal);
  renderProductionLaunchArchive(data.production_launch_archive);
  renderProductionLaunchFinale(data.production_launch_finale);
  renderProductionLaunchBundleVerification(data.production_launch_bundle_verification);

  els.deployExportSteps.innerHTML = (data.export_steps || [])
    .map((step) => `<li>${step}</li>`)
    .join("");

  els.deployChecklist.innerHTML = (data.items || []).map((row) => `
    <div class="deploy-item">
      <strong>${row.title}</strong>${badge(row.status.toUpperCase())}
      <p>${row.detail}</p>
      ${row.action ? `<p><em>Action:</em> ${row.action}</p>` : ""}
    </div>`).join("");

  renderDeployDemoGates(data.demo_gates, data.demo_admin_actions);
}

async function runDemoLockSmoke(offerId = null, facilityName = "the first broadcasting demo shift") {
  if (!(await confirmDemoReadyLockTest(facilityName))) {
    showToast("Lock test cancelled — shift left broadcasting", true);
    return;
  }
  const path = offerId
    ? `/api/seed/demo-lock-smoke?offer_id=${encodeURIComponent(offerId)}`
    : "/api/seed/demo-lock-smoke";
  const data = await api(path, { method: "POST" });
  if (data.ok) {
    logOps(
      `Demo lock smoke — ${data.facility_name} locked by ${data.clinician_email} · placement ${data.placement_id}`,
    );
    showToast(`Lock OK — ${data.facility_name} (${data.clinician_email})`);
    if (data.offer_row?.resettable) {
      logOps(`Locked row ready for Reset — ${data.offer_row.facility_name} (${data.offer_row.compliance_lock_status})`);
    }
  } else {
    logOps(`Demo lock smoke failed — ${data.status}: ${data.message}`);
    showToast(data.message || `Lock smoke failed (${data.status})`, true);
  }
  renderDemoStatus(data.demo_status);
  await refreshAll();
}

function wireDemoLockSmokeButtons() {
  els.demoOffersTable?.querySelectorAll(".demo-lock-smoke-offer-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await runDemoLockSmoke(button.dataset.offerId, button.dataset.facilityName || "this shift");
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });
}

async function runDemoNotifyMatched(offerId, facilityName = "this shift") {
  if (!(await confirmDemoReadyNotifyMatched(facilityName))) {
    showToast("Notify matched cancelled — no push alerts sent", true);
    return;
  }
  const data = await api(`/api/seed/demo-notify-matched?offer_id=${encodeURIComponent(offerId)}`, {
    method: "POST",
  });
  logOps(`Demo notify — ${data.facility_name}: ${data.matched_push_alerts_sent} matched push alert(s)`);
  showToast(data.message || `Sent ${data.matched_push_alerts_sent} matched push alert(s)`);
  renderDemoStatus(data.demo_status);
  await refreshAll();
}

function wireDemoNotifyMatchedButtons() {
  els.demoOffersTable?.querySelectorAll(".demo-notify-matched-offer-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await runDemoNotifyMatched(button.dataset.offerId, button.dataset.facilityName || "this shift");
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });
}

async function runDemoResetOffer(offerId, facilityName = "this shift") {
  if (!(await confirmDemoReadyResetOffer(facilityName))) {
    showToast("Per-row reset cancelled — locked shift left unchanged", true);
    return;
  }
  const data = await api(`/api/seed/demo-reset-offer?offer_id=${encodeURIComponent(offerId)}`, {
    method: "POST",
  });
  logOps(`Demo reset — ${data.facility_name}: ${data.message}`);
  showToast(data.message);
  if (data.offer_row?.loaded) {
    logOps(
      `Reset row broadcasting — ${data.offer_row.facility_name} (${data.offer_row.compliance_lock_status})`,
    );
  }
  renderDemoStatus(data.status);
  await refreshAll();
}

function wireDemoResetOfferButtons() {
  els.demoOffersTable?.querySelectorAll(".demo-reset-offer-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await runDemoResetOffer(button.dataset.offerId, button.dataset.facilityName || "this shift");
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });
}

function renderDemoHealth(health) {
  if (!els.demoHealthBadge) return;
  if (!health) {
    els.demoHealthBadge.classList.add("hidden");
    return;
  }
  els.demoHealthBadge.className = `demo-health-badge ${health.status}`;
  const issues = (health.issues || []).length
    ? `<ul>${health.issues.map((issue) => `<li>${issue}</li>`).join("")}</ul>`
    : "";
  const facilityCounts =
    health.present_facility_count != null && health.expected_facility_count != null
      ? `<p class="demo-health-facilities">${health.present_facility_count}/${health.expected_facility_count} present · ${health.broadcasting_facility_count ?? "—"}/${health.expected_facility_count} broadcasting</p>`
      : "";
  const gateHints = (health.gate_hints || []).length
    ? `<ul class="demo-health-gates">${health.gate_hints.map((hint) => `<li>${hint}</li>`).join("")}</ul>`
    : "";
  const activeGates = (health.active_gates || []).length
    ? `<p class="demo-health-active-gates"><strong>Active gates:</strong> ${health.active_gates.join(", ")}</p>`
    : "";
  const gateCount = health.gate_count != null
    ? `<p class="demo-health-gate-count"><strong>Confirmation gates:</strong> ${health.gate_count} configured</p>`
    : "";
  const adminActionCount = health.demo_admin_action_count != null
    ? `<p class="demo-health-admin-actions"><strong>Demo admin actions:</strong> ${health.demo_admin_action_count} cataloged</p>`
    : "";
  els.demoHealthBadge.innerHTML = `
    <strong>${health.label}</strong>
    <p>${health.summary}</p>
    ${facilityCounts}
    ${gateCount}
    ${adminActionCount}
    ${gateHints}
    ${activeGates}
    ${issues}`;
  els.demoHealthBadge.classList.remove("hidden");
}

function renderDemoStatus(data) {
  lastDemoHealth = data.health || null;
  renderDemoHealth(data.health);
  renderDemoGates(data.demo_gates, data.demo_admin_actions);
  els.demoSummary.innerHTML = `
    <div class="stat-card">
      <span class="label">Loaded</span>
      <strong>${data.loaded ? "YES" : "PARTIAL"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Facilities</span>
      <strong>${data.present_facility_count ?? data.facility_count} / ${data.expected_facility_count}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Broadcasting</span>
      <strong>${data.facility_count} / ${data.expected_facility_count}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Demo clinicians</span>
      <strong>${(data.clinicians || []).length}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Portal logins</span>
      <strong>${data.portal_account_count ?? 0}${data.portal_ready ? " ✓" : ""}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Push subs</span>
      <strong>${data.push_subscription_count ?? 0}${data.push_subscriptions_ready ? " ✓" : ""}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Demo password</span>
      <strong>${data.demo_portal_password_hint || "SecretPass1"}</strong>
    </div>
    <div class="stat-card">
      <span class="label">Admin actions</span>
      <strong>${(data.demo_admin_action_count ?? data.health?.demo_admin_action_count ?? (data.demo_admin_actions || []).length) || "n/a"}</strong>
    </div>`;

  const offers = data.offers || [];
  els.demoOffersTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Facility</th>
          <th>State</th>
          <th>Type</th>
          <th>Role</th>
          <th>Matched</th>
          <th>Push ready</th>
          <th>Status</th>
          <th>Portal link</th>
          <th>Demo as</th>
          <th>Lock test</th>
          <th>Notify</th>
          <th>Reset</th>
        </tr>
      </thead>
      <tbody>
        ${offers.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.state || "—"}</td>
            <td>${row.facility_type || "—"}</td>
            <td>${row.shift_role || "—"}</td>
            <td>${row.matched_clinician_count}</td>
            <td>${row.push_ready_count}</td>
            <td>${badge(demoOfferStatusLabel(row))}</td>
            <td>${row.portal_deep_link ? `<a href="${row.portal_deep_link}" target="_blank" rel="noopener">Open</a>` : "—"}</td>
            <td>${row.demo_clinician_email || "—"}</td>
            <td>${demoOfferLockTestable(row) ? `<button class="btn ghost demo-lock-smoke-offer-btn" type="button" data-offer-id="${row.offer_id}" data-facility-name="${row.facility_name}">Lock test</button>` : "—"}</td>
            <td>${demoOfferLockTestable(row) ? `<button class="btn ghost demo-notify-matched-offer-btn" type="button" data-offer-id="${row.offer_id}" data-facility-name="${row.facility_name}">Notify</button>` : "—"}</td>
            <td>${demoOfferResettable(row) ? `<button class="btn ghost demo-reset-offer-btn" type="button" data-offer-id="${row.offer_id}" data-facility-name="${row.facility_name}">Reset</button>` : "—"}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  wireDemoLockSmokeButtons();
  wireDemoNotifyMatchedButtons();
  wireDemoResetOfferButtons();

  const clinicians = data.clinicians || [];
  els.demoCliniciansTable.innerHTML = clinicians.length ? `
    <table>
      <thead>
        <tr>
          <th>Email</th>
          <th>Name</th>
          <th>State</th>
          <th>Credential</th>
          <th>Portal</th>
          <th>Push</th>
        </tr>
      </thead>
      <tbody>
        ${clinicians.map((row) => `
          <tr>
            <td>${row.email}</td>
            <td>${row.full_name}</td>
            <td>${row.state}</td>
            <td>${row.credential_type}</td>
            <td>${row.portal_enabled ? badge("READY") : badge("MISSING")}</td>
            <td>${row.push_enabled ? badge("READY") : badge("MISSING")}</td>
          </tr>`).join("")}
      </tbody>
    </table>` : `<p class="muted">No @offercare.demo clinicians loaded yet.</p>`;

  els.demoNextSteps.innerHTML = (data.next_steps || [])
    .map((step) => `<li>${step}</li>`)
    .join("");
}

function renderIntegrations(data) {
  const channels = [
    { label: "Twilio SMS", row: data.twilio },
    { label: "Email alerts", row: data.email },
    { label: "Web Push", row: data.push },
    { label: "VMS outbound", row: data.vms },
  ];
  els.integrationsGrid.innerHTML = channels.map(({ label, row }) => {
    const status = row.live_ready ? "LIVE READY" : row.dry_run ? "DRY RUN" : "OFFLINE";
    let extra = "";
    if (label.startsWith("Twilio")) {
      extra = [
        `Signatures: ${row.signature_validation ? "on" : "off"}`,
        row.inbound_webhook_url ? `Webhook: ${row.inbound_webhook_url}` : "Webhook: not set",
      ].join(" · ");
    } else if (label.startsWith("Email")) {
      extra = `From: ${row.from_address || "not set"} · SMTP: ${row.smtp_host || "not set"}`;
    } else if (label.startsWith("Web Push")) {
      extra = `VAPID: ${row.vapid_public_key ? "configured" : "not set"}`;
    } else {
      extra = `URL: ${row.submission_url || "not set"}`;
    }
    return `
      <div class="integration-card">
        <strong>${label}</strong>
        ${badge(status.replace(" ", "_"))}
        <p class="meta">${row.detail}</p>
        <p class="meta">${extra}</p>
      </div>`;
  }).join("");
}

async function loadTwilioSmsProductionPanel() {
  const data = await api("/api/integrations/twilio/go-live-profile");
  if (els.twilioSmsProductionSummary) {
    const summary = data.summary || {};
    els.twilioSmsProductionSummary.innerHTML = `
      <div class="stat-card">
        <span class="label">Twilio production</span>
        <strong>${data.production_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Live SMS</span>
        <strong>${data.live_sms_ready ? "READY" : "NOT YET"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Checks ready</span>
        <strong>${summary.ready ?? "—"}</strong>
      </div>
      <div class="stat-card">
        <span class="label">Reply keyword</span>
        <strong>${summary.reply_keyword || "YES"}</strong>
      </div>`;
  }
  if (els.twilioSmsProductionSteps) {
    els.twilioSmsProductionSteps.innerHTML = (data.steps || [])
      .map((step) => `<li>${step}</li>`)
      .join("");
  }
  return data;
}

async function runTwilioLockReplySmoke() {
  const data = await api("/api/integrations/twilio/lock-reply-smoke", { method: "POST", body: JSON.stringify({}) });
  if (data.ok) {
    showToast(`Lock reply smoke OK — ${data.facility_name} locked (${data.phone_number})`);
    logOps(`Twilio lock reply smoke — ${data.facility_name} · placement ${data.placement_id}`);
  } else {
    showToast(data.message || `Lock reply smoke failed (${data.status})`, true);
  }
  await refreshPendingAndStats();
}

async function copyTwilioGoLiveEnv() {
  const data = await api("/api/integrations/twilio/go-live-profile");
  await navigator.clipboard.writeText(data.env_snippet);
  showToast(`Copied Twilio go-live .env (${data.production_ready ? "READY" : "NOT YET"})`);
}

async function testTwilioSmsDelivery() {
  const phone = window.prompt("Test SMS phone number (E.164)", "+14105550001");
  if (!phone) return;
  const data = await api("/api/integrations/test/sms", {
    method: "POST",
    body: JSON.stringify({ phone_number: phone, message: "OfferCare.ai Twilio production test" }),
  });
  showToast(`Test SMS — ${data.status} (${data.mode})`);
}

function renderSniperScores(rows) {
  if (!rows.length) {
    els.sniperTable.innerHTML = `<p class="empty">No clinicians yet. Seed demo or wait for applications.</p>`;
    return;
  }
  const sorted = [...rows].sort((a, b) => b.response_propensity - a.response_propensity);
  els.sniperTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Clinician</th><th>Status</th><th>H</th><th>T</th><th>SMS total</th><th>YES locks</th><th>Recent SMS</th>
        </tr>
      </thead>
      <tbody>
        ${sorted.map((row) => `
          <tr>
            <td>${row.full_name}<br><span class="muted">${row.phone_number}</span></td>
            <td>${badge(row.license_status)}</td>
            <td><span class="score-bar">${fmtPct(row.response_propensity)}</span></td>
            <td><span class="score-bar">${Number(row.fatigue_score).toFixed(2)}</span></td>
            <td>${row.notifications_total}</td>
            <td>${row.acceptances_total}</td>
            <td>${row.notifications_recent}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderPlacements(rows) {
  if (!rows.length) {
    els.placementsTable.innerHTML = `<p class="empty">No placements yet. Lock a shift via SMS YES flow.</p>`;
    return;
  }
  els.placementsTable.innerHTML = `
    <table>
      <thead><tr><th>Facility</th><th>Unit</th><th>Clinician</th><th>Rate</th><th>VMS</th><th>Actions</th></tr></thead>
      <tbody>
        ${rows.map((row) => `
          <tr>
            <td>${row.facility_name}</td>
            <td>${row.clinical_unit}</td>
            <td>${row.clinician_name || row.assigned_clinician_id}</td>
            <td>$${Number(row.hourly_bill_rate).toFixed(2)}/hr</td>
            <td>${badge(row.vms_submission_status)} ${row.vms_external_ref ? `<br><span class="muted">${row.vms_external_ref}</span>` : ""}</td>
            <td>
              ${row.vms_submission_status === "PENDING"
                ? `<button class="btn small" data-submit-vms="${row.placement_id}">Submit VMS</button>`
                : ""}
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  els.placementsTable.querySelectorAll("[data-submit-vms]").forEach((btn) => {
    btn.addEventListener("click", () => submitPlacement(btn.dataset.submitVms));
  });
}

async function verifyClinician(providerId, action) {
  try {
    await api(`/api/clinicians/${providerId}/verify`, {
      method: "POST",
      body: JSON.stringify({ action, reviewer: "admin_dashboard" }),
    });
    showToast(`Clinician ${action.toLowerCase()}d`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function previewRank(offerId) {
  try {
    const data = await api(`/shift-sniper/offers/${offerId}/rank`);
    els.rankBody.textContent = JSON.stringify(data, null, 2);
    els.rankDialog.showModal();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openScheduleEditor(offerId) {
  try {
    const row = await api(`/api/shifts/offers/${offerId}`);
    scheduleEditOfferId = offerId;
    els.scheduleDialogMeta.textContent = `${row.facility_name} · ${row.shift_role} · $${Number(row.hourly_pay_rate).toFixed(2)}/hr`;
    els.scheduleStartInput.value = toDatetimeLocalValue(row.shift_starts_at);
    els.scheduleEndInput.value = toDatetimeLocalValue(row.shift_ends_at);
    els.scheduleDialog.showModal();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function saveScheduleEdit(event) {
  event.preventDefault();
  if (!scheduleEditOfferId) return;
  const shift_starts_at = fromDatetimeLocalValue(els.scheduleStartInput.value);
  const shift_ends_at = fromDatetimeLocalValue(els.scheduleEndInput.value);
  if (!shift_starts_at || !shift_ends_at) {
    showToast("Enter valid start and end times", true);
    return;
  }
  try {
    await api(`/api/shifts/offers/${scheduleEditOfferId}/schedule`, {
      method: "PATCH",
      body: JSON.stringify({ shift_starts_at, shift_ends_at }),
    });
    els.scheduleDialog.close();
    scheduleEditOfferId = null;
    showToast("Shift schedule updated");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function notifyOffer(offerId) {
  try {
    const data = await api(`/shift-sniper/offers/${offerId}/notify`, {
      method: "POST",
      body: JSON.stringify({ max_recipients: 1, reply_keyword: "YES" }),
    });
    const top = data.ranked?.[0]?.full_name || "clinician";
    showToast(`Notified ${top} (dry-run if Twilio not configured)`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function notifyMatchedOffer(offerId) {
  try {
    const data = await api(`/api/shifts/offers/${offerId}/notify-matched`, { method: "POST" });
    const sent = data.matched_push_alerts_sent ?? 0;
    logOps(`Matched push sent for offer ${offerId} — ${sent} device(s)`);
    showToast(sent ? `Matched push sent to ${sent} device(s)` : "No matched clinicians with push enabled");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function cascadeOffer(offerId) {
  try {
    const data = await api(`/shift-sniper/offers/${offerId}/cascade`, {
      method: "POST",
      body: JSON.stringify({ reply_keyword: "YES", force: true }),
    });
    showToast(`${data.status}: ${data.message}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function submitPlacement(placementId) {
  try {
    const data = await api(`/api/vms/placements/${placementId}/submit`, { method: "POST" });
    showToast(`VMS ${data.status}: ${data.external_ref || data.message}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

function setConnectionStatus(state, detail = "") {
  const node = els.connectionStatus;
  if (!node) return;
  node.classList.remove("hidden", "ok", "warn", "fail");
  if (state === "hidden") {
    node.classList.add("hidden");
    return;
  }
  if (state === "connected") {
    node.textContent = detail || "Connected to API";
    node.classList.add("ok");
    return;
  }
  if (state === "loading") {
    node.textContent = detail || "Refreshing…";
    node.classList.add("warn");
    return;
  }
  node.textContent = detail || "Not connected";
  node.classList.add("fail");
}

async function refreshAll() {
  if (!getKey()) {
    setConnectionStatus("fail", "Not connected — paste admin key");
    throw new Error("Admin API key missing — click Disconnect and sign in again.");
  }
  const refreshLabel = els.refreshBtn?.textContent || "Refresh all";
  if (els.refreshBtn) {
    els.refreshBtn.disabled = true;
    els.refreshBtn.textContent = "Refreshing…";
  }
  setConnectionStatus("loading");
  try {
  const requests = await Promise.allSettled([
    api("/api/clinicians/pending"),
    api("/api/shifts/filters"),
    loadShifts(),
    api("/api/vms/placements?limit=50"),
    api("/api/integrations/status"),
    api("/api/integrations/live-scrapers"),
    api("/api/deploy/checklist?lite=true"),
    api("/api/seed/demo-status"),
    api("/shift-sniper/scores"),
    api("/api/ops/production-dashboard"),
    api("/api/ops/metrics"),
    api("/api/ops/audit?limit=25"),
    api("/api/ops/cascade-worker/status"),
    api("/api/ops/staffing-scheduler/status"),
    api("/api/ops/compliance-scheduler/status"),
  ]);

  const pick = (index, fallback = null) =>
    requests[index]?.status === "fulfilled" ? requests[index].value : fallback;

  const pending = pick(0, []);
  const shiftFilters = pick(1, {
    states: [],
    counties: [],
    facility_types: [],
    shift_roles: [],
  });
  const shifts = pick(2, []);
  const placements = pick(3, []);
  const integrations = pick(4, null);
  const liveScrapers = pick(5, null);
  const deployChecklist = pick(6, null);
  const demoStatus = pick(7, null);
  const sniperScores = pick(8, []);
  const productionOps = pick(9, null);
  const opsMetrics = pick(10, null);
  const auditEvents = pick(11, []);
  const cascadeWorker = pick(12, null);
  const staffingScheduler = pick(13, null);
  const complianceScheduler = pick(14, null);

  requests.forEach((result, index) => {
    if (result.status === "rejected") {
      console.warn("Admin refresh partial failure", index, result.reason);
    }
  });
  if (requests[6]?.status === "rejected") {
    logOps(`Deploy checklist unavailable — ${requests[6].reason?.message || "error"}`);
  }

  populateShiftFilters(shiftFilters);
  renderStats(pending, shifts, placements, productionOps?.metrics || opsMetrics);
  renderProductionOpsDashboard(productionOps);
  if (!productionOps?.workers?.cascade) {
    renderCascadeWorker(cascadeWorker);
    renderStaffingScheduler(staffingScheduler);
    renderComplianceScheduler(complianceScheduler);
    renderAuditLog(auditEvents);
  }
  if (deployChecklist) {
    renderDeployChecklist(deployChecklist);
  }
  renderDemoStatus(demoStatus);
  renderIntegrations(integrations);
  renderLiveScrapers(liveScrapers);
  await loadTwilioSmsProductionPanel();
  renderSniperScores(sniperScores);
  renderPending(pending);
  renderShifts(shifts);
  renderPlacements(placements);
  await loadInfrastructureReadiness();
  await loadVettedCareDashboard();
  await loadComplianceDashboard();
  await loadOutreachDashboard();
  await loadWorkerInflowDashboard();
    setConnectionStatus("connected", `Connected · ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    setConnectionStatus("fail", "Refresh failed — check API window");
    throw error;
  } finally {
    if (els.refreshBtn) {
      els.refreshBtn.disabled = false;
      els.refreshBtn.textContent = refreshLabel;
    }
  }
}

async function connect() {
  if (typeof window.offercareAdminConnect === "function") {
    await window.offercareAdminConnect();
    return;
  }
  const key = els.apiKeyInput.value.trim();
  if (!key) {
    els.gateError.textContent = "Admin API key is required.";
    els.gateError.classList.remove("hidden");
    return;
  }
  setKey(key);
  const connectLabel = els.connectBtn.textContent;
  els.connectBtn.disabled = true;
  els.connectBtn.textContent = "Connecting…";
  els.gateError.classList.add("hidden");
  let opened = false;
  try {
    await api("/api/clinicians/pending");
    els.gate.classList.add("hidden");
    els.app.classList.remove("hidden");
    opened = true;
    await refreshAll();
    showToast("Connected to VettedCare.ai admin API");
  } catch (error) {
    setKey("");
    if (opened) {
      els.app.classList.add("hidden");
      els.gate.classList.remove("hidden");
    }
    const detail = String(error?.message || error || "unknown error");
    if (detail.includes("admin_unauthorized")) {
      els.gateError.textContent =
        "Connection failed: admin key rejected. Copy ADMIN_API_KEY from .env exactly, restart start-api.bat, then try again.";
    } else {
      els.gateError.textContent = `Connection failed: ${detail}`;
    }
    els.gateError.classList.remove("hidden");
  } finally {
    els.connectBtn.disabled = false;
    els.connectBtn.textContent = connectLabel;
  }
}

function disconnect() {
  if (typeof window.offercareAdminDisconnect === "function") {
    window.offercareAdminDisconnect();
  } else {
    setKey("");
    els.app.classList.add("hidden");
    els.gate.classList.remove("hidden");
    els.apiKeyInput.value = "";
  }
  setConnectionStatus("hidden");
}

function logOps(message) {
  const stamp = new Date().toLocaleTimeString();
  els.opsLog.textContent = `[${stamp}] ${message}\n` + els.opsLog.textContent;
}

els.disconnectBtn?.addEventListener("click", disconnect);
els.connectBtn?.addEventListener("click", () => connect().catch((error) => {
  if (els.gateError) {
    els.gateError.textContent = String(error?.message || error || "Connection failed");
    els.gateError.classList.remove("hidden");
  }
}));
els.refreshBtn?.addEventListener("click", () =>
  refreshAll()
    .then(() => showToast("Dashboard refreshed"))
    .catch((e) => showToast(e.message, true)),
);
els.cascadeWorkerTickBtn?.addEventListener("click", () => runCascadeWorkerTick().catch((e) => showToast(e.message, true)));
els.refreshProductionOpsBtn?.addEventListener("click", () => refreshProductionOpsDashboard().catch((e) => showToast(e.message, true)));
els.runProductionPerfectionCheckBtn?.addEventListener("click", () => runProductionPerfectionCheck().catch((e) => showToast(e.message, true)));
els.copyProductionPerfectionEnvBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/deploy/production-perfection-capstone");
    await navigator.clipboard.writeText(data.env_snippet);
    showToast(`Copied production perfection .env (${data.production_perfection_ready ? "READY" : "NOT YET"})`);
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadProductionOpsDashboardBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile(
      "/api/ops/production-dashboard.json",
      "offercare-production-ops-dashboard.json",
    );
    showToast("Exported production ops dashboard (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadProductionPerfectionCapstoneBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile(
      "/api/deploy/production-perfection-capstone.json",
      "offercare-production-perfection-capstone.json",
    );
    showToast("Exported production perfection capstone (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.runProductionLaunchCeremonyBtn?.addEventListener("click", () => runProductionLaunchCeremony().catch((e) => showToast(e.message, true)));
els.sealProductionGoLiveRecordBtn?.addEventListener("click", () => sealProductionGoLiveRecord().catch((e) => showToast(e.message, true)));
els.downloadProductionGoLiveRecordJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-go-live-record.json",
      "offercare-production-go-live-record.json",
    );
    showToast("Downloaded production go-live record JSON");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.attestProductionLaunchBtn?.addEventListener("click", () => attestProductionLaunch().catch((e) => showToast(e.message, true)));
els.downloadProductionLaunchAttestationMdBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-launch-attestation.md",
      "offercare-production-launch-attestation.md",
    );
    showToast("Downloaded production launch attestation markdown");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadProductionLaunchAttestationJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-launch-attestation.json",
      "offercare-production-launch-attestation.json",
    );
    showToast("Downloaded production launch attestation JSON");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.sealProductionLaunchPerfectionBtn?.addEventListener("click", () => sealProductionLaunchPerfection().catch((e) => showToast(e.message, true)));
els.downloadProductionLaunchPerfectionSealJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-launch-perfection-seal.json",
      "offercare-production-launch-perfection-seal.json",
    );
    showToast("Downloaded production launch perfection seal JSON");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.archiveProductionLaunchBtn?.addEventListener("click", () => archiveProductionLaunch().catch((e) => showToast(e.message, true)));
els.downloadProductionLaunchArchiveJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-launch-archive.json",
      "offercare-production-launch-archive.json",
    );
    showToast("Downloaded production launch archive JSON");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.runProductionLaunchFinaleBtn?.addEventListener("click", () => runProductionLaunchFinale().catch((e) => showToast(e.message, true)));
els.downloadProductionLaunchFinaleJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-launch-finale.json",
      "offercare-production-launch-finale.json",
    );
    showToast("Downloaded production launch finale JSON");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.verifyProductionLaunchBundleBtn?.addEventListener("click", () => verifyProductionLaunchBundle().catch((e) => showToast(e.message, true)));
els.downloadProductionLaunchPerfectionManifestJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAttachment(
      "/api/deploy/production-launch-perfection-manifest.json",
      "offercare-production-launch-perfection-manifest.json",
    );
    showToast("Downloaded production launch perfection manifest JSON");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadProductionLaunchCeremonyMdBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile(
      "/api/deploy/production-launch-ceremony.md",
      "offercare-production-launch-ceremony.md",
    );
    showToast("Downloaded launch ceremony sign-off (.md)");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.downloadProductionLaunchCeremonyJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile(
      "/api/deploy/production-launch-ceremony.json",
      "offercare-production-launch-ceremony.json",
    );
    showToast("Exported production launch ceremony (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});
els.staffingVmsTickBtn?.addEventListener("click", () => runStaffingVmsTick().catch((e) => showToast(e.message, true)));
els.staffingJobBoardTickBtn?.addEventListener("click", () => runStaffingJobBoardTick().catch((e) => showToast(e.message, true)));
els.complianceSchedulerTickBtn?.addEventListener("click", () => runComplianceSchedulerTick().catch((e) => showToast(e.message, true)));
els.applyShiftFiltersBtn?.addEventListener("click", async () => {
  try {
    const shifts = await loadShifts();
    renderShifts(shifts);
    showToast(`Showing ${shifts.length} open shifts`);
  } catch (error) {
    showToast(error.message, true);
  }
});
els.closeRankDialog?.addEventListener("click", () => els.rankDialog.close());
els.closeComplianceDialog?.addEventListener("click", () => els.complianceDialog.close());
els.runComplianceMonitorBtn?.addEventListener("click", () => runComplianceMonitor().catch((e) => showToast(e.message, true)));
els.runVettedSafetyBtn?.addEventListener("click", () => runVettedSafetyCycle().catch((e) => showToast(e.message, true)));
els.syncVettedStatusBtn?.addEventListener("click", () => syncVettedStatuses().catch((e) => showToast(e.message, true)));
els.refreshVettedBtn?.addEventListener("click", () => loadVettedCareDashboard().catch((e) => showToast(e.message, true)));
els.refreshInfraBtn?.addEventListener("click", () => loadInfrastructureReadiness().catch((e) => showToast(e.message, true)));
els.scanCrisisSignalsBtn?.addEventListener("click", () => scanCrisisSignals().catch((e) => showToast(e.message, true)));
els.scanJobBoardsBtn?.addEventListener("click", () => scanJobBoardCrisis().catch((e) => showToast(e.message, true)));
els.ingestVmsShiftsBtn?.addEventListener("click", () => ingestVmsShifts().catch((e) => showToast(e.message, true)));
els.refreshComplianceBtn?.addEventListener("click", () => loadComplianceDashboard().then(() => showToast("Compliance dashboard refreshed")).catch((e) => showToast(e.message, true)));
els.runOutreachCampaignBtn?.addEventListener("click", () => runOutreachCampaign(false).catch((e) => showToast(e.message, true)));
els.sendOutreachCampaignBtn?.addEventListener("click", () => runOutreachCampaign(true).catch((e) => showToast(e.message, true)));
els.refreshOutreachBtn?.addEventListener("click", () => loadOutreachDashboard().then(() => showToast("Outreach dashboard refreshed")).catch((e) => showToast(e.message, true)));
els.refreshWorkerInflowBtn?.addEventListener("click", () => loadWorkerInflowDashboard().then(() => showToast("Worker inflow stats refreshed")).catch((e) => showToast(e.message, true)));
els.copyWorkerInflowLinkBtn?.addEventListener("click", () => copyWorkerInflowLink().catch((e) => showToast(e.message, true)));
els.closeScheduleDialog?.addEventListener("click", () => {
  scheduleEditOfferId = null;
  els.scheduleDialog?.close();
});
els.scheduleForm?.addEventListener("submit", (event) => {
  saveScheduleEdit(event).catch((error) => showToast(error.message, true));
});

els.scrapeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/maryland-hospitals", {
      method: "POST",
      body: JSON.stringify({ limit: 25 }),
    });
    logOps(`MD scrape — created ${data.created}, updated ${data.updated}`);
    showToast(`Scraped ${data.fetched} Maryland hospitals`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapePaBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/pennsylvania-hospitals", {
      method: "POST",
      body: JSON.stringify({ limit: 25 }),
    });
    logOps(`PA scrape — created ${data.created}, updated ${data.updated}`);
    showToast(`Scraped ${data.fetched} Pennsylvania hospitals`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapeDeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/delaware-hospitals", {
      method: "POST",
      body: JSON.stringify({ limit: 25 }),
    });
    logOps(`DE scrape — created ${data.created}, updated ${data.updated}`);
    showToast(`Scraped ${data.fetched} Delaware hospitals`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapeNjBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/new-jersey-hospitals", {
      method: "POST",
      body: JSON.stringify({ limit: 25 }),
    });
    logOps(`NJ scrape — created ${data.created}, updated ${data.updated}`);
    showToast(`Scraped ${data.fetched} New Jersey hospitals`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapeExpansionBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/expansion-states", {
      method: "POST",
      body: JSON.stringify({ limit: 25 }),
    });
    logOps(`PA+DE+NJ scrape — created ${data.created}, updated ${data.updated}`);
    showToast(`Scraped ${data.fetched} PA/DE/NJ hospitals`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapeNursingHomesBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/nursing-homes", {
      method: "POST",
      body: JSON.stringify({ limit: 25, state: "MD", auto_create_shifts: true }),
    });
    logOps(
      `MD nursing homes — created ${data.created}, updated ${data.updated}, shifts ${data.shifts_created}, matched push ${data.matched_push_alerts_sent ?? 0}`,
    );
    showToast(`Scraped ${data.fetched} Maryland nursing homes`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapeHomeHealthBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/home-health-agencies", {
      method: "POST",
      body: JSON.stringify({ limit: 25, state: "MD", auto_create_shifts: true }),
    });
    logOps(
      `MD home health — created ${data.created}, updated ${data.updated}, shifts ${data.shifts_created}`,
    );
    showToast(`Scraped ${data.fetched} Maryland home health agencies`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.scrapePostAcuteBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/scrape/post-acute-mid-atlantic", {
      method: "POST",
      body: JSON.stringify({ limit: 25, auto_create_shifts: true }),
    });
    logOps(
      `Post-acute scrape — SNF created ${data.nursing_homes.created}, HH created ${data.home_health.created}, shifts ${data.shifts_created}, matched push ${data.matched_push_alerts_sent ?? 0}`,
    );
    showToast(`Scraped ${data.fetched} nursing homes + home health agencies`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.autoShiftsBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/shifts/auto-create", {
      method: "POST",
      body: JSON.stringify({ limit: 25 }),
    });
    logOps(`Auto-create — ${data.offers_created} offers across ${data.facilities_processed} facilities`);
    showToast(`Created ${data.offers_created} open shifts`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedMidAtlanticDemosBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/mid-atlantic-demos", { method: "POST" });
    logOps(
      `Full demo environment — ${data.count} facilities (${data.hospital.count} hospital, ${data.post_acute.count} post-acute) across ${data.states.join(", ")} · ${data.portal_accounts.clinician_count} portal logins (${data.portal_accounts.password_hint})`,
    );
    showToast(`Seeded full demo environment — ${data.count} facilities in ${data.states.join(", ")}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedPostAcuteDemosBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/post-acute-demos", { method: "POST" });
    logOps(
      `Post-acute demos seeded — ${data.count} facilities across ${data.states.join(", ")}`,
    );
    showToast(`Seeded ${data.count} post-acute demos (${data.states.join(", ")})`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedHospitalDemosBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/hospital-demos", { method: "POST" });
    logOps(`Hospital demos seeded — ${data.count} ICUs across ${data.states.join(", ")}`);
    showToast(`Seeded ${data.count} hospital demos (${data.states.join(", ")})`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedDemoBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/saint-judes", { method: "POST" });
    logOps(`Saint Jude demo seeded — offer ${data.offer_id}`);
    showToast("Saint Jude demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedInovaBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/inova-fairfax", { method: "POST" });
    logOps(`Inova Fairfax VA demo seeded — offer ${data.offer_id}`);
    showToast("Virginia demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedHackensackBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/hackensack", { method: "POST" });
    logOps(`Hackensack NJ demo seeded — offer ${data.offer_id}`);
    showToast("New Jersey demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedNursingHomeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/nursing-home", { method: "POST" });
    logOps(`Nursing home demo seeded — offer ${data.offer_id}`);
    showToast("Nursing home demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedVaNursingHomeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/va-nursing-home", { method: "POST" });
    logOps(`VA nursing home demo seeded — offer ${data.offer_id}`);
    showToast("Virginia nursing home demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedDcNursingHomeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/dc-nursing-home", { method: "POST" });
    logOps(`DC nursing home demo seeded — offer ${data.offer_id}`);
    showToast("DC nursing home demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedPaNursingHomeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/pa-nursing-home", { method: "POST" });
    logOps(`PA nursing home demo seeded — offer ${data.offer_id}`);
    showToast("Pennsylvania nursing home demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedDeNursingHomeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/de-nursing-home", { method: "POST" });
    logOps(`DE nursing home demo seeded — offer ${data.offer_id}`);
    showToast("Delaware nursing home demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedNjNursingHomeBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/nj-nursing-home", { method: "POST" });
    logOps(`NJ nursing home demo seeded — offer ${data.offer_id}`);
    showToast("New Jersey nursing home demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.seedHomeHealthBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/home-health", { method: "POST" });
    logOps(`Home health demo seeded — offer ${data.offer_id}`);
    showToast("Home health demo seeded");
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.refreshIntegrationsBtn?.addEventListener("click", async () => {
  try {
    const [integrations, liveScrapers] = await Promise.all([
      api("/api/integrations/status"),
      api("/api/integrations/live-scrapers"),
    ]);
    renderIntegrations(integrations);
    renderLiveScrapers(liveScrapers);
    await loadTwilioSmsProductionPanel();
    showToast("Integration status refreshed");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.probeLiveScrapersBtn?.addEventListener("click", () => probeAllLiveScrapers().catch((e) => showToast(e.message, true)));
els.copyLiveScrapersEnvBtn?.addEventListener("click", () => copyLiveScrapersGoLiveEnv().catch((e) => showToast(e.message, true)));
els.testTwilioSmsBtn?.addEventListener("click", () => testTwilioSmsDelivery().catch((e) => showToast(e.message, true)));
els.twilioLockReplySmokeBtn?.addEventListener("click", () => runTwilioLockReplySmoke().catch((e) => showToast(e.message, true)));
els.copyTwilioGoLiveEnvBtn?.addEventListener("click", () => copyTwilioGoLiveEnv().catch((e) => showToast(e.message, true)));

els.refreshDeployBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/deploy/checklist");
    renderDeployChecklist(data);
    showToast("Deploy checklist refreshed");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDeployChecklistJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile("/api/deploy/checklist.json", "offercare-deploy-checklist.json");
    logOps("Exported deploy checklist (.json)");
    showToast("Exported deploy checklist (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDeployChecklistCsvBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile("/api/deploy/checklist.csv", "offercare-deploy-checklist.csv");
    logOps("Exported deploy checklist (.csv)");
    showToast("Exported deploy checklist (.csv)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.copyDeployGatesBtn?.addEventListener("click", async () => {
  try {
    await copyDemoGatesToClipboard();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDeployGatesTxtBtn?.addEventListener("click", async () => {
  try {
    await downloadDemoGatesTxtFile();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDeployGatesJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadDemoGatesJsonFile();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDeployBundleBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyExport("Download deploy bundle"))) {
      showToast("Download cancelled — run full demo setup until health is green", true);
      return;
    }
    await downloadAdminFile("/api/deploy/deploy-bundle.zip", "offercare-deploy-bundle.zip");
    logOps("Downloaded deploy bundle (.zip)");
    showToast("Downloaded deploy bundle (.zip)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.copyMarylandProductionEnvBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/deploy/maryland-production-runbook");
    await navigator.clipboard.writeText(data.env_snippet);
    showToast(`Copied Maryland production .env (${data.production_ready ? "READY" : "NOT YET"})`);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadMarylandProductionRunbookBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile(
      "/api/deploy/maryland-production-runbook.json",
      "offercare-maryland-production-runbook.json",
    );
    showToast("Exported Maryland production runbook (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.copyDeployLiveSmsEnvBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/integrations/twilio/go-live-profile");
    await navigator.clipboard.writeText(data.env_snippet);
    showToast(`Copied Twilio production .env (${data.production_ready ? "READY" : "NOT YET"})`);
  } catch (error) {
    showToast(error.message, true);
  }
});

async function runMarylandLaunchSmoke() {
  const data = await api("/api/deploy/maryland-launch-smoke", { method: "POST", body: JSON.stringify({}) });
  if (data.ok) {
    showToast(`Launch smoke OK — ${data.facility_name} locked`);
    logOps(
      `Maryland launch smoke — probes ${data.scraper_probes_ok ? "OK" : "FAIL"}, `
        + `lock ${data.lock_reply_smoke_ok ? "OK" : "FAIL"} · placement ${data.placement_id}`,
    );
  } else {
    showToast(data.message || "Maryland launch smoke failed", true);
    logOps(`Maryland launch smoke failed — ${data.message}`);
  }
  await refreshPendingAndStats();
}

els.runMarylandLaunchSmokeBtn?.addEventListener("click", () => runMarylandLaunchSmoke().catch((e) => showToast(e.message, true)));

els.copyMarylandLaunchEnvBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/deploy/maryland-launch-capstone");
    await navigator.clipboard.writeText(data.env_snippet);
    showToast(`Copied Maryland launch .env (${data.launch_ready ? "READY" : "NOT YET"})`);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadMarylandLaunchCapstoneBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile(
      "/api/deploy/maryland-launch-capstone.json",
      "offercare-maryland-launch-capstone.json",
    );
    showToast("Exported Maryland launch capstone (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.refreshDemoStatusBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/demo-status");
    renderDemoStatus(data);
    showToast("Demo environment status refreshed");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.runDemoSetupBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyExport("Run full demo setup"))) {
      showToast("Demo setup cancelled — resolve health issues or confirm to proceed", true);
      return;
    }
    const data = await api("/api/seed/demo-setup", { method: "POST" });
    logOps(
      `Full demo setup — reset ${data.reset.offers_reset} offers (${data.reset.placements_cleared} placements cleared) · ${data.seed.count} facilities across ${data.seed.states.join(", ")} · ${data.push_subscriptions.clinician_count} push subs · ${data.matched_push.matched_push_alerts_sent} matched alerts`,
    );
    showToast(
      `Demo ready — reset ${data.reset.offers_reset} shifts, ${data.seed.count} facilities, ${data.matched_push.matched_push_alerts_sent} matched push alerts sent`,
    );
    renderDemoStatus(data.status);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.resetDemoBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyReset("Reset demo environment"))) {
      showToast("Demo reset cancelled — ready environment left unchanged", true);
      return;
    }
    const data = await api("/api/seed/demo-reset", { method: "POST" });
    logOps(
      `Demo reset — ${data.offers_reset} offers unlocked, ${data.placements_cleared} placements cleared across ${data.offer_count} demo shifts`,
    );
    showToast(`Reset ${data.offers_reset} demo shifts (${data.placements_cleared} placements cleared)`);
    renderDemoStatus(data.status);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.copyDemoLinksBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyExport("Copy demo portal links"))) {
      showToast("Copy cancelled — run full demo setup until health is green", true);
      return;
    }
    const data = await api("/api/seed/demo-links");
    const lines = [
      `Portal login: ${data.portal_login_url}`,
      `Sample clinician: ${data.sample_clinician_email}`,
      `Password: ${data.portal_password_hint}`,
      "",
      ...data.offers.map(
        (row) => `${row.facility_name} (${row.state} ${row.shift_role}) → ${row.portal_url}${row.demo_clinician_email ? ` as ${row.demo_clinician_email}` : ""}`,
      ),
    ];
    await navigator.clipboard.writeText(lines.join("\n"));
    logOps(`Copied ${data.offers.length} demo portal deep links`);
    showToast(`Copied ${data.offers.length} demo portal links`);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.copyDemoWalkthroughBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/seed/demo-walkthrough");
    if (!data.demo_ready) {
      const proceed = await confirmDemoReadyExport("Copy walkthrough");
      if (!proceed) {
        showToast("Copy cancelled — run full demo setup until health is green", true);
        return;
      }
    }
    await navigator.clipboard.writeText(data.markdown);
    logOps(`Copied demo walkthrough script (${data.offer_count} shifts)`);
    showToast(`Copied demo walkthrough (${data.offer_count} shifts)`);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDemoWalkthroughBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyExport("Download walkthrough"))) {
      showToast("Download cancelled — run full demo setup until health is green", true);
      return;
    }
    await downloadAdminFile("/api/seed/demo-walkthrough.md", "offercare-demo-walkthrough.md");
    logOps("Downloaded demo walkthrough script (.md)");
    showToast("Downloaded demo walkthrough (.md)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDemoStatusJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile("/api/seed/demo-status.json", "offercare-demo-status.json");
    logOps("Exported demo status (.json)");
    showToast("Exported demo status (.json)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDemoStatusCsvBtn?.addEventListener("click", async () => {
  try {
    await downloadAdminFile("/api/seed/demo-status.csv", "offercare-demo-status.csv");
    logOps("Exported demo status (.csv)");
    showToast("Exported demo status (.csv)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDemoGatesJsonBtn?.addEventListener("click", async () => {
  try {
    await downloadDemoGatesJsonFile();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDemoGatesTxtBtn?.addEventListener("click", async () => {
  try {
    await downloadDemoGatesTxtFile();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.copyDemoGatesBtn?.addEventListener("click", async () => {
  try {
    await copyDemoGatesToClipboard();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.downloadDemoBundleBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyExport("Download demo bundle"))) {
      showToast("Download cancelled — run full demo setup until health is green", true);
      return;
    }
    await downloadAdminFile("/api/seed/demo-bundle.zip", "offercare-demo-bundle.zip");
    logOps("Downloaded demo bundle (.zip)");
    showToast("Downloaded demo bundle (.zip)");
  } catch (error) {
    showToast(error.message, true);
  }
});

els.ensureDemoPortalBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyEnsurePortal())) {
      showToast("Ensure portal logins cancelled — demo passwords left unchanged", true);
      return;
    }
    const data = await api("/api/seed/demo-portal-accounts", { method: "POST" });
    logOps(
      `Demo portal logins — ${data.created} created, ${data.updated} updated (${data.password_hint})`,
    );
    showToast(`Ensured ${data.clinician_count} demo portal logins (${data.password_hint})`);
    renderDemoStatus(data.demo_status);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.ensureDemoPushBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyEnsurePush())) {
      showToast("Ensure push subscriptions cancelled — no demo push subs changed", true);
      return;
    }
    const data = await api("/api/seed/demo-push-subscriptions", { method: "POST" });
    logOps(
      `Demo push subscriptions — ${data.created} created, ${data.existing} existing across ${data.clinician_count} clinicians`,
    );
    showToast(`Ensured demo push subscriptions for ${data.clinician_count} clinicians`);
    renderDemoStatus(data.demo_status);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.notifyMatchedDemosBtn?.addEventListener("click", async () => {
  try {
    if (!(await confirmDemoReadyNotifyMatched("all demo shifts"))) {
      showToast("Notify matched cancelled — no push alerts sent", true);
      return;
    }
    const data = await api("/api/seed/notify-matched-demos", { method: "POST" });
    logOps(
      `Demo matched push — ${data.matched_push_alerts_sent} alerts across ${data.offer_count} demo shifts`,
    );
    showToast(`Sent ${data.matched_push_alerts_sent} matched push alerts on ${data.offer_count} demos`);
    renderDemoStatus(data.demo_status);
  } catch (error) {
    showToast(error.message, true);
  }
});

els.demoLockSmokeBtn?.addEventListener("click", async () => {
  try {
    await runDemoLockSmoke();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.relearnScoresBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/shift-sniper/relearn-scores", { method: "POST" });
    showToast(`Relearned scores for ${data.updated} clinicians`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

els.submitPendingVmsBtn?.addEventListener("click", async () => {
  try {
    const data = await api("/api/vms/placements/submit-pending?limit=25", { method: "POST" });
    logOps(`VMS batch — submitted ${data.submitted}`);
    showToast(`Submitted ${data.submitted} placements to VMS`);
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
});

function slugifyPocketTitle(title) {
  return String(title || "section")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const POCKET_NAV_GROUPS = [
  {
    key: "launch",
    label: "Launch & go-live",
    hint: "Production readiness chain",
    titles: [
      "Production ops dashboard",
      "Production perfection",
      "Production launch ceremony",
      "Production go-live record",
      "Production launch attestation",
      "Production launch perfection seal",
      "Production launch archive",
      "Production launch perfection finale",
      "Production launch perfection manifest",
    ],
  },
  {
    key: "platform",
    label: "Platform ops",
    hint: "Workers, deploy, integrations",
    titles: [
      "Ops metrics",
      "Audit log",
      "Deploy walkthrough",
      "Integrations",
      "Shift Sniper intelligence",
    ],
  },
  {
    key: "grid",
    label: "Grid & staffing",
    hint: "Scrape, shifts, placements",
    titles: [
      "Grid operations",
      "Demo environment",
      "Worker inflow (opt-in)",
      "Pending clinicians",
      "Open shifts",
      "Placements & VMS",
    ],
  },
  {
    key: "compliance",
    label: "Compliance & outreach",
    hint: "COMAR, crisis, B2B pipeline",
    titles: ["Maryland COMAR compliance", "B2B outreach pipeline"],
  },
];

function pocketNavGroupKey(title) {
  for (const group of POCKET_NAV_GROUPS) {
    if (group.titles.includes(title)) return group.key;
  }
  return "platform";
}

const POCKET_DEFAULT_OPEN = new Set([
  "Open shifts",
  "Grid operations",
  "Worker inflow (opt-in)",
  "Pending clinicians",
  "Demo environment",
]);


function mountAdminPockets() {
  const app = document.getElementById("app");
  if (!app || app.dataset.pocketsMounted === "1") return;

  const pockets = [];
  app.querySelectorAll(":scope > section.panel").forEach((section) => {
    const head = section.querySelector(":scope > .panel-head");
    if (!head) return;

    const title = head.querySelector("h2")?.textContent?.trim() || "Section";
    const pocketId = `pocket-${slugifyPocketTitle(title)}`;
    const groupKey = pocketNavGroupKey(title);
    section.id = pocketId;
    section.classList.add(`admin-pocket-shell--${groupKey}`);

    const details = document.createElement("details");
    details.className = `admin-pocket admin-pocket--${groupKey}`;
    details.open = POCKET_DEFAULT_OPEN.has(title);

    const summary = document.createElement("summary");
    summary.className = "admin-pocket__summary";
    summary.appendChild(head);

    const chevron = document.createElement("span");
    chevron.className = "admin-pocket__chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.textContent = "▸";
    summary.appendChild(chevron);

    const body = document.createElement("div");
    body.className = "admin-pocket__body";
    [...section.children].forEach((child) => {
      if (child !== head) body.appendChild(child);
    });

    details.appendChild(summary);
    details.appendChild(body);
    section.appendChild(details);

    details.addEventListener("toggle", () => {
      document.querySelectorAll(".admin-pocket-nav__link").forEach((link) => {
        link.classList.toggle("is-active", link.dataset.pocketTarget === pocketId && details.open);
      });
    });

    pockets.push({ id: pocketId, title, details, groupKey });
  });

  if (pockets.length) {
    const nav = document.createElement("nav");
    nav.className = "admin-pocket-nav";
    nav.innerHTML = `
      <div class="admin-pocket-nav__hero">
        <div class="admin-pocket-nav__intro">
          <p class="admin-pocket-nav__eyebrow">Maryland State Wide Grid</p>
          <h2 class="admin-pocket-nav__title">Console sections</h2>
          <p class="admin-pocket-nav__subtitle">Jump to launch, platform, grid, or compliance modules.</p>
        </div>
        <div class="admin-pocket-nav__actions">
          <button type="button" class="admin-pocket-nav__action admin-pocket-nav__action--expand" data-pocket-expand-all>Expand all</button>
          <button type="button" class="admin-pocket-nav__action admin-pocket-nav__action--collapse" data-pocket-collapse-all>Collapse all</button>
        </div>
      </div>
    `;

    const groupsWrap = document.createElement("div");
    groupsWrap.className = "admin-pocket-nav__groups";

    POCKET_NAV_GROUPS.forEach((group) => {
      const groupPockets = pockets.filter((pocket) => pocket.groupKey === group.key);
      if (!groupPockets.length) return;

      const groupEl = document.createElement("section");
      groupEl.className = `admin-pocket-nav__group admin-pocket-nav__group--${group.key}`;
      groupEl.innerHTML = `
        <header class="admin-pocket-nav__group-head">
          <span class="admin-pocket-nav__group-dot" aria-hidden="true"></span>
          <div>
            <h3 class="admin-pocket-nav__group-label">${group.label}</h3>
            <p class="admin-pocket-nav__group-hint">${group.hint}</p>
          </div>
        </header>
      `;

      const list = document.createElement("div");
      list.className = "admin-pocket-nav__list";
      groupPockets.forEach(({ id, title, details }) => {
        const link = document.createElement("button");
        link.type = "button";
        link.className = `admin-pocket-nav__link admin-pocket-nav__link--${group.key}`;
        link.dataset.pocketTarget = id;
        link.innerHTML = `<span class="admin-pocket-nav__link-text">${title}</span>`;
        if (details.open) link.classList.add("is-active");
        link.addEventListener("click", () => {
          details.open = true;
          document.querySelectorAll(".admin-pocket-nav__link").forEach((node) => {
            node.classList.toggle("is-active", node === link);
          });
          sectionScroll(id);
        });
        list.appendChild(link);
      });

      groupEl.appendChild(list);
      groupsWrap.appendChild(groupEl);
    });

    nav.appendChild(groupsWrap);
    nav.querySelector("[data-pocket-expand-all]")?.addEventListener("click", () => {
      pockets.forEach(({ details }) => {
        details.open = true;
      });
      document.querySelectorAll(".admin-pocket-nav__link").forEach((link) => {
        link.classList.toggle("is-active", true);
      });
    });
    nav.querySelector("[data-pocket-collapse-all]")?.addEventListener("click", () => {
      pockets.forEach(({ details }) => {
        details.open = false;
      });
      document.querySelectorAll(".admin-pocket-nav__link").forEach((link) => {
        link.classList.remove("is-active");
      });
    });

    const stats = document.getElementById("stats");
    if (stats?.nextSibling) {
      stats.parentNode?.insertBefore(nav, stats.nextSibling);
    } else {
      app.insertBefore(nav, app.querySelector("section.panel"));
    }
  }

  app.dataset.pocketsMounted = "1";
}

function sectionScroll(pocketId) {
  const section = document.getElementById(pocketId);
  if (!section) return;
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

window.addEventListener("offercare-admin-connected", () => {
  mountAdminPockets();
  setConnectionStatus("loading", "Loading dashboard…");
  loadShiftFilters().catch((error) => {
    logOps(`Shift filters unavailable — ${error.message}`);
    showToast(error.message, true);
  });
  refreshAll().catch((error) => showToast(error.message, true));
});

if (!els.app?.classList.contains("hidden")) {
  mountAdminPockets();
  refreshAll().catch((error) => showToast(error.message, true));
}

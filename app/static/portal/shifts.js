"""Portal shift loading helpers — demo walkthrough lock hints in the browser."""

(function portalShiftHelpers() {
  const DEMO_EMAIL_SUFFIX = "@offercare.demo";

  function isDemoProvider(provider) {
    return String(provider?.email || "")
      .trim()
      .toLowerCase()
      .endsWith(DEMO_EMAIL_SUFFIX);
  }

  function demoRoleMatches(credential, shiftRole) {
    const cred = String(credential || "").toUpperCase();
    const role = String(shiftRole || "").toUpperCase();
    if (!cred || !role) return false;
    if (cred === role) return true;
    if (cred === "CNA" && ["CNA", "GNA", "NA"].includes(role)) return true;
    if (cred === "LPN" && ["LPN", "LVN"].includes(role)) return true;
    if (cred === "RN" && ["RN", "ICU_RN", "ER_RN"].includes(role)) return true;
    return false;
  }

  function applyDemoClientLockHints(rows, provider) {
    if (!isDemoProvider(provider) || !Array.isArray(rows)) return rows;
    const homeState = String(provider.state || "").toUpperCase();
    const minRate = Number(provider.min_hourly_rate || 0);
    const enriched = rows.map((row) => {
      if (row.lock_eligible) return row;
      const broadcasting = String(row.compliance_lock_status || "").toUpperCase() === "BROADCASTING";
      const stateOk = String(row.state || "").toUpperCase() === homeState;
      const payOk = Number(row.hourly_pay_rate) >= minRate;
      const roleOk = demoRoleMatches(provider.credential_type, row.shift_role);
      if (!broadcasting || !stateOk || !payOk || !roleOk) return row;
      return {
        ...row,
        lock_eligible: true,
        lock_preview: "Ready to lock (demo)",
        rate_delta: Number((Number(row.hourly_pay_rate) - minRate).toFixed(2)),
        vault_review_recommended: false,
      };
    });
    enriched.sort((a, b) => {
      if (a.lock_eligible !== b.lock_eligible) return a.lock_eligible ? -1 : 1;
      return (Number(b.rate_delta) || -1) - (Number(a.rate_delta) || -1);
    });
    return enriched;
  }

  async function bootstrapDemoShifts(apiFn) {
    if (typeof apiFn !== "function") return;
    try {
      await apiFn("/api/clinicians/me/demo-shift-bootstrap", { method: "POST", body: "{}" });
    } catch {
      // Legacy API — client-side demo hints still apply.
    }
  }

  window.PortalShifts = {
    isDemoProvider,
    applyDemoClientLockHints,
    bootstrapDemoShifts,
  };
})();

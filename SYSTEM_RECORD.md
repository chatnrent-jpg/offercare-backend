# VettedCare Platform — Canonical System Record

**Purpose:** Master operational blueprint for domain boundaries, authority chains, and audit policy.  
**Audience:** Product, engineering, operations, and compliance stakeholders.  
**Scope:** Whole-platform structure — not a wiring or integration checklist.  
**Last established:** Phase A — operational boundary lockdown.  
**Last sprint lock:** VCAI-INFRA-SPRINT-2026-07-02 — Section 5 canonically locked (Amendment A — 2026-07-02; **Amendment B — 2026-07-02**).

---

## 1. THE OPERATIONAL MATRIX (Live vs. Mock Boundaries)

| Core Domain | Active Status | Operational Notes |
|-------------|---------------|-------------------|
| PostgreSQL Core Schema & Migrations | **PRODUCTION REAL** (Alembic 001–019, Healer active) | Primary system of record. Nineteen Alembic revisions cover facilities, providers, offers, placements, compliance, outreach, Manus vetting, instant pay, and embeddings. Boot-time schema healer verifies and heals the compliance audit ledger table before workers start. |
| Rule-Based Shift Matching & Sniper Cascades | **PRODUCTION REAL** (Postgres State Engine) | Ranking, geo constraints, GNA firewall, and lookahead-safe checks run against live database state. Cascade notify worker and retry scheduler operate on real offer and placement rows. |
| Semantic pgvector Embeddings Matcher | **CONDITIONALLY REAL** (Active if HNSW/LLM extensions active, otherwise Mock Fallback) | Vector similarity search is production-capable when pgvector extension, HNSW index, and outreach LLM credentials are present. Without them, hash-based mock embeddings preserve pipeline continuity without claiming live semantic accuracy. |
| MBON / OIG Credential Engine | **ENGINE REAL / COUPLING MOCK** (Circuit Breaker active, Scraper gateway built, Live data gated) | Autonomous credential engine, 150ms network circuit breaker, and Sentinel geo validation are implemented. Registry handshakes in the strategy layer remain mock-coupled; app-layer scraper gateway supports live verification when dry-run flags are disabled. |
| Stripe Escrow & Instant Payouts | **SCHEMA REAL / ROUTING MOCK** (Dry-run escrow hooks live) | Escrow webhook, payout ledger tables, supervisor sign-off flow, and payout worker exist against real schema. Stripe routing defaults to dry-run until production keys and dry-run flags are explicitly cleared. |
| Communications (Twilio / Push / Email) | **PIPELINE REAL / CARRIER MOCK** (Dry-run by default) | Notification orchestration, cascade SMS paths, push subscription model, and email campaign logging are built. Carrier delivery defaults to dry-run across SMS, push, and SMTP until live credentials and flags are engaged. |
| Clinician Portal & Shift Lock | **PRODUCTION REAL** | Apply, authentication, matched shifts, shift lock, calendar export, and push subscription flows operate against live portal and provider tables. |
| VMS Shift Ingest | **PIPELINE REAL / DATA MOCK** (Dry-run ingest by default) | HTTP ingest and optional portal worker paths exist. Synthetic shift generation remains the default until live VMS credentials and dry-run toggles are cleared. |
| B2B Outreach & Recruitment | **ORCHESTRATION REAL / SEND MOCK** | Crisis signals, contact enrichment, campaign orchestration, and email logs are persisted. LLM copy generation and outbound email default to template and dry-run modes. |
| Manus Vetting & Safety Cycle | **PRODUCTION REAL** (Worker optional) | Work queue, run ingest, safety cycle, audit logs, and credential alerts are real database-backed flows. External Manus worker is optional; hooks are ready. |
| Maryland Desk Orchestrator | **ENGINES REAL / FEED STAGING-FIRST** | Backup routing, conflict detection, surge pricing, penalty, and match chaining are production-quality algorithms. Primary desk inputs still favor staging JSON artifacts unless live Montgomery dispatch flags and database parity are active. |
| Compliance Audit Ledger | **MODEL REAL / ENCRYPTION ACTIVE** | Immutable-style audit table with field-level Fernet encryption on payload bodies. Boot healer ensures table presence; writers must conform to audit transaction policy below. |
| Production Launch & Infra Readiness | **META-READINESS REAL** | Deploy checklists, health aggregations, runbooks, and launch ceremony builders report readiness state. These artifacts govern go-live discipline; they are not substitute product features. |

**Matrix rule:** A domain marked PRODUCTION REAL owns live PostgreSQL truth. A domain marked MOCK or CONDITIONALLY REAL must never be described to operators or partners as fully live without explicit environment confirmation.

---

## 2. THE COMPLIANCE CHAIN OF COMMAND

Two compliance layers exist by design. They do not compete; they operate at different lifecycle moments with different latency and depth requirements.

### PRE-MATCH INTAKE GATE (Strategy Layer)

**Authority:** Immediate, automated, high-speed front gate before match initialization or facility query acceptance.

**Components:**
- CredentialCheckEngine — Maryland license and OIG exclusion screening with mock registry coupling and live provider resolution when database rows exist.
- NetworkCircuitBreaker — 150 millisecond speed guard with CLOSED, OPEN, and HALF_OPEN self-healing states; trips route candidates to CREDENTIALS_PENDING rather than blocking server boot.
- SentinelValidationSuite — Coordinate and radius perimeter validation (including 150-mile geo guard); blocks invalid facility or query inputs before they enter matching pipelines.

**Behavior:**
- Runs synchronously at the edge of matching and semantic search entry points.
- Must complete or trip within the 150ms performance envelope.
- Purpose is to shield the database and downstream workers from bad inputs, slow external registries, and out-of-perimeter facility requests.
- Does not perform deep document review or async scraper sweeps.

**Outcome states:** CREDENTIALS_PASSED, CREDENTIALS_PENDING, LICENSE_EXPIRED, LICENSE_INACTIVE, OIG_FLAGGED, SENTINEL_BLOCK.

### POST-PLACEMENT DEPLOYMENT AUDIT (App Layer)

**Authority:** Deep, asynchronous regulatory verification after a match is initialized and before escrow lock or final dispatch commitment.

**Components:**
- Live scraper gateway adapters for MBON, OIG, and Maryland judiciary sources.
- Clinician compliance document tracking pipeline.
- Compliance monitor and dispatch suspension services.
- License verification logs and exclusion screening history cross-reference.

**Behavior:**
- Executes after match initialization; tolerates longer latency than the intake gate.
- Gathers documentary and registry evidence into persistent compliance tables.
- Can suspend or flag dispatch when deep checks fail, independent of the fast intake gate result.
- Operates under app-layer dry-run toggles until live scraper gateway and credentials are confirmed.

**Boundary rule:** The strategy intake gate decides whether a candidate may enter the matching conversation. The app post-placement audit decides whether a initialized match may proceed to escrow lock and confirmed deployment. Neither layer overrides the other; both may record outcomes to the compliance audit ledger per policy below.

---

## 3. THE MATCHING WINNER-TAKE-ALL PROTOCOL

Shift dispatch authority follows a strict tier protocol. When multiple matchers could apply, the higher-precedence tier wins for that dispatch context.

### Tier 1 — Rule Sniper (Urgent Regional Vacancies)

**Wins when:** An immediate, urgent, regional placement vacancy must be filled under time pressure with known facility, role, and geo constraints.

**Authority:** Rule-based shift matching, sniper ranking, geo matching, GNA firewall, cascade notify worker, and match retry scheduler.

**Rationale:** Deterministic Postgres state, lookahead-safe rules, and cascade retry are optimized for speed and operational certainty. Urgent vacancies do not wait for embedding API latency or semantic ambiguity resolution.

### Tier 2 — Semantic Vector Matcher (Complex Tag-Dense Requests)

**Wins when:** The request is complex, tag-dense, or specialty-specific — for example, dementia care specialized night shifts tied to specific facility profiles or nuanced clinical preference language.

**Authority:** Semantic payout engine, pgvector similarity search, provider profile embeddings, and vector match API when HNSW and LLM extensions are active.

**Rationale:** Semantic ranking resolves preference-rich queries that rule tables alone cannot express. When vector infrastructure or LLM credentials are unavailable, this tier degrades to mock fallback and does not override Tier 1 for urgent regional vacancies.

### Protocol Rules

1. Urgent regional vacancy plus active sniper candidate pool → **Rule Sniper wins.**
2. Complex tag-dense provider or facility request with no urgent sniper override → **Semantic Vector wins** (when conditionally real).
3. Both tiers produce candidates → **Rule Sniper takes dispatch precedence** if the vacancy is classified urgent; otherwise semantic rank leads specialty placement.
4. Credential intake gate failure at either tier → **No dispatch** regardless of match score; candidate routes to CREDENTIALS_PENDING or hard block per gate outcome.
5. Post-placement audit failure after match initialization → **Dispatch hold** until app-layer compliance clears or escalates.

---

## 4. THE AUDIT LEDGER TRANSACTION POLICY

The compliance_audit_ledger table is the immutable enterprise audit trail for high-risk compliance and performance events. Payload bodies are field-level encrypted at rest using Fernet with the HIVE_FIELD_ENCRYPTION_KEY environment token (baseline fallback key permitted only in non-production test environments).

### Mandatory Write Events

Every occurrence of the following events **must** produce a ledger row with encrypted raw_payload_json:

| Event Class | Trigger | Minimum Record Fields |
|-------------|---------|----------------------|
| SENTINEL_BLOCK | Coordinate validation failure or radius perimeter breach (including 150-mile geo guard rejection) | Event type, validation reason, facility or query coordinates, timestamp, block rationale |
| CIRCUIT_BREAKER_TRIPPED | API lookup latency timeout under the 150ms network speed guard | Event type, callable or registry target, trip status, timeout threshold, timestamp |
| OIG_FLAGGED | OIG exclusion hit or internal restriction log cross-reference during credential screening | Provider identifier, OIG status, match count, screening source, timestamp |
| Structural Credential Mismatch | License expired, inactive, disciplinary, or other structural mismatch during screening that hard-blocks or reclassifies eligibility | Provider identifier, compliance status, MBON status, license expiration context, timestamp |

### Write Discipline

- Writes are append-oriented; ledger rows are not updated in place for audit integrity.
- Encryption applies on assignment to raw_payload_json; legacy plaintext rows decrypt-fallback safely for read compatibility.
- Boot schema healer verifies table presence; missing table heal attempts must not block API startup.
- Ledger writes fail open at the caller only where explicitly documented (e.g., Sentinel persist during database unavailability logs warning and continues); production operators must treat repeated write failures as infra incidents.

### Events Explicitly Outside Mandatory Ledger Scope (Unless Policy Extended)

- Routine CREDENTIALS_PASSED confirmations with no anomaly.
- Successful match rankings and cascade notifications without compliance anomaly.
- Dry-run SMS, email, push, and Stripe events (unless they coincide with a mandatory event class above).

---

**Milestone:** Phase A — Canonical System Record established.

---

## 5. SPRINT DEPLOYMENT RECORD

**Sprint ID:** VCAI-INFRA-SPRINT-2026-07-02  
**Execution status:** **SUCCESSFUL — DEPLOYED TO LOCAL ENGINE**  
**Recorded:** 2026-07-02 (UTC-4)  
**Scope:** Payroll intercept · HB 1106 compliance sentinel · Manus OHCQ lead loops · Workstream/v0 caregiver intake · **Amendment A:** 9-route regional manifest · HB 1106 bias auditor · Skyflow PII vault · **Amendment B:** Maryland AEDT disclosure box · payroll onboarding syncer · B2B invoicing markup engine  
**Canonical lock:** **LOCKED** — this section is append-only authority for Sprint infrastructure architecture. Amendments require explicit governance revision.

### 5.1 Execution Summary

The VettedCare.ai backend infrastructure sprint completed successful local execution across four integration surfaces. All core modules ship with unit test coverage, Alembic schema support through revision **027**, Manus work-queue registration, and dry-run defaults for external API keys pending the dedicated keys-assignment day. No Phase A operational boundaries (Sections 1–4) were superseded; this sprint extends live engine capability within those boundaries. **Amendment A** (same-day) adds the 9-route regional manifest, HB 1106 hash-chained bias auditor, and Skyflow PII tokenization gate documented in §5.8–5.10. **Amendment B** (same-day) adds the Maryland AEDT 30-day disclosure compliance box, automated Gusto/Check HQ payroll onboarding syncer, and B2B facility invoicing markup pipeline documented in §5.12–5.14.

| Integration | Status | Primary Artifact |
|-------------|--------|------------------|
| Gusto/Check HQ → Stripe 150ms payroll tax intercept bridge | **EXECUTED** | `app/services/payroll_tax_intercept_bridge.py` |
| MD HB 1106 compliance sentinel (SNF matching gate) | **EXECUTED** | `app/middleware/compliance_sentinel.py` |
| Manus OHCQ citation tracking & B2B lead loops | **EXECUTED** | `data_engine/ohcq_citation_tracker.py` + Manus workflows |
| Workstream / v0 Baltimore instant-pay caregiver intake queue | **EXECUTED** | `/baltimore-instant-pay-cna` + `caregiver_intake_queue` |

---

### 5.2 Integration Architecture — 150ms Gusto/Check Stripe Intercept Bridge

**Purpose:** Intercept gross instant-payout amounts before Stripe debit-card dispatch; compute Tier 1 W-2 net pay after federal FICA, Maryland state withholding, and county piggyback; pass **net pay only** to the Stripe instant payout payload.

**Authority chain:**
```
Supervisor timesheet sign-off
  → apply_instant_payout_tax_intercept() / build_stripe_instant_payout_payload()
  → Gusto/Check HQ endpoint mirror (docs/payroll/W2-MARYLAND-WITHHOLDING-ENDPOINTS.md)
  → Maryland county residence resolution (CaregiverW2EmployeeAccount)
  → Net pay Decimal
  → semantic_payout_engine.trigger_instant_payout() / api/instant_pay_retention.py
  → Stripe instant payout (dry-run until keys cleared)
```

**Performance envelope:** Operates within the platform's 150ms network speed-guard discipline — intercept is synchronous and local (no live Gusto/Check round-trip on the hot path; endpoint routes are mirrored from payroll docs). External registry calls remain circuit-breaker gated per Section 2.

**Key components:**
- `app/services/payroll_tax_intercept_bridge.py` — gross-to-net computation, MD county piggyback table, W-2 Tier 1 account resolution
- `strategy/semantic_payout_engine.py` — wired pre-Stripe payload mutation
- `api/instant_pay_retention.py` — instant pay worker integration
- `tests/test_payroll_tax_intercept_bridge.py` — **5 passed**

**Configuration:** `PAYROLL_TAX_INTERCEPT_ENABLED`, caregiver dual-account schema (Alembic **022**).

---

### 5.3 Integration Architecture — MD HB 1106 Compliance Sentinel

**Purpose:** Strict pre-match logic gate for nursing-home (SNF) shift matching — enforce HB 1106 automated hiring anti-bias consent and MBON verification freshness (24-hour window) before a caregiver enters the match matrix.

**Authority chain:**
```
Shift match request (SNF / NURSING_HOME)
  → run_compliance_sentinel() [app/middleware/compliance_sentinel.py]
  → HB 1106 consent check (CONSENT_HB1106_AUTOMATED_HIRING_ANTI_BIAS via worker_consent)
  → MBON freshness check (COMPLIANCE_SENTINEL_MBON_MAX_AGE_HOURS = 24)
  → Outcome: COMPLIANCE_SENTINEL_CLEAR | MATCHING_HOLD | BLOCKED
  → Encrypted write to compliance_audit_ledger (STATE_REPORTING_SCHEMA: MD_AUTOMATED_HIRING_COMPLIANCE_v1)
  → shift_matching.py / unified_match_matrix_broker.py / compliance_authority_anchor.py
```

**Outcome semantics:**
- **CLEAR** — candidate proceeds to matching
- **MATCHING_HOLD** — stale MBON or pending verification; no dispatch
- **BLOCKED** — missing HB 1106 consent; hard stop with audit row

**Key components:**
- `app/middleware/compliance_sentinel.py`
- `app/services/worker_consent.py` — HB 1106 consent token
- `app/models/compliance_audit_ledger.py` — encrypted audit persistence
- `tests/test_compliance_sentinel.py` — **6 passed**

**Configuration:** `COMPLIANCE_SENTINEL_ENABLED`, `COMPLIANCE_SENTINEL_HB1106_REQUIRED`, `COMPLIANCE_SENTINEL_MBON_MAX_AGE_HOURS`.

**Boundary note:** This sentinel is the **app-layer SNF matching gate** complementing the strategy-layer PRE-MATCH INTAKE GATE (Section 2). Both may write to the audit ledger; neither overrides the other.

---

### 5.4 Integration Architecture — Manus OHCQ Tracking Loops

**Purpose:** Automated Maryland OHCQ/CMS staffing-citation discovery, lead flagging, Clay enrichment handoff, HeyReach DON outreach sequencing, and offline pipeline manifest generation for B2B recruitment prioritization.

**Loop architecture:**
```
Manus work-queue trigger
  → OHCQ citation tracker [data_engine/ohcq_citation_tracker.py]
      Sources: MDH OHCQ Excel registry · CMS health citations (r5ix-sfxw) · CMS provider staffing (4pq5-n9py)
      Output: leads/ohcq_staffing_citation_flags_md.csv (353 flagged facilities — live sweep verified)
  → Clay DON/HR enrichment [data_engine/clay_ohcq_enrichment.py]
      Template: integrations/clay/ohcq_citation_enrichment.template.json
      Output: leads/ohcq_staffing_citation_enriched_md.csv
  → HeyReach multi-channel sequence [data_engine/heyreach_outreach.py]
      Template: integrations/heyreach/md_don_ohcq_outreach.template.json
      Output: leads/heyreach_md_don_ohcq_import.csv · heyreach_md_don_ohcq_sequence.json
  → Offline pipeline manifest [data_engine/md_ohcq_leads_pipeline.py]
      Output: logs/manus/md_ohcq_leads_pipeline_manifest.json
```

**Manus-registered workflows** (`app/services/manus_recruitment.py`):
- `ohcq-staffing-citation-tracker`
- `clay-ohcq-don-hr-enrichment`
- `md-ohcq-leads-pipeline-offline`
- `heyreach-md-don-ohcq-sequence`

**County normalization:** `data_engine/md_county_normalizer.py` maps CMS city tokens to official Maryland counties for outreach copy accuracy.

**Test coverage:** OHCQ tracker **9 passed** · Clay enrichment **5 passed** · HeyReach outreach **5 passed** · MD pipeline **5 passed**.

**External keys (deferred):** `CLAY_TABLE_WEBHOOK_URL`, `HEYREACH_API_KEY` — dry-run and OHCQ-flags fallback operational without live keys.

---

### 5.5 Integration Architecture — Unified Workstream / v0 Mobile Caregiver Intake Queue

**Purpose:** Mobile-first Baltimore CNA conversion landing page connected to Workstream job distribution (Indeed + ZipRecruiter) with a unified `caregiver_intake_queue` database table receiving text-to-apply submissions from both the v0 landing page and Workstream SMS reply webhooks.

**Caregiver intake authority chain:**
```
Candidate touchpoint
  ├─ v0 landing POST /api/landing/baltimore-instant-pay-cna/text-apply
  ├─ Workstream webhook POST /api/v1/webhooks/workstream/text-apply
  └─ queue_caregiver_text_intake() [app/services/caregiver_intake_queue.py]
      → caregiver_intake_queue table (Alembic 023)
      → queue_status: QUEUED
      → landing_slug: baltimore-instant-pay-cna
      → Full onboarding handoff: /join
```

**v0 mobile landing (`/baltimore-instant-pay-cna/`):**
- Static assets: `app/static/baltimore-instant-pay-cna/` (Inter, card layout, sticky mobile CTA)
- Core selling points rendered: **Instant Pay via Stripe** · **Automated W-2 compliance**
- Prominent text-to-apply phone block with SMS consent

**Workstream distribution bridge:**
- Service: `app/services/workstream_job_bridge.py`
- Template: `integrations/workstream/baltimore_instant_pay_cna.template.json`
- Channels: **Indeed**, **ZipRecruiter** (Baltimore metro, 35-mile radius)
- API headers on every Workstream request: `Instant Pay via Stripe: enabled` · `W-2 Status: Tier 1 W-2 Employee`
- Webhook destination: `/api/v1/webhooks/workstream/text-apply` → `caregiver_intake_queue`
- Script: `scripts/run-workstream-baltimore-cna-distribute.bat`
- Export: `leads/workstream_baltimore_cna_job_posts.json`

**Payroll ↔ landing alignment:** Workstream job posts and v0 landing copy both reference the payroll tax intercept bridge (Stripe net pay after W-2 withholding) as the primary caregiver value proposition.

**Test coverage:** Baltimore landing **5 passed** · Workstream bridge **4 passed**.

**External keys (deferred):** `WORKSTREAM_CLIENT_ID`, `WORKSTREAM_ACCESS_TOKEN`, `WORKSTREAM_WEBHOOK_BEARER_TOKEN`, `PUBLIC_BASE_URL`.

---

### 5.6 Sprint Schema & Route Registry

| Revision / Route | Description |
|------------------|-------------|
| Alembic **022** | Dual-account caregiver schema (Tier 1 W-2 / Tier 2 1099) |
| Alembic **023** | `caregiver_intake_queue` table |
| Alembic **024** | Skyflow PII token columns on caregiver profile / W-2 account tables |
| Alembic **025** | `maryland_providers.consent_signed_at` — Maryland AEDT 30-day disclosure timestamp |
| Alembic **026** | `gusto_employee_id`, `payroll_onboarding_error` on W-2 employee accounts |
| Alembic **027** | `facility_billing_audit_ledger` — itemized B2B invoice math per completed shift |
| `/shared/aedt_disclosure.js` | Shared Maryland AEDT disclosure checkbox (mounted at `/shared/`) |
| `/baltimore-instant-pay-cna/` | v0 mobile caregiver landing (seed route; superseded by manifest registry) |
| `/{region}-instant-pay-{license}/` | **9 localized landing routes** (3 regions × 3 license types — see §5.8) |
| `/api/landing/routes/manifest` | Programmatic route manifest export |
| `/api/landing/instant-pay/{region}/{license}` | Localized landing content API |
| `/api/landing/instant-pay/{region}/{license}/text-apply` | Localized text-to-apply intake |
| `/api/landing/baltimore-instant-pay-cna` | Legacy Baltimore landing content API |
| `/api/landing/baltimore-instant-pay-cna/text-apply` | Legacy Baltimore direct text-to-apply intake |
| `/api/v1/webhooks/workstream/text-apply` | Workstream SMS reply → intake queue |
| `/api/v1/pay/*` | Instant pay retention (tax intercept wired) |
| `/api/caregivers/provision` | Caregiver onboarding with Skyflow PII tokenization gate (§5.10) |

---

### 5.8 Amendment A — Dynamic 9-Route Regional Landing Manifest

**Amendment ID:** VCAI-INFRA-SPRINT-2026-07-02-A  
**Recorded:** 2026-07-02 (UTC-4)  
**Purpose:** Programmatic regional expansion of the v0 instant-pay caregiver landing surface — generate localized URLs from Maryland Region × License Type parameters without duplicating layout assets.

**Route matrix (3 × 3 = 9 routes):**

| Region | CNA | GNA | LPN |
|--------|-----|-----|-----|
| Baltimore | `baltimore-instant-pay-cna` | `baltimore-instant-pay-gna` | `baltimore-instant-pay-lpn` |
| Silver Spring | `silver-spring-instant-pay-cna` | `silver-spring-instant-pay-gna` | `silver-spring-instant-pay-lpn` |
| Bethesda | `bethesda-instant-pay-cna` | `bethesda-instant-pay-gna` | `bethesda-instant-pay-lpn` |

**URL pattern:** `{region}-instant-pay-{license}`

**Authority chain:**
```
route_manifest.py [app/static/landing/route_manifest.py]
  → iter_routes() / manifest_export()
  → localized_instant_pay_landing.py [app/services/localized_instant_pay_landing.py]
  → main.py dynamic route registration (all 9 slugs)
  → queue_caregiver_text_intake() with region_metadata JSON
  → caregiver_intake_queue (Alembic 023)
```

**Key components:**
- `app/static/landing/route_manifest.py` — `MarylandRegionSpec`, `LicenseTypeSpec`, `LocalizedRouteSpec`, `V0_LAYOUT_RULES`, `manifest_export()`
- `app/services/localized_instant_pay_landing.py` — shared v0 layout loader, localized page builder, intake handoff
- `app/routers/landing.py` — `GET /api/landing/routes/manifest`, localized content + text-apply endpoints
- `app/main.py` — registers static mounts and API routes for all manifest slugs at boot

**Layout rule:** All nine routes share the v0-mobile-first-instant-pay shell (`baltimore-instant-pay-cna` template dir) with region-specific metadata (market, county, default ZIP, phone placeholder) injected at render time.

**Test coverage:** `tests/test_route_manifest.py` — **6 passed** · Baltimore landing regression — **5 passed**.

---

### 5.9 Amendment A — Hash-Chained HB 1106 Algorithmic Bias Auditor

**Amendment ID:** VCAI-INFRA-SPRINT-2026-07-02-A  
**Recorded:** 2026-07-02 (UTC-4)  
**Purpose:** Post-match compliance certification for Maryland HB 1106 — evaluate every caregiver↔facility shift match on four objective metrics only; produce an unalterable, hash-chained audit log for annual third-party compliance review.

**Authority chain:**
```
Successful shift match [app/services/shift_matching.py]
  → _run_bias_auditor_on_match() (fail-open; skips demo walkthrough providers)
  → intercept_caregiver_shift_match() [compliance/algorithmic_bias_auditor.py]
  → collect_objective_match_metrics()
      1. MBON license status
      2. Geographic distance (haversine miles)
      3. Historical facility rating
      4. Specific clinical skills / care tags
  → build_claude_prompt_matrix() → Claude 3.5 Sonnet (live) | deterministic dry-run
  → append_hb1106_audit_record() → maryland_hb1106_audit.log (hash-chained JSONL)
```

**Audit log integrity:** Each entry includes `previous_entry_hash` and `entry_hash` (SHA-256 over canonical JSON body). Append-only writes; tamper-evident chain from `GENESIS`.

**Outcome fields:** `zero_illegal_demographic_bias`, `certification_statement`, `reasoning_summary`, `engine_mode` (`deterministic_dry_run` | `claude_3_5_sonnet_live`).

**Key components:**
- `compliance/algorithmic_bias_auditor.py` — `intercept_caregiver_shift_match`, `collect_objective_match_metrics`, `append_hb1106_audit_record`
- `compliance/__init__.py` — public bias auditor exports
- `app/services/shift_matching.py` — post-broker match hook
- `tests/test_algorithmic_bias_auditor.py` — **3 passed**

**Configuration:** `BIAS_AUDITOR_ENABLED`, `BIAS_AUDITOR_DRY_RUN`, `BIAS_AUDITOR_LLM_MODEL`, `BIAS_AUDITOR_ANTHROPIC_API_KEY`, `BIAS_AUDITOR_LOG_PATH`.

**Boundary note:** Complements §5.3 compliance sentinel (pre-match SNF gate). Sentinel blocks ineligible candidates; bias auditor certifies objective-only rationale after a confirmed match.

---

### 5.10 Amendment A — Skyflow PII Tokenization Gate (Migration 024)

**Amendment ID:** VCAI-INFRA-SPRINT-2026-07-02-A  
**Recorded:** 2026-07-02 (UTC-4)  
**Purpose:** Cryptographic PII isolation for caregiver onboarding — intercept inbound SSN, date of birth, and Stripe routing tokens; dispatch to Skyflow Vault; persist only opaque token references in PostgreSQL.

**Authority chain:**
```
Inbound onboarding payload
  ├─ POST /api/caregivers/provision
  ├─ POST /api/caregivers/provision-from-provider/{provider_id}
  └─ tokenize_onboarding_pii_if_present() [app/services/caregiver_accounts.py]
      → tokenize_caregiver_pii() [app/services/skyflow_vault_service.py]
          Skyflow Vault insert (live) | deterministic dry-run vault
      → tokens_to_profile_fields() / tokens_to_w2_fields()
      → PostgreSQL token columns only (cleartext never persisted)
      → detokenize_caregiver_pii() — authorized payroll/payout flows only
```

**Tokenized fields:**

| Cleartext (inbound only) | Storage column | Table |
|--------------------------|----------------|-------|
| SSN | `skyflow_ssn_token` | `caregiver_profiles` |
| Date of birth | `skyflow_dob_token` | `caregiver_profiles` |
| Stripe routing token | `skyflow_stripe_routing_token` | `caregiver_w2_employee_accounts` |
| Vault record reference | `skyflow_vault_record_id` | `caregiver_profiles` |

**Key components:**
- `app/services/skyflow_vault_service.py` — `tokenize_caregiver_pii`, `detokenize_caregiver_pii`, `strip_cleartext_pii_from_payload`
- `app/services/caregiver_accounts.py` — ingestion gate; profile + W-2 account persistence
- `app/models/caregiver_accounts.py` — ORM token columns
- `alembic/versions/024_skyflow_pii_tokens.py` — schema migration
- `tests/test_skyflow_vault_service.py` — **4 passed** · caregiver accounts regression — **6 passed**

**Configuration:** `SKYFLOW_VAULT_ENABLED`, `SKYFLOW_VAULT_DRY_RUN`, `SKYFLOW_VAULT_ID`, `SKYFLOW_VAULT_URL`, `SKYFLOW_VAULT_TABLE`, `SKYFLOW_BEARER_TOKEN`, `SKYFLOW_DRY_VAULT_PATH`.

**Dry-run vault:** Local mapping at `logs/skyflow_dry_vault.json` enables tokenize/detokenize round-trip without live Skyflow credentials.

**External keys (deferred):** `SKYFLOW_BEARER_TOKEN`, `SKYFLOW_VAULT_ID`, `SKYFLOW_VAULT_URL` — dry-run operational until keys-assignment day.

---

### 5.12 Amendment B — Maryland AEDT 30-Day Disclosure Compliance Box (Migration 025)

**Amendment ID:** VCAI-INFRA-SPRINT-2026-07-02-B  
**Recorded:** 2026-07-02 (UTC-4)  
**Purpose:** Mandatory user-facing Maryland Automated Employment Decision Tool (AEDT) 30-day notice — checkbox consent before automated shift-routing and hiring tools process license credentials, geographic proximity, and experience parameters.

**Authority chain:**
```
Caregiver intake touchpoint
  ├─ /join landing apply [app/static/landing/]
  ├─ Clinician portal apply [app/static/portal/]
  └─ createAedtDisclosureBox() [app/static/shared/aedt_disclosure.js]
      → consent_aedt_30_day checkbox (client-side validate)
      → POST apply payload with consent_aedt_30_day: true
      → record_maryland_aedt_consent() [app/services/worker_consent.py]
          → maryland_providers.consent_signed_at (Alembic 025)
          → LicenseVerificationLog rows (CONSENT_MARYLAND_AEDT_30_DAY + CONSENT_HB1106_ANTI_BIAS)
      → resolve_provider_consent_signed_at() [compliance_sentinel.py]
      → SNF matching gate HB 1106 clearance (§5.3)
```

**Key components:**
- `app/static/shared/aedt_disclosure.js` — `createAedtDisclosureBox()`, client validation, `consent_aedt_30_day` field export
- `app/static/shared/aedt_disclosure.css` — disclosure box styling
- `app/main.py` — `/shared/` static mount for shared compliance assets
- `app/static/landing/index.html` + `app/static/portal/index.html` — disclosure box embedded on apply forms
- `app/services/worker_consent.py` — `record_maryland_aedt_consent()`, `resolve_provider_consent_signed_at()`
- `app/services/maryland_landing.py` — landing apply handoff with AEDT consent
- `app/middleware/compliance_sentinel.py` — reads `consent_signed_at` for HB 1106 gate
- `app/schemas.py` — `consent_aedt_30_day` required on `MarylandLandingApplyRequest`
- `alembic/versions/025_maryland_aedt_consent_signed_at.py` — schema migration
- `tests/test_maryland_aedt_consent.py` — **2 passed** · compliance sentinel regression — **6 passed**

**Boundary note:** HB 1106 anti-bias consent is no longer auto-recorded at generic apply; it is explicitly bound to the Maryland AEDT disclosure checkbox acceptance. Operators must not bypass the front-end disclosure box for SNF-eligible caregivers.

---

### 5.13 Amendment B — Automated Payroll Onboarding Syncer (Migration 026)

**Amendment ID:** VCAI-INFRA-SPRINT-2026-07-02-B  
**Recorded:** 2026-07-02 (UTC-4)  
**Purpose:** Background employee provisioning — when MBON realtime validation clears to ACTIVE, automatically create the Tier 1 W-2 caregiver as a Gusto Embedded or Check HQ employee without manual payroll desk intervention.

**Authority chain:**
```
MBON credentialing pipeline [app/services/credentialing_pipeline.py]
  → MBON status ACTIVE (realtime validation)
  → sync_payroll_onboarding_after_mbon_clear() [app/services/payroll_onboarding_syncer.py]
      → is_mbon_realtime_clear() gate
      → Tier 1 W-2 bundle resolution (CaregiverProfile + CaregiverW2EmployeeAccount)
      → build_gusto_employee_payload() | Check HQ employee payload
      → POST /v1/employees (Gusto) | POST /employees (Check HQ)
          [docs/payroll/W2-MARYLAND-WITHHOLDING-ENDPOINTS.md]
      → gusto_employee_id persisted (Alembic 026)
      → payroll_onboarding_error on validation/transport failure
```

**Outcome semantics:**
- **SYNCED** — employee created; `gusto_employee_id` stored
- **DRY_RUN** — payload built and logged; no live API call
- **SKIPPED** — sync disabled or MBON not cleared
- **VALIDATION_ERROR** — missing W-2 fields; routes to `QUEUE_MANUAL_PAYROLL_REVIEW`
- **TRANSPORT_ERROR** — API failure; routes to `RETRY_PAYROLL_ONBOARDING`

**Key components:**
- `app/services/payroll_onboarding_syncer.py` — `sync_payroll_onboarding_after_mbon_clear`, `build_gusto_employee_payload`, `is_mbon_realtime_clear`
- `app/services/credentialing_pipeline.py` — post-MBON ACTIVE hook
- `app/models/caregiver_accounts.py` — `gusto_employee_id`, `payroll_onboarding_error` columns
- `alembic/versions/026_gusto_employee_id.py` — schema migration
- `tests/test_payroll_onboarding_syncer.py` — **4 passed**

**Configuration:** `PAYROLL_ONBOARDING_SYNC_ENABLED`, `PAYROLL_ONBOARDING_DRY_RUN`, `PAYROLL_ONBOARDING_TIMEOUT_SECONDS`, `CHECKHQ_COMPANY_ID`, `CHECKHQ_DEFAULT_WORKPLACE_ID`, `GUSTO_API_TOKEN`, `CHECKHQ_API_KEY`.

**Boundary note:** Complements §5.2 payroll tax intercept bridge (net-pay at payout). Onboarding syncer provisions the employee record; intercept bridge computes withholding at instant pay. Neither replaces the other.

**External keys (deferred):** `GUSTO_API_TOKEN`, `CHECKHQ_API_KEY`, `CHECKHQ_COMPANY_ID` — dry-run operational until keys-assignment day.

---

### 5.14 Amendment B — B2B Invoicing Markup Engine (Migration 027)

**Amendment ID:** VCAI-INFRA-SPRINT-2026-07-02-B  
**Recorded:** 2026-07-02 (UTC-4)  
**Purpose:** Itemized facility billing math on shift completion — read logged hours and gross caregiver pay rate, apply configurable platform margin markup, compute employer FICA matching obligation, and persist an audit-grade invoice payload for B2B billing reconciliation.

**Authority chain:**
```
Caregiver shift completion (supervisor timesheet sign-off)
  → record_supervisor_signoff() [api/instant_pay_retention.py]
  → calculate_and_log_facility_invoice_on_shift_complete()
      [app/services/b2b_invoicing_engine.py]
      → _resolve_shift_billing_context() (placement / offer / hours fallback)
      → calculate_facility_invoice_payload()
          Gross Pay        = hours × caregiver pay rate
          Platform Margin  = gross pay × margin_pct (default 40%)
          Employer Taxes   = gross pay × 7.65% (employer FICA match)
          Total Facility Bill = sum of above
      → persist_facility_billing_audit()
      → facility_billing_audit_ledger (Alembic 027)
```

**Itemized invoice line items:**
1. **Gross Pay** — logged shift hours × gross caregiver hourly rate
2. **Platform Margin** — configurable percentage markup on gross pay (default **40%**)
3. **Employer Taxes** — employer FICA matching (**7.65%** Social Security + Medicare)
4. **Total Facility Bill** — Gross Pay + Platform Margin + Employer Taxes

**Key components:**
- `app/services/b2b_invoicing_engine.py` — `calculate_facility_invoice_payload`, `calculate_and_log_facility_invoice_on_shift_complete`, `persist_facility_billing_audit`
- `app/models.py` — `FacilityBillingAuditLedger` ORM
- `alembic/versions/027_facility_billing_audit.py` — schema migration
- `api/instant_pay_retention.py` — supervisor sign-off hook (fail-open on invoice errors)
- `tests/test_b2b_invoicing_engine.py` — **4 passed**

**Configuration:** `B2B_INVOICING_ENABLED`, `B2B_INVOICE_MARGIN_PCT` (default `0.40`).

**Boundary note:** Invoice engine runs at shift completion alongside instant pay sign-off (§5.2). Payout routing to caregivers and facility billing are separate ledgers; facility invoice audit does not mutate caregiver payout amounts.

---

### 5.11 Canonical Lock Attestation

This Sprint Deployment Record is **canonically locked** as of **2026-07-02**, with **Amendment A** and **Amendment B** appended same-day.

- **Lock scope:** Sections 5.1–5.6 define authoritative architecture for the four inaugural sprint integrations. **Sections 5.8–5.10 (Amendment A)** define authoritative architecture for the regional route manifest, HB 1106 bias auditor, and Skyflow PII tokenization gate. **Sections 5.12–5.14 (Amendment B)** define authoritative architecture for the Maryland AEDT disclosure compliance box, automated payroll onboarding syncer, and B2B facility invoicing markup engine. Integration wiring projects, Manus runbooks, and operator documentation must conform to these chains of command.
- **Amendment A attestation:** The three programmatic additions documented in §5.8–5.10 are **canonically locked** under sprint ID `VCAI-INFRA-SPRINT-2026-07-02-A`. No cleartext PII may be persisted to caregiver profile tables when Skyflow tokenization is enabled; HB 1106 match certifications must append to the hash-chained log; localized landing routes must resolve through `route_manifest.py`.
- **Amendment B attestation:** The three programmatic additions documented in §5.12–5.14 are **canonically locked** under sprint ID `VCAI-INFRA-SPRINT-2026-07-02-B`. Maryland AEDT disclosure consent must be captured via `aedt_disclosure.js` before apply submission; `consent_signed_at` on `maryland_providers` is the authoritative HB 1106 consent timestamp for the compliance sentinel. Payroll employee provisioning must route through `sync_payroll_onboarding_after_mbon_clear()` on MBON ACTIVE clearance. Facility billing math on shift completion must route through `calculate_facility_invoice_payload()` and persist to `facility_billing_audit_ledger`; inline facility bill calculations outside this engine are prohibited without governance revision.
- **Amendment policy:** Changes to intercept bridge logic, sentinel gate conditions, OHCQ loop topology, intake queue schema, route manifest matrix, bias auditor metrics, Skyflow tokenization gate, AEDT disclosure copy or consent flow, payroll onboarding sync topology, or B2B invoicing margin/FICA formulas require an explicit append to this section with a new sprint or amendment ID — inline edits to locked subsections are prohibited without governance review.
- **Live-vs-mock:** Sprint modules default to dry-run for external carriers (Stripe, Clay, HeyReach, Workstream, Skyflow, Anthropic, Gusto, Check HQ) until environment keys are assigned. Operators must not describe carrier delivery, live vault tokenization, live payroll employee provisioning, or live facility invoicing export as production until the corresponding Section 1 matrix row is updated.
- **Supersedes:** Amendment A extends — does not replace — the inaugural sprint lock (§5.1–5.6). Amendment B extends — does not replace — Amendment A or the inaugural sprint lock. Baltimore single-route landing (§5.5) remains valid; manifest registry (§5.8) is the authoritative expansion path for new regions and license types.

**Milestone:** Sprint VCAI-INFRA-SPRINT-2026-07-02 — Canonical lock established.  
**Milestone:** Amendment A (VCAI-INFRA-SPRINT-2026-07-02-A) — Route manifest · HB 1106 bias auditor · Skyflow PII vault canonically locked.  
**Milestone:** Amendment B (VCAI-INFRA-SPRINT-2026-07-02-B) — Maryland AEDT disclosure box · payroll onboarding syncer · B2B invoicing markup engine canonically locked.

---

## Document Governance

- This record is the canonical authority for live-vs-mock boundaries, compliance layer roles, matching precedence, audit ledger policy, and **Sprint VCAI-INFRA-SPRINT-2026-07-02 deployment architecture (Section 5 — LOCKED; Amendment A — LOCKED; Amendment B — LOCKED)**.
- Integration and wiring projects must conform to these boundaries; they do not redefine them.
- When a domain transitions from MOCK to PRODUCTION REAL, update Section 1 matrix row and record the environment gate required for that transition.
- No secondary architecture document supersedes this file for Phase A operational boundaries or Sprint 2026-07-02 infrastructure architecture.

**Milestone:** Phase A — Canonical System Record established.  
**Milestone:** Sprint VCAI-INFRA-SPRINT-2026-07-02 — Deployment record canonically locked.  
**Milestone:** Amendment A (VCAI-INFRA-SPRINT-2026-07-02-A) — 9-route manifest · HB 1106 bias auditor · Skyflow PII vault canonically locked.  
**Milestone:** Amendment B (VCAI-INFRA-SPRINT-2026-07-02-B) — Maryland AEDT disclosure box · payroll onboarding syncer · B2B invoicing markup engine canonically locked.

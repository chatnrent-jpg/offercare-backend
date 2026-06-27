from pathlib import Path

ROOT = Path(r"C:\VettedCare.ai\vettedcare-backend")
demo_env = ROOT / "app/services/demo_environment.py"
text = demo_env.read_text(encoding="utf-8")

old1 = """def _demo_clinician_fields(provider: MarylandProvider | None) -> dict[str, str | None]:
    if provider is None:
        return {\"demo_clinician_email\": None, \"demo_clinician_name\": None}
    return {
        \"demo_clinician_email\": provider.email,
        \"demo_clinician_name\": provider.full_name,
    }

def _count_matched_clinicians"""

new1 = """def _demo_clinician_fields(provider: MarylandProvider | None) -> dict[str, str | None]:
    if provider is None:
        return {\"demo_clinician_email\": None, \"demo_clinician_name\": None}
    return {
        \"demo_clinician_email\": provider.email,
        \"demo_clinician_name\": provider.full_name,
    }


def _demo_offer_resettable(offer_id: str | None, compliance_lock_status: str | None) -> bool:
    status = str(compliance_lock_status or \"\")
    return bool(offer_id and status and status != \"BROADCASTING\")


def _build_locked_demo_offer_row(
    db: Session,
    *,
    facility_name: str,
    facility: MarylandFacility,
    offer: OfferCareJobOffer,
) -> dict:
    row = get_open_shift_by_id(db, offer.offer_id)
    lock_status = str(offer.compliance_lock_status)
    if row is None:
        return {
            \"facility_name\": facility_name,
            \"state\": facility.state,
            \"facility_type\": facility.facility_type,
            \"shift_role\": offer.shift_role,
            \"offer_id\": str(offer.offer_id),
            \"loaded\": False,
            \"resettable\": _demo_offer_resettable(str(offer.offer_id), lock_status),
            \"compliance_lock_status\": lock_status,
            \"matched_clinician_count\": 0,
            \"push_ready_count\": 0,
            \"portal_deep_link\": demo_portal_deep_link(str(offer.offer_id)),
            **_demo_clinician_fields(None),
        }
    matched_count, push_ready_count = _count_matched_clinicians(db, row)
    demo_clinician = find_demo_clinician_for_shift(db, row)
    return {
        \"facility_name\": facility_name,
        \"state\": str(row[\"state\"]),
        \"facility_type\": str(row[\"facility_type\"]),
        \"shift_role\": str(row[\"shift_role\"]),
        \"offer_id\": str(row[\"offer_id\"]),
        \"loaded\": False,
        \"resettable\": _demo_offer_resettable(str(row[\"offer_id\"]), lock_status),
        \"compliance_lock_status\": lock_status,
        \"matched_clinician_count\": matched_count,
        \"push_ready_count\": push_ready_count,
        \"portal_deep_link\": demo_portal_deep_link(str(row[\"offer_id\"])),
        **_demo_clinician_fields(demo_clinician),
    }


def _count_matched_clinicians"""

if old1 not in text:
    raise SystemExit("block1 not found")
text = text.replace(old1, new1, 1)

old2 = """    \"Or use Reset on a locked demo shift row to unlock that facility without resetting all 10 demos\",
    \"Reset demo environment to unlock shifts and clear placements before the next walkthrough\","""
new2 = """    \"Or use Reset on a locked demo shift row to unlock that facility without resetting all 10 demos\",
    \"Locked demo rows stay visible with LOCKED status and Reset even when loaded is false after a lock test\",
    \"Reset demo environment to unlock shifts and clear placements before the next walkthrough\","""
if old2 not in text:
    raise SystemExit("block2 not found")
text = text.replace(old2, new2, 1)

old3 = """            if primary_offer is not None and str(primary_offer.compliance_lock_status) != \"BROADCASTING\":
                offers.append(
                    {
                        \"facility_name\": facility_name,
                        \"state\": facility.state,
                        \"facility_type\": facility.facility_type,
                        \"shift_role\": primary_offer.shift_role,
                        \"offer_id\": str(primary_offer.offer_id),
                        \"loaded\": False,
                        \"compliance_lock_status\": str(primary_offer.compliance_lock_status),
                        \"matched_clinician_count\": 0,
                        \"push_ready_count\": 0,
                        \"portal_deep_link\": demo_portal_deep_link(str(primary_offer.offer_id)),
                    }
                )
                continue"""
new3 = """            if primary_offer is not None and str(primary_offer.compliance_lock_status) != \"BROADCASTING\":
                offers.append(
                    _build_locked_demo_offer_row(
                        db,
                        facility_name=facility_name,
                        facility=facility,
                        offer=primary_offer,
                    )
                )
                continue"""
if old3 not in text:
    raise SystemExit("block3 not found")
text = text.replace(old3, new3, 1)

old4 = """                    \"offer_id\": None,
                    \"loaded\": False,
                    \"compliance_lock_status\": None,"""
new4 = """                    \"offer_id\": None,
                    \"loaded\": False,
                    \"resettable\": False,
                    \"compliance_lock_status\": None,"""
if text.count(old4) != 2:
    raise SystemExit(f"block4 count={text.count(old4)}")
text = text.replace(old4, new4)

old5 = """        if row is None:
            offers.append(
                {
                    \"facility_name\": facility_name,
                    \"state\": facility.state,
                    \"facility_type\": facility.facility_type,
                    \"shift_role\": offer.shift_role,
                    \"offer_id\": str(offer.offer_id),
                    \"loaded\": False,
                    \"compliance_lock_status\": offer.compliance_lock_status,
                    \"matched_clinician_count\": 0,
                    \"push_ready_count\": 0,
                    \"portal_deep_link\": demo_portal_deep_link(str(offer.offer_id)),
                }
            )
            continue"""
new5 = """        if row is None:
            offers.append(
                {
                    \"facility_name\": facility_name,
                    \"state\": facility.state,
                    \"facility_type\": facility.facility_type,
                    \"shift_role\": offer.shift_role,
                    \"offer_id\": str(offer.offer_id),
                    \"loaded\": False,
                    \"resettable\": _demo_offer_resettable(str(offer.offer_id), offer.compliance_lock_status),
                    \"compliance_lock_status\": offer.compliance_lock_status,
                    \"matched_clinician_count\": 0,
                    \"push_ready_count\": 0,
                    \"portal_deep_link\": demo_portal_deep_link(str(offer.offer_id)),
                    **_demo_clinician_fields(None),
                }
            )
            continue"""
if old5 not in text:
    raise SystemExit("block5 not found")
text = text.replace(old5, new5, 1)

old6 = """                \"offer_id\": str(row[\"offer_id\"]),
                \"loaded\": True,
                \"compliance_lock_status\": str(row[\"compliance_lock_status\"]),"""
new6 = """                \"offer_id\": str(row[\"offer_id\"]),
                \"loaded\": True,
                \"resettable\": False,
                \"compliance_lock_status\": str(row[\"compliance_lock_status\"]),"""
if old6 not in text:
    raise SystemExit("block6 not found")
text = text.replace(old6, new6, 1)

demo_env.write_text(text, encoding="utf-8")

schemas = ROOT / "app/schemas.py"
stext = schemas.read_text(encoding="utf-8")
sold = """    offer_id: str | None
    loaded: bool
    compliance_lock_status: str | None"""
snew = """    offer_id: str | None
    loaded: bool
    resettable: bool = False
    compliance_lock_status: str | None"""
if sold not in stext:
    raise SystemExit("schema block not found")
schemas.write_text(stext.replace(sold, snew, 1), encoding="utf-8")

deploy = ROOT / "app/services/deploy_walkthrough.py"
dtext = deploy.read_text(encoding="utf-8")
dold = """            \"Or use Reset on a locked demo shift row to unlock one facility without resetting all 10 demos\",
            \"Reset demo environment to unlock shifts and clear placements before the next walkthrough\","""
dnew = """            \"Or use Reset on a locked demo shift row to unlock one facility without resetting all 10 demos\",
            \"Locked demo rows keep LOCKED status and per-row Reset visible after lock test even when loaded is false\",
            \"Reset demo environment to unlock shifts and clear placements before the next walkthrough\","""
if dold not in dtext:
    raise SystemExit("deploy block not found")
deploy.write_text(dtext.replace(dold, dnew, 1), encoding="utf-8")

app_js = ROOT / "app/static/admin/app.js"
js = app_js.read_text(encoding="utf-8")
jsold = "function renderDeployChecklist(data) {"
jsnew = """function demoOfferStatusLabel(row) {
  if (row.compliance_lock_status && row.compliance_lock_status !== \"BROADCASTING\") {
    return row.compliance_lock_status;
  }
  if (row.loaded) return row.compliance_lock_status || \"LOADED\";
  return \"MISSING\";
}

function demoOfferLockTestable(row) {
  return Boolean(row.offer_id && row.loaded && row.compliance_lock_status === \"BROADCASTING\");
}

function demoOfferResettable(row) {
  return Boolean(row.resettable || (row.offer_id && row.compliance_lock_status && row.compliance_lock_status !== \"BROADCASTING\"));
}

function renderDeployChecklist(data) {"""
if jsold not in js:
    raise SystemExit("app.js block1 not found")
js = js.replace(jsold, jsnew, 1)

jsold2 = """            <td>${row.loaded ? badge(row.compliance_lock_status || \"LOADED\") : badge(\"MISSING\")}</td>
            <td>${row.portal_deep_link ? `<a href=\"${row.portal_deep_link}\" target=\"_blank\" rel=\"noopener\">Open</a>` : \"—\"}</td>
            <td>${row.demo_clinician_email || \"—\"}</td>
            <td>${row.offer_id && row.loaded && row.compliance_lock_status === \"BROADCASTING\" ? `<button class=\"btn ghost demo-lock-smoke-offer-btn\" type=\"button\" data-offer-id=\"${row.offer_id}\">Lock test</button>` : \"—\"}</td>
            <td>${row.offer_id && row.loaded && row.compliance_lock_status === \"BROADCASTING\" ? `<button class=\"btn ghost demo-notify-matched-offer-btn\" type=\"button\" data-offer-id=\"${row.offer_id}\">Notify</button>` : \"—\"}</td>
            <td>${row.offer_id && row.compliance_lock_status && row.compliance_lock_status !== \"BROADCASTING\" ? `<button class=\"btn ghost demo-reset-offer-btn\" type=\"button\" data-offer-id=\"${row.offer_id}\">Reset</button>` : \"—\"}</td>"""

jsnew2 = """            <td>${badge(demoOfferStatusLabel(row))}</td>
            <td>${row.portal_deep_link ? `<a href=\"${row.portal_deep_link}\" target=\"_blank\" rel=\"noopener\">Open</a>` : \"—\"}</td>
            <td>${row.demo_clinician_email || \"—\"}</td>
            <td>${demoOfferLockTestable(row) ? `<button class=\"btn ghost demo-lock-smoke-offer-btn\" type=\"button\" data-offer-id=\"${row.offer_id}\">Lock test</button>` : \"—\"}</td>
            <td>${demoOfferLockTestable(row) ? `<button class=\"btn ghost demo-notify-matched-offer-btn\" type=\"button\" data-offer-id=\"${row.offer_id}\">Notify</button>` : \"—\"}</td>
            <td>${demoOfferResettable(row) ? `<button class=\"btn ghost demo-reset-offer-btn\" type=\"button\" data-offer-id=\"${row.offer_id}\">Reset</button>` : \"—\"}</td>"""

if jsold2 not in js:
    raise SystemExit("app.js block2 not found")
app_js.write_text(js.replace(jsold2, jsnew2, 1), encoding="utf-8")

print("patch ok")

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_admin_api_key
from app.database import get_db
from app.schemas import (
    DeployChecklistResponse,
    MarylandLaunchCapstoneResponse,
    MarylandLaunchSmokeRequest,
    MarylandLaunchSmokeResponse,
    MarylandProductionRunbookResponse,
    ProductionLaunchCeremonyResponse,
    ProductionLaunchCeremonyRunRequest,
    ProductionLaunchCeremonyRunResponse,
    ProductionGoLiveRecordResponse,
    ProductionGoLiveRecordSealRequest,
    ProductionGoLiveRecordSealResponse,
    ProductionLaunchAttestationResponse,
    ProductionLaunchAttestationAttestResponse,
    ProductionLaunchPerfectionSealResponse,
    ProductionLaunchPerfectionSealSealRequest,
    ProductionLaunchPerfectionSealSealResponse,
    ProductionLaunchArchiveResponse,
    ProductionLaunchArchiveArchiveResponse,
    ProductionLaunchFinaleResponse,
    ProductionLaunchFinaleRunRequest,
    ProductionLaunchFinaleRunResponse,
    ProductionLaunchPerfectionManifestResponse,
    ProductionLaunchBundleVerifyResponse,
    ProductionPerfectionCapstoneResponse,
    ProductionPerfectionCheckRequest,
    ProductionPerfectionCheckResponse,
    ProductionOpsDashboardResponse,
    TwilioSmsProductionRunbookResponse,
)
from app.services.deploy_walkthrough import (
    build_deploy_checklist,
    build_deploy_checklist_csv,
    build_deploy_checklist_json,
    build_deploy_export_bundle,
)
from app.services.maryland_launch_capstone import (
    build_maryland_launch_capstone,
    build_maryland_launch_capstone_json,
    run_maryland_launch_smoke,
)
from app.services.production_ops_dashboard import as_production_ops_dashboard_response
from app.services.production_launch_ceremony import (
    build_production_launch_ceremony,
    build_production_launch_ceremony_json,
    build_production_launch_ceremony_markdown,
    run_production_launch_ceremony,
)
from app.services.production_go_live_record import (
    build_production_go_live_record,
    build_production_go_live_record_json,
    seal_production_go_live_record,
)
from app.services.production_launch_attestation import (
    attest_production_launch,
    build_production_launch_attestation,
    build_production_launch_attestation_json,
    build_production_launch_attestation_markdown,
)
from app.services.production_launch_perfection_seal import (
    build_production_launch_perfection_seal,
    build_production_launch_perfection_seal_json,
    seal_production_launch_perfection,
)
from app.services.production_launch_archive import (
    archive_production_launch,
    build_production_launch_archive,
    build_production_launch_archive_json,
)
from app.services.production_launch_finale import (
    build_production_launch_finale,
    build_production_launch_finale_json,
    run_production_launch_finale,
)
from app.services.production_launch_perfection_manifest import (
    build_production_launch_perfection_manifest,
    build_production_launch_perfection_manifest_json,
    verify_production_launch_bundle,
)
from app.services.production_perfection_capstone import (
    build_production_perfection_capstone,
    build_production_perfection_capstone_json,
    run_production_perfection_check,
)
from app.services.maryland_production_runbook import (
    build_maryland_production_runbook,
    build_maryland_production_runbook_json,
)

router = APIRouter(prefix="/api/deploy", tags=["deploy"])


def _maryland_production_runbook_response(runbook: dict) -> MarylandProductionRunbookResponse:
    return MarylandProductionRunbookResponse(
        production_ready=runbook["production_ready"],
        summary=runbook["summary"],
        checks=runbook["checks"],
        steps=runbook["steps"],
        env_snippet=runbook["env_snippet"],
        launch_urls=runbook["launch_urls"],
        probes=runbook.get("probes") or [],
    )


def _twilio_sms_production_runbook_response(runbook: dict) -> TwilioSmsProductionRunbookResponse:
    return TwilioSmsProductionRunbookResponse(
        production_ready=runbook["production_ready"],
        live_sms_ready=runbook["live_sms_ready"],
        summary=runbook["summary"],
        checks=runbook["checks"],
        steps=runbook["steps"],
        env_snippet=runbook["env_snippet"],
        twilio_console_steps=runbook["twilio_console_steps"],
    )


def _maryland_launch_capstone_response(capstone: dict) -> MarylandLaunchCapstoneResponse:
    md_runbook = capstone.get("maryland_production_runbook")
    sms_runbook = capstone.get("twilio_sms_production_runbook")
    return MarylandLaunchCapstoneResponse(
        launch_ready=capstone["launch_ready"],
        maryland_production_ready=capstone["maryland_production_ready"],
        twilio_sms_production_ready=capstone["twilio_sms_production_ready"],
        live_sms_ready=capstone["live_sms_ready"],
        live_scrapers_all_live=capstone["live_scrapers_all_live"],
        summary=capstone["summary"],
        checks=capstone["checks"],
        steps=capstone["steps"],
        env_snippet=capstone["env_snippet"],
        launch_urls=capstone["launch_urls"],
        probes=capstone.get("probes") or [],
        maryland_production_runbook=_maryland_production_runbook_response(md_runbook)
        if md_runbook is not None
        else None,
        twilio_sms_production_runbook=_twilio_sms_production_runbook_response(sms_runbook)
        if sms_runbook is not None
        else None,
    )


def _production_perfection_capstone_response(capstone: dict) -> ProductionPerfectionCapstoneResponse:
    ops_dashboard = capstone.get("production_ops_dashboard")
    launch_capstone = capstone.get("maryland_launch_capstone")
    return ProductionPerfectionCapstoneResponse(
        production_perfection_ready=capstone["production_perfection_ready"],
        production_ops_ready=capstone["production_ops_ready"],
        maryland_launch_ready=capstone["maryland_launch_ready"],
        summary=capstone["summary"],
        checks=capstone["checks"],
        steps=capstone["steps"],
        env_snippet=capstone["env_snippet"],
        launch_urls=capstone["launch_urls"],
        production_ops_dashboard=as_production_ops_dashboard_response(ops_dashboard)
        if ops_dashboard is not None
        else None,
        maryland_launch_capstone=_maryland_launch_capstone_response(launch_capstone)
        if launch_capstone is not None
        else None,
    )


def _production_launch_ceremony_response(ceremony: dict) -> ProductionLaunchCeremonyResponse:
    perfection = ceremony.get("production_perfection_capstone")
    return ProductionLaunchCeremonyResponse(
        launch_ceremony_ready=ceremony["launch_ceremony_ready"],
        production_perfection_ready=ceremony["production_perfection_ready"],
        production_ops_ready=ceremony["production_ops_ready"],
        maryland_launch_ready=ceremony["maryland_launch_ready"],
        summary=ceremony["summary"],
        checks=ceremony["checks"],
        steps=ceremony["steps"],
        signoff_markdown=ceremony["signoff_markdown"],
        launch_urls=ceremony["launch_urls"],
        bundle_artifacts=ceremony.get("bundle_artifacts") or [],
        production_perfection_capstone=_production_perfection_capstone_response(perfection)
        if perfection is not None
        else None,
    )


def _production_go_live_record_response(record: dict) -> ProductionGoLiveRecordResponse:
    ceremony = record.get("production_launch_ceremony")
    return ProductionGoLiveRecordResponse(
        production_go_live_record_ready=record["production_go_live_record_ready"],
        launch_ceremony_ready=record["launch_ceremony_ready"],
        production_perfection_ready=record["production_perfection_ready"],
        production_ops_ready=record["production_ops_ready"],
        maryland_launch_ready=record["maryland_launch_ready"],
        sealed=record["sealed"],
        immutable=record["immutable"],
        record_id=record.get("record_id"),
        sealed_at=record.get("sealed_at"),
        summary=record["summary"],
        checks=record["checks"],
        steps=record["steps"],
        launch_urls=record["launch_urls"],
        bundle_artifacts=record.get("bundle_artifacts") or [],
        health_snapshot=record["health_snapshot"],
        production_launch_ceremony=_production_launch_ceremony_response(ceremony)
        if ceremony is not None
        else None,
        sealed_record=record.get("sealed_record"),
    )


def _production_launch_attestation_response(attestation: dict) -> ProductionLaunchAttestationResponse:
    go_live = attestation.get("production_go_live_record")
    return ProductionLaunchAttestationResponse(
        production_launch_attestation_ready=attestation["production_launch_attestation_ready"],
        production_go_live_record_ready=attestation["production_go_live_record_ready"],
        launch_ceremony_ready=attestation["launch_ceremony_ready"],
        production_perfection_ready=attestation["production_perfection_ready"],
        production_ops_ready=attestation["production_ops_ready"],
        maryland_launch_ready=attestation["maryland_launch_ready"],
        attested=attestation["attested"],
        digest_valid=attestation["digest_valid"],
        attestation_id=attestation.get("attestation_id"),
        attested_at=attestation.get("attested_at"),
        record_id=attestation.get("record_id"),
        digest_sha256=attestation.get("digest_sha256"),
        summary=attestation["summary"],
        checks=attestation["checks"],
        steps=attestation["steps"],
        attestation_markdown=attestation["attestation_markdown"],
        launch_urls=attestation["launch_urls"],
        bundle_artifacts=attestation.get("bundle_artifacts") or [],
        production_go_live_record=_production_go_live_record_response(go_live)
        if go_live is not None
        else None,
        attestation_subject=attestation.get("attestation_subject"),
        attestation_record=attestation.get("attestation_record"),
    )


def _production_launch_perfection_seal_response(capstone: dict) -> ProductionLaunchPerfectionSealResponse:
    attestation = capstone.get("production_launch_attestation")
    perfection = capstone.get("production_perfection_capstone")
    return ProductionLaunchPerfectionSealResponse(
        production_launch_perfection_ready=capstone["production_launch_perfection_ready"],
        production_perfection_ready=capstone["production_perfection_ready"],
        production_launch_attestation_ready=capstone["production_launch_attestation_ready"],
        production_go_live_record_ready=capstone["production_go_live_record_ready"],
        launch_ceremony_ready=capstone["launch_ceremony_ready"],
        production_ops_ready=capstone["production_ops_ready"],
        maryland_launch_ready=capstone["maryland_launch_ready"],
        sealed=capstone["sealed"],
        immutable=capstone["immutable"],
        seal_id=capstone.get("seal_id"),
        sealed_at=capstone.get("sealed_at"),
        record_id=capstone.get("record_id"),
        attestation_id=capstone.get("attestation_id"),
        digest_sha256=capstone.get("digest_sha256"),
        summary=capstone["summary"],
        checks=capstone["checks"],
        steps=capstone["steps"],
        launch_urls=capstone["launch_urls"],
        bundle_artifacts=capstone.get("bundle_artifacts") or [],
        production_launch_attestation=_production_launch_attestation_response(attestation)
        if attestation is not None
        else None,
        production_perfection_capstone=_production_perfection_capstone_response(perfection)
        if perfection is not None
        else None,
        perfection_seal_record=capstone.get("perfection_seal_record"),
    )


def _production_launch_archive_response(archive: dict) -> ProductionLaunchArchiveResponse:
    perfection_seal = archive.get("production_launch_perfection_seal")
    return ProductionLaunchArchiveResponse(
        production_launch_archive_ready=archive["production_launch_archive_ready"],
        production_launch_perfection_ready=archive["production_launch_perfection_ready"],
        production_launch_attestation_ready=archive["production_launch_attestation_ready"],
        production_go_live_record_ready=archive["production_go_live_record_ready"],
        launch_ceremony_ready=archive["launch_ceremony_ready"],
        production_perfection_ready=archive["production_perfection_ready"],
        archived=archive["archived"],
        digest_valid=archive["digest_valid"],
        archive_id=archive.get("archive_id"),
        archived_at=archive.get("archived_at"),
        manifest_digest=archive.get("manifest_digest"),
        artifact_count=archive["artifact_count"],
        summary=archive["summary"],
        checks=archive["checks"],
        steps=archive["steps"],
        launch_urls=archive["launch_urls"],
        bundle_artifacts=archive.get("bundle_artifacts") or [],
        manifest=archive.get("manifest") or [],
        production_launch_perfection_seal=_production_launch_perfection_seal_response(perfection_seal)
        if perfection_seal is not None
        else None,
        archive_record=archive.get("archive_record"),
    )


def _production_launch_finale_response(capstone: dict) -> ProductionLaunchFinaleResponse:
    launch_archive = capstone.get("production_launch_archive")
    perfection = capstone.get("production_perfection_capstone")
    return ProductionLaunchFinaleResponse(
        production_launch_finale_ready=capstone["production_launch_finale_ready"],
        production_launch_archive_ready=capstone["production_launch_archive_ready"],
        production_launch_perfection_ready=capstone["production_launch_perfection_ready"],
        production_launch_attestation_ready=capstone["production_launch_attestation_ready"],
        production_go_live_record_ready=capstone["production_go_live_record_ready"],
        launch_ceremony_ready=capstone["launch_ceremony_ready"],
        production_perfection_ready=capstone["production_perfection_ready"],
        completed=capstone["completed"],
        immutable=capstone["immutable"],
        finale_id=capstone.get("finale_id"),
        completed_at=capstone.get("completed_at"),
        manifest_digest=capstone.get("manifest_digest"),
        artifact_count=capstone.get("artifact_count"),
        summary=capstone["summary"],
        checks=capstone["checks"],
        steps=capstone["steps"],
        launch_urls=capstone["launch_urls"],
        bundle_artifacts=capstone.get("bundle_artifacts") or [],
        production_launch_archive=_production_launch_archive_response(launch_archive)
        if launch_archive is not None
        else None,
        production_perfection_capstone=_production_perfection_capstone_response(perfection)
        if perfection is not None
        else None,
        finale_record=capstone.get("finale_record"),
    )


def _production_launch_perfection_manifest_response(
    manifest: dict,
) -> ProductionLaunchPerfectionManifestResponse:
    launch_finale = manifest.get("production_launch_finale")
    return ProductionLaunchPerfectionManifestResponse(
        production_launch_bundle_verified_ready=manifest["production_launch_bundle_verified_ready"],
        production_launch_finale_ready=manifest["production_launch_finale_ready"],
        production_launch_archive_ready=manifest["production_launch_archive_ready"],
        production_launch_perfection_ready=manifest["production_launch_perfection_ready"],
        production_perfection_ready=manifest["production_perfection_ready"],
        verified=manifest["verified"],
        verification_id=manifest.get("verification_id"),
        verified_at=manifest.get("verified_at"),
        manifest_digest=manifest.get("manifest_digest"),
        current_manifest_digest=manifest.get("current_manifest_digest"),
        digest_valid=manifest["digest_valid"],
        matched_count=manifest["matched_count"],
        mismatched_count=manifest["mismatched_count"],
        missing_count=manifest["missing_count"],
        supplemental_count=manifest["supplemental_count"],
        bundle_file_count=manifest["bundle_file_count"],
        summary=manifest["summary"],
        checks=manifest["checks"],
        steps=manifest["steps"],
        launch_urls=manifest["launch_urls"],
        bundle_artifacts=manifest.get("bundle_artifacts") or [],
        verification_entries=manifest.get("verification_entries") or [],
        production_launch_finale=_production_launch_finale_response(launch_finale)
        if launch_finale is not None
        else None,
        verification_record=manifest.get("verification_record"),
    )


@router.get("/checklist", response_model=DeployChecklistResponse, dependencies=[Depends(require_admin_api_key)])
def deploy_checklist(db: Session = Depends(get_db)):
    payload = build_deploy_checklist(db)
    runbook = payload.get("maryland_production_runbook")
    if runbook is not None:
        payload["maryland_production_runbook"] = _maryland_production_runbook_response(runbook)
    sms_runbook = payload.get("twilio_sms_production_runbook")
    if sms_runbook is not None:
        payload["twilio_sms_production_runbook"] = _twilio_sms_production_runbook_response(sms_runbook)
    launch_capstone = payload.get("maryland_launch_capstone")
    if launch_capstone is not None:
        payload["maryland_launch_capstone"] = _maryland_launch_capstone_response(launch_capstone)
    ops_dashboard = payload.get("production_ops_dashboard")
    if ops_dashboard is not None:
        payload["production_ops_dashboard"] = as_production_ops_dashboard_response(ops_dashboard)
    perfection_capstone = payload.get("production_perfection_capstone")
    if perfection_capstone is not None:
        payload["production_perfection_capstone"] = _production_perfection_capstone_response(perfection_capstone)
    launch_ceremony = payload.get("production_launch_ceremony")
    if launch_ceremony is not None:
        payload["production_launch_ceremony"] = _production_launch_ceremony_response(launch_ceremony)
    go_live_record = payload.get("production_go_live_record")
    if go_live_record is not None:
        payload["production_go_live_record"] = _production_go_live_record_response(go_live_record)
    launch_attestation = payload.get("production_launch_attestation")
    if launch_attestation is not None:
        payload["production_launch_attestation"] = _production_launch_attestation_response(launch_attestation)
    perfection_seal = payload.get("production_launch_perfection_seal")
    if perfection_seal is not None:
        payload["production_launch_perfection_seal"] = _production_launch_perfection_seal_response(perfection_seal)
    launch_archive = payload.get("production_launch_archive")
    if launch_archive is not None:
        payload["production_launch_archive"] = _production_launch_archive_response(launch_archive)
    launch_finale = payload.get("production_launch_finale")
    if launch_finale is not None:
        payload["production_launch_finale"] = _production_launch_finale_response(launch_finale)
    bundle_verification = payload.get("production_launch_bundle_verification")
    if bundle_verification is not None:
        payload["production_launch_bundle_verification"] = (
            _production_launch_perfection_manifest_response(bundle_verification)
        )
    return DeployChecklistResponse(**payload)


@router.get(
    "/maryland-production-runbook",
    response_model=MarylandProductionRunbookResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def maryland_production_runbook(include_probes: bool = False, db: Session = Depends(get_db)):
    runbook = build_maryland_production_runbook(db, include_probes=include_probes)
    return _maryland_production_runbook_response(runbook)


@router.get("/maryland-production-runbook.json", dependencies=[Depends(require_admin_api_key)])
def maryland_production_runbook_json_download(include_probes: bool = False, db: Session = Depends(get_db)):
    payload = build_maryland_production_runbook_json(db, include_probes=include_probes)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get(
    "/maryland-launch-capstone",
    response_model=MarylandLaunchCapstoneResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def maryland_launch_capstone(include_probes: bool = False, db: Session = Depends(get_db)):
    capstone = build_maryland_launch_capstone(db, include_probes=include_probes)
    return _maryland_launch_capstone_response(capstone)


@router.get("/maryland-launch-capstone.json", dependencies=[Depends(require_admin_api_key)])
def maryland_launch_capstone_json_download(include_probes: bool = False, db: Session = Depends(get_db)):
    payload = build_maryland_launch_capstone_json(db, include_probes=include_probes)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/maryland-launch-smoke",
    response_model=MarylandLaunchSmokeResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def maryland_launch_smoke(
    payload: MarylandLaunchSmokeRequest | None = None,
    db: Session = Depends(get_db),
):
    result = run_maryland_launch_smoke(
        db,
        phone_number=payload.phone_number if payload else None,
        probe_scrapers=payload.probe_scrapers if payload else True,
    )
    return MarylandLaunchSmokeResponse(**result)


@router.get(
    "/production-perfection-capstone",
    response_model=ProductionPerfectionCapstoneResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_perfection_capstone(db: Session = Depends(get_db)):
    capstone = build_production_perfection_capstone(db)
    return _production_perfection_capstone_response(capstone)


@router.get("/production-perfection-capstone.json", dependencies=[Depends(require_admin_api_key)])
def production_perfection_capstone_json_download(db: Session = Depends(get_db)):
    payload = build_production_perfection_capstone_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-perfection-check",
    response_model=ProductionPerfectionCheckResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_perfection_check(
    payload: ProductionPerfectionCheckRequest | None = None,
    db: Session = Depends(get_db),
):
    result = run_production_perfection_check(
        db,
        phone_number=payload.phone_number if payload else None,
        probe_scrapers=payload.probe_scrapers if payload else True,
    )
    return ProductionPerfectionCheckResponse(**result)


@router.get(
    "/production-launch-ceremony",
    response_model=ProductionLaunchCeremonyResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_ceremony(db: Session = Depends(get_db)):
    ceremony = build_production_launch_ceremony(db)
    return _production_launch_ceremony_response(ceremony)


@router.get("/production-launch-ceremony.md", dependencies=[Depends(require_admin_api_key)])
def production_launch_ceremony_markdown_download(db: Session = Depends(get_db)):
    payload = build_production_launch_ceremony_markdown(db)
    return Response(
        content=payload["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/production-launch-ceremony.json", dependencies=[Depends(require_admin_api_key)])
def production_launch_ceremony_json_download(db: Session = Depends(get_db)):
    payload = build_production_launch_ceremony_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-launch-ceremony/run",
    response_model=ProductionLaunchCeremonyRunResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_ceremony_run(
    payload: ProductionLaunchCeremonyRunRequest | None = None,
    db: Session = Depends(get_db),
):
    result = run_production_launch_ceremony(
        db,
        phone_number=payload.phone_number if payload else None,
        probe_scrapers=payload.probe_scrapers if payload else True,
    )
    return ProductionLaunchCeremonyRunResponse(**result)


@router.get(
    "/production-go-live-record",
    response_model=ProductionGoLiveRecordResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_go_live_record(db: Session = Depends(get_db)):
    record = build_production_go_live_record(db)
    return _production_go_live_record_response(record)


@router.get("/production-go-live-record.json", dependencies=[Depends(require_admin_api_key)])
def production_go_live_record_json_download(db: Session = Depends(get_db)):
    payload = build_production_go_live_record_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-go-live-record/seal",
    response_model=ProductionGoLiveRecordSealResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_go_live_record_seal(
    payload: ProductionGoLiveRecordSealRequest | None = None,
    db: Session = Depends(get_db),
):
    result = seal_production_go_live_record(
        db,
        phone_number=payload.phone_number if payload else None,
        probe_scrapers=payload.probe_scrapers if payload else True,
    )
    ceremony_run = result.get("ceremony_run")
    if ceremony_run is not None:
        result["ceremony_run"] = ProductionLaunchCeremonyRunResponse(**ceremony_run)
    return ProductionGoLiveRecordSealResponse(**result)


@router.get(
    "/production-launch-attestation",
    response_model=ProductionLaunchAttestationResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_attestation(db: Session = Depends(get_db)):
    attestation = build_production_launch_attestation(db)
    return _production_launch_attestation_response(attestation)


@router.get("/production-launch-attestation.md", dependencies=[Depends(require_admin_api_key)])
def production_launch_attestation_markdown_download(db: Session = Depends(get_db)):
    payload = build_production_launch_attestation_markdown(db)
    return Response(
        content=payload["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/production-launch-attestation.json", dependencies=[Depends(require_admin_api_key)])
def production_launch_attestation_json_download(db: Session = Depends(get_db)):
    payload = build_production_launch_attestation_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-launch-attestation/attest",
    response_model=ProductionLaunchAttestationAttestResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_attestation_attest(db: Session = Depends(get_db)):
    result = attest_production_launch(db)
    return ProductionLaunchAttestationAttestResponse(**result)


@router.get(
    "/production-launch-perfection-seal",
    response_model=ProductionLaunchPerfectionSealResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_perfection_seal(db: Session = Depends(get_db)):
    capstone = build_production_launch_perfection_seal(db)
    return _production_launch_perfection_seal_response(capstone)


@router.get("/production-launch-perfection-seal.json", dependencies=[Depends(require_admin_api_key)])
def production_launch_perfection_seal_json_download(db: Session = Depends(get_db)):
    payload = build_production_launch_perfection_seal_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-launch-perfection-seal/seal",
    response_model=ProductionLaunchPerfectionSealSealResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_perfection_seal_run(
    payload: ProductionLaunchPerfectionSealSealRequest | None = None,
    db: Session = Depends(get_db),
):
    result = seal_production_launch_perfection(
        db,
        phone_number=payload.phone_number if payload else None,
        probe_scrapers=payload.probe_scrapers if payload else True,
    )
    return ProductionLaunchPerfectionSealSealResponse(**result)


@router.get(
    "/production-launch-archive",
    response_model=ProductionLaunchArchiveResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_archive(db: Session = Depends(get_db)):
    archive = build_production_launch_archive(db)
    return _production_launch_archive_response(archive)


@router.get("/production-launch-archive.json", dependencies=[Depends(require_admin_api_key)])
def production_launch_archive_json_download(db: Session = Depends(get_db)):
    payload = build_production_launch_archive_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-launch-archive/archive",
    response_model=ProductionLaunchArchiveArchiveResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_archive_run(db: Session = Depends(get_db)):
    result = archive_production_launch(db)
    return ProductionLaunchArchiveArchiveResponse(**result)


@router.get(
    "/production-launch-finale",
    response_model=ProductionLaunchFinaleResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_finale(db: Session = Depends(get_db)):
    capstone = build_production_launch_finale(db)
    return _production_launch_finale_response(capstone)


@router.get("/production-launch-finale.json", dependencies=[Depends(require_admin_api_key)])
def production_launch_finale_json_download(db: Session = Depends(get_db)):
    payload = build_production_launch_finale_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-launch-finale/run",
    response_model=ProductionLaunchFinaleRunResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_finale_run(
    payload: ProductionLaunchFinaleRunRequest | None = None,
    db: Session = Depends(get_db),
):
    result = run_production_launch_finale(
        db,
        phone_number=payload.phone_number if payload else None,
        probe_scrapers=payload.probe_scrapers if payload else True,
    )
    return ProductionLaunchFinaleRunResponse(**result)


@router.get(
    "/production-launch-perfection-manifest",
    response_model=ProductionLaunchPerfectionManifestResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_perfection_manifest(db: Session = Depends(get_db)):
    manifest = build_production_launch_perfection_manifest(db)
    return _production_launch_perfection_manifest_response(manifest)


@router.get(
    "/production-launch-perfection-manifest.json",
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_perfection_manifest_json_download(db: Session = Depends(get_db)):
    payload = build_production_launch_perfection_manifest_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.post(
    "/production-launch-perfection-manifest/verify",
    response_model=ProductionLaunchBundleVerifyResponse,
    dependencies=[Depends(require_admin_api_key)],
)
def production_launch_bundle_verify(db: Session = Depends(get_db)):
    result = verify_production_launch_bundle(db)
    return ProductionLaunchBundleVerifyResponse(**result)


@router.get("/checklist.json", dependencies=[Depends(require_admin_api_key)])
def deploy_checklist_json_download(db: Session = Depends(get_db)):
    payload = build_deploy_checklist_json(db)
    return Response(
        content=payload["content"],
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/checklist.csv", dependencies=[Depends(require_admin_api_key)])
def deploy_checklist_csv_download(db: Session = Depends(get_db)):
    payload = build_deploy_checklist_csv(db)
    return Response(
        content=payload["content"],
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )


@router.get("/deploy-bundle.zip", dependencies=[Depends(require_admin_api_key)])
def deploy_export_bundle_download(db: Session = Depends(get_db)):
    payload = build_deploy_export_bundle(db)
    return Response(
        content=payload["content"],
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}"'},
    )

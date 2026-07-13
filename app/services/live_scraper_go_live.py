"""Go-live profile for flipping live scraper channels off dry-run."""

from __future__ import annotations

from app.config import settings
from app.services.live_scraper_urls import CHANNEL_ADAPTER_PATHS, effective_live_scraper_url, live_scraper_gateway_base
from app.services.live_scrapers import live_scraper_channels


def build_live_scraper_go_live_profile() -> dict:
    gateway = live_scraper_gateway_base()
    env_lines = [
        "# Live scraper go-live profile (VettedMe step 133)",
        f"LIVE_SCRAPER_GATEWAY_BASE_URL={gateway or 'http://127.0.0.1:8000/api/adapters'}",
        "LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=true",
        "MBON_VERIFY_DRY_RUN=false",
        "OIG_SCREEN_DRY_RUN=false",
        "MD_JUDICIARY_DRY_RUN=false",
        "JOB_BOARD_SCRAPE_DRY_RUN=false",
        "VMS_INGEST_DRY_RUN=false",
    ]
    channels = []
    for channel in live_scraper_channels():
        endpoint = effective_live_scraper_url(channel.id)
        channels.append(
            {
                "id": channel.id,
                "name": channel.name,
                "dry_run": channel.dry_run,
                "configured": channel.configured,
                "live_ready": channel.live_ready,
                "endpoint": endpoint or None,
                "adapter_path": CHANNEL_ADAPTER_PATHS.get(channel.id),
                "config_hint": channel.config_hint,
            }
        )
    live_ready_count = sum(1 for row in channels if row["live_ready"])
    return {
        "gateway_base_url": gateway or None,
        "mock_adapters_enabled": settings.LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED,
        "total_channels": len(channels),
        "live_ready_count": live_ready_count,
        "all_live": live_ready_count == len(channels),
        "env_snippet": "\n".join(env_lines),
        "channels": channels,
        "steps": [
            "Set LIVE_SCRAPER_GATEWAY_BASE_URL to your adapter service (local mock: http://127.0.0.1:8000/api/adapters)",
            "Enable LIVE_SCRAPER_MOCK_ADAPTERS_ENABLED=true for local in-process adapters, or point gateway at production adapters",
            "Flip MBON_VERIFY_DRY_RUN, OIG_SCREEN_DRY_RUN, MD_JUDICIARY_DRY_RUN, JOB_BOARD_SCRAPE_DRY_RUN, and VMS_INGEST_DRY_RUN to false",
            "Admin → Integrations → Live scrapers — confirm all five channels show LIVE READY",
            "Admin → Integrations → Probe live scrapers to verify adapter latency and HTTP health",
            "Deploy checklist live_scrapers item should move from pending to ready when all_live is true",
        ],
    }

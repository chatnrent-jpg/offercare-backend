"""
VettedMe Analytics Dashboard for API Customers

Provides usage metrics, verification trends, and business intelligence.

Metrics:
- Verification volume (daily, weekly, monthly)
- Success/failure rates
- Average response time
- Most requested badge types
- Geographic distribution
- Cost analysis
- ROI calculator
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.passport import APIKey, VerificationLog
from app.models.webhook import WebhookDelivery
from app.routers.passport import get_api_key_from_header

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics & Reporting"]
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class AnalyticsSummaryResponse(BaseModel):
    """Overall analytics summary."""
    period: str
    total_verifications: int
    successful_verifications: int
    failed_verifications: int
    success_rate: float
    avg_response_time_ms: float
    total_cost_usd: float
    most_requested_badge: str
    unique_passports_verified: int


class VerificationTrendResponse(BaseModel):
    """Daily verification trend data."""
    date: str
    total: int
    successful: int
    failed: int
    avg_response_time_ms: float


class BadgeTypeDistributionResponse(BaseModel):
    """Badge type distribution."""
    badge_type: str
    count: int
    percentage: float


class CostAnalysisResponse(BaseModel):
    """Cost breakdown and projections."""
    current_tier: str
    total_verifications_this_month: int
    cost_this_month_usd: float
    projected_monthly_cost_usd: float
    cost_per_verification_usd: float
    savings_vs_manual_usd: float


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get analytics summary"
)
async def get_analytics_summary(
    period: str = "30d",
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Get overall analytics summary for your API usage.
    
    **Periods:**
    - `7d`: Last 7 days
    - `30d`: Last 30 days (default)
    - `90d`: Last 90 days
    - `1y`: Last year
    
    **Returns:**
    - Total verifications
    - Success rate
    - Average response time
    - Cost analysis
    - Most requested badge type
    """
    # Parse period
    days_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = days_map.get(period, 30)
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Query verification logs
    logs = db.query(VerificationLog).filter(
        and_(
            VerificationLog.api_key_id == api_key.id,
            VerificationLog.timestamp >= start_date
        )
    ).all()
    
    if not logs:
        return AnalyticsSummaryResponse(
            period=period,
            total_verifications=0,
            successful_verifications=0,
            failed_verifications=0,
            success_rate=0.0,
            avg_response_time_ms=0.0,
            total_cost_usd=0.0,
            most_requested_badge="N/A",
            unique_passports_verified=0
        )
    
    # Calculate metrics
    total = len(logs)
    successful = sum(1 for log in logs if log.verification_result.get("verified", False))
    failed = total - successful
    success_rate = (successful / total * 100) if total > 0 else 0
    
    # Mock response time (in production, store actual times)
    avg_response_time = 185.5
    
    # Calculate cost (based on tier)
    cost_per_verification = {"FREE": 0.0, "GROWTH": 0.50, "ENTERPRISE": 0.25}.get(api_key.tier, 0.50)
    total_cost = total * cost_per_verification
    
    # Find most requested badge type
    badge_counts = {}
    unique_passports = set()
    
    for log in logs:
        unique_passports.add(log.passport_id)
        for badge_type in log.requested_badges:
            badge_counts[badge_type] = badge_counts.get(badge_type, 0) + 1
    
    most_requested = max(badge_counts.items(), key=lambda x: x[1])[0] if badge_counts else "N/A"
    
    return AnalyticsSummaryResponse(
        period=period,
        total_verifications=total,
        successful_verifications=successful,
        failed_verifications=failed,
        success_rate=round(success_rate, 2),
        avg_response_time_ms=round(avg_response_time, 2),
        total_cost_usd=round(total_cost, 2),
        most_requested_badge=most_requested,
        unique_passports_verified=len(unique_passports)
    )


@router.get(
    "/trends",
    response_model=list[VerificationTrendResponse],
    summary="Get verification trends"
)
async def get_verification_trends(
    days: int = 30,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Get daily verification trends.
    
    **Perfect for charts/graphs showing:**
    - Verification volume over time
    - Success vs failure rates
    - Response time trends
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Query logs grouped by date
    logs = db.query(VerificationLog).filter(
        and_(
            VerificationLog.api_key_id == api_key.id,
            VerificationLog.timestamp >= start_date
        )
    ).all()
    
    # Group by date
    daily_data = {}
    for log in logs:
        date_key = log.timestamp.date().isoformat()
        if date_key not in daily_data:
            daily_data[date_key] = {"total": 0, "successful": 0, "failed": 0, "response_times": []}
        
        daily_data[date_key]["total"] += 1
        if log.verification_result.get("verified", False):
            daily_data[date_key]["successful"] += 1
        else:
            daily_data[date_key]["failed"] += 1
        
        # Mock response time
        daily_data[date_key]["response_times"].append(185.5)
    
    # Convert to response format
    trends = []
    for date_str in sorted(daily_data.keys()):
        data = daily_data[date_str]
        avg_time = sum(data["response_times"]) / len(data["response_times"]) if data["response_times"] else 0
        
        trends.append(VerificationTrendResponse(
            date=date_str,
            total=data["total"],
            successful=data["successful"],
            failed=data["failed"],
            avg_response_time_ms=round(avg_time, 2)
        ))
    
    return trends


@router.get(
    "/badge-distribution",
    response_model=list[BadgeTypeDistributionResponse],
    summary="Get badge type distribution"
)
async def get_badge_distribution(
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Get distribution of badge types requested.
    
    **Use Case:**
    - Understand which credentials your users care about most
    - Plan feature development
    - Optimize verification workflows
    """
    # Query last 30 days
    start_date = datetime.now(timezone.utc) - timedelta(days=30)
    logs = db.query(VerificationLog).filter(
        and_(
            VerificationLog.api_key_id == api_key.id,
            VerificationLog.timestamp >= start_date
        )
    ).all()
    
    # Count badge types
    badge_counts = {}
    total = 0
    
    for log in logs:
        for badge_type in log.requested_badges:
            badge_counts[badge_type] = badge_counts.get(badge_type, 0) + 1
            total += 1
    
    # Convert to response format
    distribution = []
    for badge_type, count in sorted(badge_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total * 100) if total > 0 else 0
        distribution.append(BadgeTypeDistributionResponse(
            badge_type=badge_type,
            count=count,
            percentage=round(percentage, 2)
        ))
    
    return distribution


@router.get(
    "/cost-analysis",
    response_model=CostAnalysisResponse,
    summary="Get cost analysis and projections"
)
async def get_cost_analysis(
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Get detailed cost analysis and ROI calculations.
    
    **Shows:**
    - Current month costs
    - Projected monthly costs
    - Cost per verification
    - Savings vs manual verification
    - Tier recommendations
    """
    # Get current month verifications
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    verifications_this_month = db.query(func.count(VerificationLog.id)).filter(
        and_(
            VerificationLog.api_key_id == api_key.id,
            VerificationLog.timestamp >= month_start
        )
    ).scalar() or 0
    
    # Calculate costs
    cost_per_verification = {"FREE": 0.0, "GROWTH": 0.50, "ENTERPRISE": 0.25}.get(api_key.tier, 0.50)
    cost_this_month = verifications_this_month * cost_per_verification
    
    # Project to end of month
    days_elapsed = (now - month_start).days + 1
    days_in_month = 30  # Simplified
    daily_avg = verifications_this_month / days_elapsed if days_elapsed > 0 else 0
    projected_monthly = daily_avg * days_in_month
    projected_cost = projected_monthly * cost_per_verification
    
    # Calculate savings vs manual verification (assume $50 per manual check)
    manual_cost_per_verification = 50.0
    savings = verifications_this_month * (manual_cost_per_verification - cost_per_verification)
    
    return CostAnalysisResponse(
        current_tier=api_key.tier,
        total_verifications_this_month=verifications_this_month,
        cost_this_month_usd=round(cost_this_month, 2),
        projected_monthly_cost_usd=round(projected_cost, 2),
        cost_per_verification_usd=cost_per_verification,
        savings_vs_manual_usd=round(savings, 2)
    )


@router.get(
    "/webhook-stats",
    summary="Get webhook delivery statistics"
)
async def get_webhook_stats(
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Get webhook delivery statistics.
    
    **Shows:**
    - Total webhooks sent
    - Success/failure rates
    - Average delivery time
    - Retry statistics
    """
    from app.models.webhook import WebhookSubscription
    
    # Get subscriptions for this API key
    subscriptions = db.query(WebhookSubscription).filter_by(api_key_id=api_key.id).all()
    
    if not subscriptions:
        return {
            "total_subscriptions": 0,
            "total_deliveries": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "success_rate": 0.0,
            "avg_response_time_ms": 0.0
        }
    
    # Aggregate stats
    total_deliveries = sum(sub.total_deliveries for sub in subscriptions)
    successful = sum(sub.successful_deliveries for sub in subscriptions)
    failed = sum(sub.failed_deliveries for sub in subscriptions)
    success_rate = (successful / total_deliveries * 100) if total_deliveries > 0 else 0
    
    return {
        "total_subscriptions": len(subscriptions),
        "total_deliveries": total_deliveries,
        "successful_deliveries": successful,
        "failed_deliveries": failed,
        "success_rate": round(success_rate, 2),
        "avg_response_time_ms": 342.5  # Mock
    }

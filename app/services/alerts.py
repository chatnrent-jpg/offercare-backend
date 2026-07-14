"""
Infrastructure Alert Engine
Phase 2: Intelligence & Compliance - Operations

Handles critical infrastructure alerts and notifications.
Supports Slack webhooks, email alerts, and audit trail logging.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger("InfrastructureAlerts")


class InfrastructureAlertEngine:
    """
    Critical infrastructure alerting system for OHCQ compliance monitoring.
    
    Features:
    - Slack webhook notifications
    - Email alerts (future)
    - Audit trail logging
    - Graceful degradation if webhook unavailable
    """
    
    def __init__(self, slack_webhook_url: Optional[str] = None):
        """
        Initialize alert engine.
        
        Args:
            slack_webhook_url: Slack incoming webhook URL for alerts
                              Falls back to SLACK_INFRA_WEBHOOK_URL env var
        """
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_INFRA_WEBHOOK_URL")
        self.alert_log = []  # In-memory alert history
    
    def dispatch_critical_scraper_failure(
        self,
        scraper_name: str,
        error_message: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Dispatch critical alert when scraper fails.
        
        Args:
            scraper_name: Name of the failed scraper (e.g., "MBON Scraper")
            error_message: Detailed error message
            additional_context: Optional metadata (facility_id, license_number, etc.)
        
        Returns:
            Dictionary with alert status and details
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Build alert payload
        alert_data = {
            "alert_id": f"alert-{datetime.now(timezone.utc).timestamp()}",
            "timestamp": timestamp,
            "severity": "CRITICAL",
            "alert_type": "SCRAPER_FAILURE",
            "scraper_name": scraper_name,
            "error_message": error_message,
            "additional_context": additional_context or {},
            "status": "dispatched"
        }
        
        # Log to audit trail
        logger.critical(
            f"CRITICAL SCRAPER FAILURE: {scraper_name} - {error_message}",
            extra=alert_data
        )
        
        # Store in memory
        self.alert_log.append(alert_data)
        
        # Attempt Slack notification
        slack_result = self._send_slack_alert(alert_data)
        alert_data["slack_notification"] = slack_result
        
        return alert_data
    
    def _send_slack_alert(self, alert_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Send alert to Slack webhook.
        
        Args:
            alert_data: Alert information to send
        
        Returns:
            Dictionary with send status
        """
        if not self.slack_webhook_url:
            logger.warning(
                "SLACK_INFRA_WEBHOOK_URL not configured. Alert logged but not sent to Slack."
            )
            return {
                "status": "skipped",
                "reason": "webhook_not_configured"
            }
        
        # Format Slack message
        slack_payload = {
            "text": f"🚨 *CRITICAL INFRASTRUCTURE ALERT*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 Critical Scraper Failure",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Scraper:*\n{alert_data['scraper_name']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Severity:*\n{alert_data['severity']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Timestamp:*\n{alert_data['timestamp']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Alert ID:*\n{alert_data['alert_id']}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error Message:*\n```{alert_data['error_message']}```"
                    }
                }
            ]
        }
        
        # Add additional context if present
        if alert_data["additional_context"]:
            context_text = "\n".join(
                f"• {key}: {value}"
                for key, value in alert_data["additional_context"].items()
            )
            slack_payload["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Additional Context:*\n{context_text}"
                }
            })
        
        try:
            # Send to Slack
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    self.slack_webhook_url,
                    json=slack_payload
                )
                
                if response.status_code == 200:
                    logger.info(f"Slack alert sent successfully: {alert_data['alert_id']}")
                    return {
                        "status": "sent",
                        "http_status": response.status_code
                    }
                else:
                    logger.error(
                        f"Slack webhook returned {response.status_code}: {response.text}"
                    )
                    return {
                        "status": "failed",
                        "http_status": response.status_code,
                        "error": response.text
                    }
        
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack alert: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def dispatch_compliance_warning(
        self,
        warning_type: str,
        message: str,
        affected_credentials: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Dispatch warning alert for compliance issues.
        
        Args:
            warning_type: Type of warning (e.g., "STALE_VERIFICATIONS")
            message: Warning message
            affected_credentials: List of affected credential IDs
        
        Returns:
            Dictionary with alert status
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        alert_data = {
            "alert_id": f"warn-{datetime.now(timezone.utc).timestamp()}",
            "timestamp": timestamp,
            "severity": "WARNING",
            "alert_type": "COMPLIANCE_WARNING",
            "warning_type": warning_type,
            "message": message,
            "affected_credentials": affected_credentials or [],
            "status": "dispatched"
        }
        
        logger.warning(
            f"COMPLIANCE WARNING: {warning_type} - {message}",
            extra=alert_data
        )
        
        self.alert_log.append(alert_data)
        
        return alert_data
    
    def get_alert_history(self, limit: int = 10) -> list:
        """
        Get recent alert history.
        
        Args:
            limit: Maximum number of alerts to return
        
        Returns:
            List of recent alerts
        """
        return self.alert_log[-limit:]
    
    def get_critical_alerts_count(self) -> int:
        """
        Get count of critical alerts.
        
        Returns:
            Number of critical alerts in history
        """
        return sum(
            1 for alert in self.alert_log
            if alert.get("severity") == "CRITICAL"
        )


# Convenience function for quick alerts
def dispatch_scraper_failure(
    scraper_name: str,
    error_message: str,
    slack_webhook_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick function to dispatch scraper failure alert.
    
    Args:
        scraper_name: Name of the failed scraper
        error_message: Error message
        slack_webhook_url: Optional Slack webhook URL
    
    Returns:
        Alert dispatch result
    """
    engine = InfrastructureAlertEngine(slack_webhook_url)
    return engine.dispatch_critical_scraper_failure(scraper_name, error_message)

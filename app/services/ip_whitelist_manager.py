"""
IP Whitelist Manager — Corporate Network Protection

Sprint: VCAI-TIER4-HARDENING-2026-07-07
Purpose: Manage trusted IP addresses to prevent false positives.

Use Cases:
- Large facility with 10+ admins on same corporate IP
- Hospital network with NAT gateway
- Enterprise client with VPN
- Trusted API consumers

Management:
- Add IP to whitelist
- Remove IP from whitelist
- Check whitelist status
- Audit whitelist entries
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import IPWhitelist


class IPWhitelistManager:
    """
    Manage IP whitelist for corporate network protection.
    
    Main entry points:
    - add_to_whitelist(ip_address, facility_id, reason)
    - remove_from_whitelist(ip_address)
    - is_whitelisted(ip_address)
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize with optional database session."""
        self.db = db
        self._should_close_db = db is None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.db is None:
            self.db = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._should_close_db and self.db:
            await self.db.close()
    
    async def add_to_whitelist(
        self,
        ip_address: str,
        facility_id: Optional[UUID] = None,
        reason: str = "Corporate network",
        added_by: str = "System",
        expires_days: Optional[int] = None
    ) -> UUID:
        """
        Add IP to whitelist.
        
        Args:
            ip_address: IP address or CIDR range
            facility_id: Optional facility UUID
            reason: Why this IP is whitelisted
            added_by: Who added it
            expires_days: Optional expiration (e.g., 90 days)
        
        Returns:
            Whitelist entry UUID
        """
        # Check if already exists
        existing = await self._get_whitelist_entry(ip_address)
        
        if existing:
            # Update existing
            existing.is_active = "1"
            existing.whitelist_reason = reason
            if expires_days:
                existing.expires_at = datetime.utcnow() + timedelta(days=expires_days)
            await self.db.commit()
            await self.db.refresh(existing)
            
            print(f"[WHITELIST] Updated: {ip_address} - {reason}")
            return existing.id
        
        # Create new
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        whitelist_entry = IPWhitelist(
            facility_id=facility_id,
            ip_address=ip_address,
            whitelist_reason=reason,
            added_by=added_by,
            expires_at=expires_at
        )
        
        self.db.add(whitelist_entry)
        await self.db.commit()
        await self.db.refresh(whitelist_entry)
        
        print(f"[WHITELIST] Added: {ip_address} - {reason}")
        
        return whitelist_entry.id
    
    async def remove_from_whitelist(self, ip_address: str) -> bool:
        """
        Remove IP from whitelist.
        
        Returns True if removed, False if not found.
        """
        entry = await self._get_whitelist_entry(ip_address)
        
        if entry:
            entry.is_active = "0"
            await self.db.commit()
            print(f"[WHITELIST] Removed: {ip_address}")
            return True
        
        return False
    
    async def is_whitelisted(self, ip_address: str) -> bool:
        """Check if IP is currently whitelisted."""
        entry = await self._get_whitelist_entry(ip_address)
        
        if not entry or entry.is_active != "1":
            return False
        
        # Check expiration
        if entry.expires_at and entry.expires_at < datetime.utcnow():
            entry.is_active = "0"
            await self.db.commit()
            return False
        
        return True
    
    async def get_all_whitelisted(self) -> List[IPWhitelist]:
        """Get all active whitelist entries."""
        stmt = select(IPWhitelist).where(IPWhitelist.is_active == "1")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def _get_whitelist_entry(self, ip_address: str) -> Optional[IPWhitelist]:
        """Get whitelist entry by IP."""
        stmt = select(IPWhitelist).where(IPWhitelist.ip_address == ip_address)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


# Convenience functions
async def whitelist_corporate_ip(
    ip_address: str,
    facility_id: UUID,
    reason: str = "Corporate network"
) -> UUID:
    """Add corporate IP to whitelist (convenience wrapper)."""
    async with IPWhitelistManager() as manager:
        return await manager.add_to_whitelist(ip_address, facility_id, reason)

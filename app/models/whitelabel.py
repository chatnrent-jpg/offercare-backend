"""
VettedMe White-Label Customization

Allows enterprise customers to customize the passport experience with their own branding.

Features:
- Custom colors (primary, secondary, accent)
- Custom logos (header, favicon)
- Custom domain (passports.yourcompany.com)
- Custom email templates
- Custom widget styling
- Custom success/error messages

Enterprise Tier: $5,000/month base + $0.25/verification
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class WhiteLabelConfig(Base):
    """
    White-label branding configuration for enterprise customers.
    
    Allows customization of:
    - Colors and styling
    - Logos and images
    - Domain and branding
    - Email templates
    - Widget appearance
    """
    __tablename__ = "whitelabel_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Branding
    company_name = Column(String(255), nullable=False, doc="Company name displayed in UI")
    custom_domain = Column(String(255), nullable=True, doc="Custom domain (e.g., verify.company.com)")
    
    # Colors (hex codes)
    primary_color = Column(String(7), default="#667eea", nullable=False, doc="Primary brand color")
    secondary_color = Column(String(7), default="#764ba2", nullable=False, doc="Secondary brand color")
    accent_color = Column(String(7), default="#10B981", nullable=False, doc="Accent color for success states")
    error_color = Column(String(7), default="#EF4444", nullable=False, doc="Error color")
    
    # Logos (URLs or base64)
    logo_url = Column(String(2048), nullable=True, doc="Main logo URL")
    logo_square_url = Column(String(2048), nullable=True, doc="Square logo for small spaces")
    favicon_url = Column(String(2048), nullable=True, doc="Favicon URL")
    
    # Custom text
    tagline = Column(String(255), nullable=True, doc="Company tagline")
    support_email = Column(String(255), nullable=True, doc="Support email for users")
    support_url = Column(String(2048), nullable=True, doc="Support URL")
    
    # Email customization
    email_from_name = Column(String(255), nullable=True, doc="'From' name in emails")
    email_from_address = Column(String(255), nullable=True, doc="'From' email address")
    email_templates = Column(JSONB, default={}, nullable=False, doc="Custom email templates")
    
    # Widget customization
    widget_style = Column(JSONB, default={}, nullable=False, doc="Custom CSS for embeddable widget")
    
    # Features
    show_vettedme_branding = Column(Boolean, default=True, nullable=False, doc="Show 'Powered by VettedMe'")
    custom_success_message = Column(Text, nullable=True, doc="Custom verification success message")
    custom_error_message = Column(Text, nullable=True, doc="Custom verification error message")
    
    # Status
    status = Column(String(20), nullable=False, default="ACTIVE", doc="ACTIVE, SUSPENDED, or DISABLED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<WhiteLabelConfig(id={self.id}, company={self.company_name})>"
    
    def get_widget_css(self) -> str:
        """
        Generate custom CSS for the embeddable widget.
        
        Returns:
            str: CSS string with custom colors
        """
        return f"""
        .vettedme-badge-container {{
            background: linear-gradient(135deg, {self.primary_color} 0%, {self.secondary_color} 100%);
        }}
        
        .vettedme-badge-container:hover {{
            box-shadow: 0 6px 12px {self.primary_color}40;
        }}
        
        .vettedme-section-action {{
            background: linear-gradient(135deg, {self.primary_color} 0%, {self.secondary_color} 100%);
        }}
        
        .vettedme-badge-item.verified {{
            border-color: {self.accent_color};
        }}
        """
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "company_name": self.company_name,
            "custom_domain": self.custom_domain,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "accent_color": self.accent_color,
            "error_color": self.error_color,
            "logo_url": self.logo_url,
            "logo_square_url": self.logo_square_url,
            "favicon_url": self.favicon_url,
            "tagline": self.tagline,
            "support_email": self.support_email,
            "support_url": self.support_url,
            "show_vettedme_branding": self.show_vettedme_branding,
            "status": self.status
        }

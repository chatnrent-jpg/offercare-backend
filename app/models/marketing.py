"""
Marketing Engine Database Models
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class HealthcareFacility(Base):
    """Healthcare facilities in Prince George's County, MD"""
    __tablename__ = "healthcare_facilities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    facility_type = Column(String)  # Hospital, Nursing Home, Assisted Living
    address = Column(String)
    city = Column(String, index=True)
    state = Column(String, default="MD")
    zip_code = Column(String, index=True)
    county = Column(String, default="Prince George's County", index=True)
    
    # Facility details
    beds = Column(Integer)
    phone = Column(String)
    website = Column(String)
    email = Column(String)
    
    # Data sources
    cms_id = Column(String, unique=True, index=True)  # CMS Provider ID
    md_license_number = Column(String, unique=True, index=True)
    google_place_id = Column(String, unique=True)
    
    # Social media
    linkedin_url = Column(String)
    facebook_url = Column(String)
    twitter_url = Column(String)
    
    # Metadata
    scraped_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_quality_score = Column(Float, default=0.0)  # 0-1
    
    # Relationships
    contacts = relationship("ContactLead", back_populates="facility")
    campaigns = relationship("EmailCampaign", secondary="campaign_facilities", back_populates="facilities")


class ContactLead(Base):
    """Individual contacts at healthcare facilities"""
    __tablename__ = "contact_leads"
    
    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("healthcare_facilities.id"), nullable=False, index=True)
    
    # Contact details
    first_name = Column(String)
    last_name = Column(String)
    full_name = Column(String, index=True)
    title = Column(String, index=True)  # DON, HR Director, etc.
    email = Column(String, index=True)
    phone = Column(String)
    
    # Social profiles
    linkedin_url = Column(String, unique=True, index=True)
    facebook_url = Column(String)
    
    # Email verification
    email_verified = Column(Boolean, default=False)
    email_verification_date = Column(DateTime)
    email_verification_service = Column(String)  # Hunter, ZeroBounce, etc.
    email_deliverable = Column(Boolean)
    
    # Data quality
    confidence_score = Column(Float, default=0.0, index=True)  # 0-1
    data_source = Column(String)  # Website, LinkedIn, Facebook, Manual
    scraped_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Engagement tracking
    contacted = Column(Boolean, default=False, index=True)
    first_contact_date = Column(DateTime)
    last_contact_date = Column(DateTime)
    contact_count = Column(Integer, default=0)
    responded = Column(Boolean, default=False, index=True)
    first_response_date = Column(DateTime)
    
    # CRM fields
    status = Column(String, default="new", index=True)  # new, contacted, interested, not_interested, converted
    notes = Column(Text)
    tags = Column(JSON)  # ["high_priority", "follow_up", etc.]
    
    # Relationships
    facility = relationship("HealthcareFacility", back_populates="contacts")
    campaign_sends = relationship("CampaignSend", back_populates="contact")


class EmailCampaign(Base):
    """Email marketing campaigns"""
    __tablename__ = "email_campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text)
    
    # Campaign settings
    from_name = Column(String, default="VettedMe Team")
    from_email = Column(String, default="hello@vettedme.ai")
    reply_to = Column(String)
    
    # Targeting
    target_titles = Column(JSON)  # ["DON", "HR Director", etc.]
    target_facility_types = Column(JSON)  # ["Nursing Home", "Hospital", etc.]
    min_confidence_score = Column(Float, default=0.5)
    
    # Status
    status = Column(String, default="draft", index=True)  # draft, scheduled, sending, sent, paused
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    
    # Metrics
    total_recipients = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)
    replied_count = Column(Integer, default=0)
    bounced_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    facilities = relationship("HealthcareFacility", secondary="campaign_facilities", back_populates="campaigns")
    sends = relationship("CampaignSend", back_populates="campaign")


class CampaignSend(Base):
    """Individual email sends (tracking)"""
    __tablename__ = "campaign_sends"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contact_leads.id"), nullable=False, index=True)
    
    # Send details
    sent_at = Column(DateTime, index=True)
    delivered_at = Column(DateTime)
    opened_at = Column(DateTime)
    first_click_at = Column(DateTime)
    replied_at = Column(DateTime)
    bounced_at = Column(DateTime)
    
    # Tracking
    opens_count = Column(Integer, default=0)
    clicks_count = Column(Integer, default=0)
    bounce_reason = Column(String)
    
    # Unique identifiers for tracking
    tracking_id = Column(String, unique=True, index=True)
    
    # Relationships
    campaign = relationship("EmailCampaign", back_populates="sends")
    contact = relationship("ContactLead", back_populates="campaign_sends")


# Association table for many-to-many relationship
from sqlalchemy import Table

campaign_facilities = Table(
    "campaign_facilities",
    Base.metadata,
    Column("campaign_id", Integer, ForeignKey("email_campaigns.id"), primary_key=True),
    Column("facility_id", Integer, ForeignKey("healthcare_facilities.id"), primary_key=True),
)


class ScraperJob(Base):
    """Track scraping jobs and their status"""
    __tablename__ = "scraper_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String, nullable=False, index=True)  # cms, google_maps, linkedin, facebook, website
    target = Column(String)  # URL or search query
    status = Column(String, default="pending", index=True)  # pending, running, completed, failed
    
    # Results
    facilities_found = Column(Integer, default=0)
    contacts_found = Column(Integer, default=0)
    emails_found = Column(Integer, default=0)
    
    # Execution
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

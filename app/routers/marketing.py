"""
Marketing Engine API Endpoints
Lead generation, email campaigns, contact management
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.marketing import (
    HealthcareFacility,
    ContactLead,
    EmailCampaign,
    CampaignSend,
    ScraperJob,
)
from app.services.marketing_engine import MarketingEngine, generate_email_campaign_targets

router = APIRouter(prefix="/api/v1/marketing", tags=["Marketing"])


# ==================== Pydantic Schemas ====================

class FacilityCreate(BaseModel):
    name: str
    facility_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    beds: Optional[int] = None


class FacilityResponse(BaseModel):
    id: int
    name: str
    facility_type: Optional[str]
    address: Optional[str]
    city: Optional[str]
    zip_code: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    contact_count: int
    data_quality_score: float
    
    class Config:
        from_attributes = True


class ContactCreate(BaseModel):
    facility_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    title: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    data_source: str = "manual"


class ContactResponse(BaseModel):
    id: int
    facility_id: int
    full_name: str
    title: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    confidence_score: float
    email_verified: bool
    contacted: bool
    status: str
    
    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    body_text: Optional[str] = None
    target_titles: Optional[List[str]] = None
    target_facility_types: Optional[List[str]] = None
    min_confidence_score: float = 0.7


class CampaignResponse(BaseModel):
    id: int
    name: str
    subject: str
    status: str
    total_recipients: int
    sent_count: int
    opened_count: int
    clicked_count: int
    replied_count: int
    
    class Config:
        from_attributes = True


# ==================== Facility Endpoints ====================

@router.get("/facilities", response_model=List[FacilityResponse])
def list_facilities(
    skip: int = 0,
    limit: int = 100,
    city: Optional[str] = None,
    facility_type: Optional[str] = None,
    min_beds: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """List all healthcare facilities in Prince George's County"""
    query = db.query(
        HealthcareFacility,
        func.count(ContactLead.id).label("contact_count")
    ).outerjoin(ContactLead).group_by(HealthcareFacility.id)
    
    if city:
        query = query.filter(HealthcareFacility.city == city)
    if facility_type:
        query = query.filter(HealthcareFacility.facility_type == facility_type)
    if min_beds:
        query = query.filter(HealthcareFacility.beds >= min_beds)
    
    facilities = query.offset(skip).limit(limit).all()
    
    return [
        FacilityResponse(
            **facility.__dict__,
            contact_count=count
        )
        for facility, count in facilities
    ]


@router.post("/facilities", response_model=FacilityResponse)
def create_facility(facility: FacilityCreate, db: Session = Depends(get_db)):
    """Add a new healthcare facility"""
    db_facility = HealthcareFacility(**facility.dict())
    db.add(db_facility)
    db.commit()
    db.refresh(db_facility)
    
    return FacilityResponse(**db_facility.__dict__, contact_count=0)


@router.get("/facilities/{facility_id}", response_model=FacilityResponse)
def get_facility(facility_id: int, db: Session = Depends(get_db)):
    """Get facility details with contact count"""
    facility = db.query(HealthcareFacility).filter(HealthcareFacility.id == facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    
    contact_count = db.query(func.count(ContactLead.id)).filter(ContactLead.facility_id == facility_id).scalar()
    
    return FacilityResponse(**facility.__dict__, contact_count=contact_count)


# ==================== Contact Endpoints ====================

@router.get("/contacts", response_model=List[ContactResponse])
def list_contacts(
    skip: int = 0,
    limit: int = 100,
    title: Optional[str] = None,
    has_email: Optional[bool] = None,
    email_verified: Optional[bool] = None,
    min_confidence: Optional[float] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all contacts with filtering"""
    query = db.query(ContactLead)
    
    if title:
        query = query.filter(ContactLead.title.ilike(f"%{title}%"))
    if has_email is not None:
        if has_email:
            query = query.filter(ContactLead.email.isnot(None))
        else:
            query = query.filter(ContactLead.email.is_(None))
    if email_verified is not None:
        query = query.filter(ContactLead.email_verified == email_verified)
    if min_confidence:
        query = query.filter(ContactLead.confidence_score >= min_confidence)
    if status:
        query = query.filter(ContactLead.status == status)
    
    contacts = query.offset(skip).limit(limit).all()
    return contacts


@router.post("/contacts", response_model=ContactResponse)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    """Add a new contact"""
    # Verify facility exists
    facility = db.query(HealthcareFacility).filter(HealthcareFacility.id == contact.facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    
    db_contact = ContactLead(**contact.dict())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    
    return db_contact


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    """Get contact details"""
    contact = db.query(ContactLead).filter(ContactLead.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.put("/contacts/{contact_id}/status")
def update_contact_status(
    contact_id: int,
    status: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Update contact status (new, contacted, interested, not_interested, converted)"""
    contact = db.query(ContactLead).filter(ContactLead.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact.status = status
    if notes:
        contact.notes = notes
    contact.last_updated = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Status updated", "contact_id": contact_id, "new_status": status}


# ==================== Scraping Endpoints ====================

@router.post("/scrape/pg-county")
def scrape_pg_county_facilities(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Scrape all healthcare facilities in Prince George's County
    Sources: Maryland Health Dept, CMS, Google Maps
    """
    job = ScraperJob(
        job_type="pg_county_full",
        target="Prince George's County, MD",
        status="pending",
    )
    db.add(job)
    db.commit()
    
    # Run scraping in background
    def run_scraping():
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        try:
            engine = MarketingEngine(db)
            leads = engine.build_pg_county_lead_list()
            
            # Save to database
            # (Implementation would insert facilities and contacts)
            
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.facilities_found = len(leads)
            db.commit()
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    
    background_tasks.add_task(run_scraping)
    
    return {
        "message": "Scraping started",
        "job_id": job.id,
        "status": "running",
        "check_status_url": f"/api/v1/marketing/scrape/jobs/{job.id}"
    }


@router.get("/scrape/jobs/{job_id}")
def get_scraper_job_status(job_id: int, db: Session = Depends(get_db)):
    """Check status of a scraping job"""
    job = db.query(ScraperJob).filter(ScraperJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "facilities_found": job.facilities_found,
        "contacts_found": job.contacts_found,
        "emails_found": job.emails_found,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
    }


# ==================== Campaign Endpoints ====================

@router.get("/campaigns", response_model=List[CampaignResponse])
def list_campaigns(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all email campaigns"""
    query = db.query(EmailCampaign)
    
    if status:
        query = query.filter(EmailCampaign.status == status)
    
    campaigns = query.order_by(EmailCampaign.created_at.desc()).offset(skip).limit(limit).all()
    return campaigns


@router.post("/campaigns", response_model=CampaignResponse)
def create_campaign(campaign: CampaignCreate, db: Session = Depends(get_db)):
    """Create a new email campaign"""
    db_campaign = EmailCampaign(**campaign.dict())
    
    # Count potential recipients
    query = db.query(ContactLead).filter(
        ContactLead.email.isnot(None),
        ContactLead.confidence_score >= campaign.min_confidence_score,
    )
    
    if campaign.target_titles:
        query = query.filter(ContactLead.title.in_(campaign.target_titles))
    
    db_campaign.total_recipients = query.count()
    
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    
    return db_campaign


@router.post("/campaigns/{campaign_id}/send")
def send_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send an email campaign"""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="Campaign already sent or in progress")
    
    campaign.status = "sending"
    campaign.sent_at = datetime.utcnow()
    db.commit()
    
    # Send emails in background
    # (Would integrate with SendGrid, AWS SES, etc.)
    
    return {
        "message": "Campaign sending started",
        "campaign_id": campaign_id,
        "total_recipients": campaign.total_recipients,
    }


@router.get("/campaigns/{campaign_id}/stats")
def get_campaign_stats(campaign_id: int, db: Session = Depends(get_db)):
    """Get detailed campaign statistics"""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "campaign_id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "total_recipients": campaign.total_recipients,
        "sent_count": campaign.sent_count,
        "delivered_count": campaign.delivered_count,
        "opened_count": campaign.opened_count,
        "clicked_count": campaign.clicked_count,
        "replied_count": campaign.replied_count,
        "bounced_count": campaign.bounced_count,
        "open_rate": round((campaign.opened_count / campaign.sent_count * 100), 2) if campaign.sent_count > 0 else 0,
        "click_rate": round((campaign.clicked_count / campaign.sent_count * 100), 2) if campaign.sent_count > 0 else 0,
        "response_rate": round((campaign.replied_count / campaign.sent_count * 100), 2) if campaign.sent_count > 0 else 0,
    }


# ==================== Analytics Endpoints ====================

@router.get("/analytics/overview")
def get_marketing_analytics(db: Session = Depends(get_db)):
    """Get overall marketing analytics dashboard"""
    total_facilities = db.query(func.count(HealthcareFacility.id)).scalar()
    total_contacts = db.query(func.count(ContactLead.id)).scalar()
    contacts_with_email = db.query(func.count(ContactLead.id)).filter(ContactLead.email.isnot(None)).scalar()
    verified_emails = db.query(func.count(ContactLead.id)).filter(ContactLead.email_verified == True).scalar()
    
    # Contacts by title
    don_count = db.query(func.count(ContactLead.id)).filter(
        ContactLead.title.ilike("%Director of Nursing%")
    ).scalar()
    hr_count = db.query(func.count(ContactLead.id)).filter(
        ContactLead.title.ilike("%HR Director%")
    ).scalar()
    admin_count = db.query(func.count(ContactLead.id)).filter(
        ContactLead.title.ilike("%Administrator%")
    ).scalar()
    
    # Contact status breakdown
    contacted_count = db.query(func.count(ContactLead.id)).filter(ContactLead.contacted == True).scalar()
    interested_count = db.query(func.count(ContactLead.id)).filter(ContactLead.status == "interested").scalar()
    converted_count = db.query(func.count(ContactLead.id)).filter(ContactLead.status == "converted").scalar()
    
    return {
        "facilities": {
            "total": total_facilities,
            "pg_county": total_facilities,  # All are in PG County
        },
        "contacts": {
            "total": total_contacts,
            "with_email": contacts_with_email,
            "verified_emails": verified_emails,
            "by_title": {
                "directors_of_nursing": don_count,
                "hr_directors": hr_count,
                "administrators": admin_count,
            },
            "by_status": {
                "new": total_contacts - contacted_count,
                "contacted": contacted_count,
                "interested": interested_count,
                "converted": converted_count,
            },
        },
        "campaigns": {
            "total": db.query(func.count(EmailCampaign.id)).scalar(),
            "sent": db.query(func.count(EmailCampaign.id)).filter(EmailCampaign.status == "sent").scalar(),
        },
    }

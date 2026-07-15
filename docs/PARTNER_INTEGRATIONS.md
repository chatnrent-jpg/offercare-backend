# VettedMe Partner Integration Templates

**Version**: 1.0.0  
**Last Updated**: 2026-07-14

Pre-built integration guides and code templates for major platforms.

---

## 🎯 Upwork Integration

### Overview
Allow Upwork freelancers to display verified VettedMe badges on their profiles.

### Implementation

**Step 1: User connects VettedMe to Upwork**
```javascript
// Upwork OAuth flow
const vettedmeAuth = {
  client_id: "your_upwork_app_id",
  redirect_uri: "https://vettedme.ai/integrations/upwork/callback",
  scope: "profile:write"
};

// Redirect user to Upwork authorization
window.location.href = `https://www.upwork.com/ab/account-security/oauth2/authorize?` +
  `response_type=code&client_id=${vettedmeAuth.client_id}&` +
  `redirect_uri=${vettedmeAuth.redirect_uri}&scope=${vettedmeAuth.scope}`;
```

**Step 2: VettedMe stores Upwork access token**
```python
# Backend callback handler
@app.post("/integrations/upwork/callback")
async def upwork_callback(code: str, db: Session = Depends(get_db)):
    # Exchange code for access token
    token_response = httpx.post("https://www.upwork.com/api/v3/oauth2/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.UPWORK_CLIENT_ID,
        "client_secret": settings.UPWORK_CLIENT_SECRET,
        "redirect_uri": "https://vettedme.ai/integrations/upwork/callback"
    })
    
    access_token = token_response.json()["access_token"]
    
    # Store in database
    integration = PartnerIntegration(
        platform="UPWORK",
        access_token=encrypt(access_token),
        status="ACTIVE"
    )
    db.add(integration)
    db.commit()
    
    return {"success": True, "message": "Upwork connected successfully"}
```

**Step 3: Auto-sync badges to Upwork profile**
```python
def sync_badges_to_upwork(passport_id: UUID, db: Session):
    # Get active badges
    passport = db.query(Passport).filter_by(id=passport_id).first()
    badges = passport.get_active_badges()
    
    # Get Upwork integration
    integration = db.query(PartnerIntegration).filter_by(
        passport_id=passport_id,
        platform="UPWORK",
        status="ACTIVE"
    ).first()
    
    if not integration:
        return
    
    access_token = decrypt(integration.access_token)
    
    # Build badge HTML
    badge_html = f'''
    <div id="vettedme-badge" 
         data-passport-id="{passport_id}" 
         data-badges="{','.join([b.badge_type for b in badges])}">
    </div>
    <script src="https://api.vettedme.ai/widgets/badge.js"></script>
    '''
    
    # Update Upwork profile via API
    httpx.put(
        "https://www.upwork.com/api/profiles/v2/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"overview": profile_text + "\\n\\n" + badge_html}
    )
```

**Webhook Handler**:
```python
@app.post("/integrations/upwork/webhook")
async def upwork_webhook(event: dict):
    # Handle Upwork events
    if event["type"] == "profile.updated":
        # Re-sync badges if profile was modified
        sync_badges_to_upwork(event["user_id"])
```

---

## 💼 LinkedIn Integration

### Overview
Display VettedMe badges in LinkedIn "About" or "Licenses & Certifications" sections.

### Implementation

**LinkedIn doesn't support OAuth writes, so we provide:**

1. **Copy-Paste Template**:
```python
def generate_linkedin_template(passport_id: UUID, badges: list):
    return f"""
VERIFIED CREDENTIALS ✅

I've verified my professional credentials through VettedMe:

{chr(10).join([f"• {BADGE_CONFIG[b.badge_type]['label']}" for b in badges])}

View my verified passport: https://verify.vettedme.ai/{passport_id}

[VettedMe Badge Widget - paste HTML below in raw mode]
<div id="vettedme-badge" data-passport-id="{passport_id}" data-badges="{','.join([b.badge_type for b in badges])}"></div>
<script src="https://api.vettedme.ai/widgets/badge.js"></script>
"""
```

2. **Chrome Extension** (auto-inject):
```javascript
// LinkedIn extension that auto-adds badges
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "inject_vettedme_badge") {
    const aboutSection = document.querySelector('.pv-about-section');
    
    // Create badge container
    const badgeDiv = document.createElement('div');
    badgeDiv.innerHTML = `
      <div id="vettedme-badge" 
           data-passport-id="${request.passportId}" 
           data-badges="${request.badges}">
      </div>
    `;
    
    // Inject at top of About section
    aboutSection.prepend(badgeDiv);
    
    // Load widget script
    const script = document.createElement('script');
    script.src = 'https://api.vettedme.ai/widgets/badge.js';
    document.body.appendChild(script);
  }
});
```

3. **QR Code Generator**:
```python
import qrcode

def generate_linkedin_qr(passport_id: UUID):
    # Generate QR code linking to verification page
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"https://verify.vettedme.ai/{passport_id}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_path = f"/tmp/qr_{passport_id}.png"
    img.save(img_path)
    
    return img_path
```

Users can then upload QR code to LinkedIn profile banner or post.

---

## 🔍 Indeed Integration

### Overview
Verify credentials for Indeed job applications.

### Implementation

**Indeed Apply API Integration**:
```python
@app.post("/integrations/indeed/apply")
async def indeed_apply_with_verification(
    job_id: str,
    passport_id: UUID,
    db: Session = Depends(get_db)
):
    # Get passport and badges
    passport = db.query(Passport).filter_by(id=passport_id).first()
    badges = passport.get_active_badges()
    
    # Build Indeed application payload
    application = {
        "job_id": job_id,
        "candidate": {
            "name": get_user_name(passport.user_id),
            "email": get_user_email(passport.user_id),
            "verified_credentials": [
                {
                    "type": badge.badge_type,
                    "verified": True,
                    "verification_provider": "VettedMe",
                    "verification_url": f"https://verify.vettedme.ai/{passport_id}"
                }
                for badge in badges
            ]
        }
    }
    
    # Submit to Indeed API
    response = httpx.post(
        "https://secure.indeed.com/v2/api/applications",
        headers={
            "Authorization": f"Bearer {INDEED_API_KEY}",
            "Content-Type": "application/json"
        },
        json=application
    )
    
    return {
        "success": response.status_code == 200,
        "application_id": response.json().get("application_id"),
        "verified_badges": len(badges)
    }
```

**Indeed Employer Integration**:
```python
# Webhook for employers to verify candidates
@app.post("/integrations/indeed/verify-candidate")
async def verify_indeed_candidate(
    application_id: str,
    passport_id: UUID,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    # Verify passport and return credential status
    engine = PassportVerificationEngine(db)
    result = engine.verify_passport(
        passport_id=passport_id,
        required_badges=["IDENTITY", "EMPLOYMENT", "COMPLIANCE"],
        api_key_id=api_key.id,
        requesting_platform="indeed.com"
    )
    
    return {
        "application_id": application_id,
        "verification_result": result,
        "recommendation": "HIRE" if result["verified"] and result["trust_score"] >= 80 else "REVIEW"
    }
```

---

## 🚀 General Integration Pattern

### For Any Platform

**1. OAuth Connection Flow**:
```python
class PartnerIntegration(Base):
    __tablename__ = "partner_integrations"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    passport_id = Column(UUID, ForeignKey("passports.id"), nullable=False)
    platform = Column(String(50), nullable=False)  # "UPWORK", "LINKEDIN", "INDEED"
    access_token = Column(Text, nullable=True)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted
    status = Column(String(20), default="ACTIVE")
    sync_enabled = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

**2. Auto-Sync Service**:
```python
async def auto_sync_credentials():
    """Background task to sync credentials to partner platforms."""
    db = SessionLocal()
    
    integrations = db.query(PartnerIntegration).filter_by(
        status="ACTIVE",
        sync_enabled=True
    ).all()
    
    for integration in integrations:
        try:
            if integration.platform == "UPWORK":
                sync_badges_to_upwork(integration.passport_id, db)
            elif integration.platform == "INDEED":
                sync_badges_to_indeed(integration.passport_id, db)
            
            integration.last_sync_at = datetime.now(timezone.utc)
            db.commit()
            
        except Exception as e:
            logger.error(f"Sync failed for {integration.id}: {e}")
```

**3. Webhook Subscriptions**:
```python
# Subscribe to VettedMe webhooks for credential changes
webhook_subscription = {
    "url": "https://yourplatform.com/vettedme/webhook",
    "events": ["credential.issued", "credential.revoked"],
    "description": "Sync credential changes to user profiles"
}

# When webhook is received:
@app.post("/vettedme/webhook")
async def vettedme_webhook(payload: dict):
    # Verify HMAC signature
    if not verify_webhook_signature(payload, request.headers["X-VettedMe-Signature"]):
        raise HTTPException(status_code=401)
    
    if payload["event_type"] == "credential.issued":
        # Update user profile with new badge
        update_user_profile(payload["passport_id"], payload["data"])
    
    elif payload["event_type"] == "credential.revoked":
        # Remove badge from profile
        remove_user_badge(payload["passport_id"], payload["data"]["badge_id"])
```

---

## 📚 Partner API Documentation

### For Partners Integrating VettedMe

**Quick Start**:
```bash
# 1. Get API key
curl -X POST https://api.vettedme.ai/v1/passport/api-keys \
  -H "Content-Type: application/json" \
  -d '{"organization_name": "Your Platform", "tier": "GROWTH"}'

# 2. Verify a user's credentials
curl -X POST https://api.vettedme.ai/v1/passport/verify \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "passport_id": "uuid-12345",
    "required_badges": ["IDENTITY", "HEALTHCARE"],
    "requesting_platform": "yourplatform.com"
  }'
```

**Response**:
```json
{
  "verified": true,
  "passport_id": "uuid-12345",
  "trust_score": 98,
  "badges": [
    {"type": "IDENTITY", "verified": true, "expires_at": "2028-07-14T00:00:00Z"},
    {"type": "HEALTHCARE", "verified": true, "expires_at": "2027-10-31T00:00:00Z"}
  ],
  "verification_token": "vtok_1721073600_uuid1234_abc"
}
```

---

## 🎯 Coming Soon

- **Fiverr Integration**: Verify freelancer credentials
- **Thumbtack Integration**: Service professional verification
- **Care.com Integration**: Caregiver background checks
- **TaskRabbit Integration**: Skilled labor verification
- **Uber/Lyft**: Driver credential verification

---

**Questions?** Contact partners@vettedme.ai

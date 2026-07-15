## 🎯 VettedMe Marketing Engine
# Lead Generation & Email Outreach for Prince George's County Healthcare Facilities

## Overview

The Marketing Engine is a comprehensive system for:
1. **Scraping** healthcare facility data from multiple sources
2. **Enriching** contacts with emails, titles, and social profiles
3. **Managing** leads and tracking engagement
4. **Campaigning** via targeted email outreach

**Target Market**: Healthcare facilities in Prince George's County, Maryland
**Target Contacts**: Directors of Nursing (DON), HR Directors, Administrators, CEOs
**Pricing**: $0.07 per verification
**Launch Date**: End of September 2026

---

## Data Sources

### 1. Maryland Department of Health
- **URL**: https://health.maryland.gov/
- **Data**: Licensed healthcare facilities in Maryland
- **Fields**: Facility name, address, license number, type, bed count

### 2. CMS Nursing Home Compare
- **API**: https://data.cms.gov/provider-data/
- **Dataset**: Nursing Home Provider Info (mj5m-pzi6)
- **Filter**: Prince George's County, MD
- **Fields**: Provider ID, name, address, phone, ownership, quality ratings

### 3. Google Maps API
- **Searches**:
  - "Nursing homes in Prince George's County MD"
  - "Hospitals in Prince George's County MD"
  - "Assisted living facilities in Prince George's County MD"
- **Fields**: Name, address, phone, website, Google ratings

### 4. Facility Websites
- **Scrape**: Leadership pages, contact pages, staff directories
- **Extract**: Names, titles, emails, phone numbers

### 5. LinkedIn
- **Search**: "Director of Nursing" + [facility name] + "Prince George's County MD"
- **Extract**: Name, title, profile URL, email (if public)

### 6. Facebook
- **Search**: Facility pages
- **Extract**: Contact info, posts, reviews

---

## Database Schema

### `healthcare_facilities`
```sql
- id (PK)
- name
- facility_type (Hospital, Nursing Home, Assisted Living)
- address, city, state, zip_code, county
- beds
- phone, website, email
- cms_id, md_license_number, google_place_id
- linkedin_url, facebook_url, twitter_url
- scraped_at, last_updated
- data_quality_score (0-1)
```

### `contact_leads`
```sql
- id (PK)
- facility_id (FK)
- first_name, last_name, full_name
- title (DON, HR Director, etc.)
- email, phone
- linkedin_url, facebook_url
- email_verified, email_verification_date
- confidence_score (0-1)
- data_source
- contacted, first_contact_date, last_contact_date
- responded, first_response_date
- status (new, contacted, interested, not_interested, converted)
- notes, tags
```

### `email_campaigns`
```sql
- id (PK)
- name, subject
- body_html, body_text
- from_name, from_email, reply_to
- target_titles, target_facility_types
- min_confidence_score
- status (draft, scheduled, sending, sent, paused)
- total_recipients, sent_count, delivered_count
- opened_count, clicked_count, replied_count, bounced_count
```

### `campaign_sends`
```sql
- id (PK)
- campaign_id (FK), contact_id (FK)
- sent_at, delivered_at, opened_at, first_click_at, replied_at, bounced_at
- opens_count, clicks_count
- tracking_id (unique)
```

---

## API Endpoints

### Facilities
- `GET /api/v1/marketing/facilities` - List all facilities
- `POST /api/v1/marketing/facilities` - Add a facility
- `GET /api/v1/marketing/facilities/{id}` - Get facility details

### Contacts
- `GET /api/v1/marketing/contacts` - List contacts (with filters)
- `POST /api/v1/marketing/contacts` - Add a contact
- `GET /api/v1/marketing/contacts/{id}` - Get contact details
- `PUT /api/v1/marketing/contacts/{id}/status` - Update status

### Scraping
- `POST /api/v1/marketing/scrape/pg-county` - Scrape all PG County facilities
- `GET /api/v1/marketing/scrape/jobs/{id}` - Check scraping job status

### Campaigns
- `GET /api/v1/marketing/campaigns` - List campaigns
- `POST /api/v1/marketing/campaigns` - Create campaign
- `POST /api/v1/marketing/campaigns/{id}/send` - Send campaign
- `GET /api/v1/marketing/campaigns/{id}/stats` - Get campaign stats

### Analytics
- `GET /api/v1/marketing/analytics/overview` - Marketing dashboard

---

## Setup Instructions

### 1. Install Dependencies
```bash
pip install beautifulsoup4 requests selenium playwright
pip install hunter  # Hunter.io Python library
pip install zerobounce  # ZeroBounce Python library
```

### 2. API Keys Required
Create a `.env` file with:
```
# Email Finding/Verification
HUNTER_API_KEY=your_hunter_io_key
ZEROBOUNCE_API_KEY=your_zerobounce_key

# Google Maps (for facility scraping)
GOOGLE_MAPS_API_KEY=your_google_maps_key

# LinkedIn (for profile scraping)
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password

# Facebook (for page scraping)
FACEBOOK_ACCESS_TOKEN=your_fb_token

# Email Sending
SENDGRID_API_KEY=your_sendgrid_key
# OR
AWS_SES_ACCESS_KEY=your_aws_key
AWS_SES_SECRET_KEY=your_aws_secret
```

### 3. Run Database Migration
```bash
alembic upgrade head
```

### 4. Start Scraping
```bash
curl -X POST http://localhost:8000/api/v1/marketing/scrape/pg-county
```

---

## Implementation Checklist

### Phase 1: Data Collection (Week 1-2)
- [ ] Scrape Maryland Health Department for licensed facilities
- [ ] Scrape CMS database for nursing homes
- [ ] Scrape Google Maps for all healthcare facilities
- [ ] Build facility deduplication logic
- [ ] Store ~200-500 facilities in database

### Phase 2: Contact Enrichment (Week 3-4)
- [ ] Scrape facility websites for leadership teams
- [ ] Search LinkedIn for DONs and HR Directors
- [ ] Search Facebook for facility pages
- [ ] Use Hunter.io to find email addresses
- [ ] Verify emails with ZeroBounce
- [ ] Calculate confidence scores
- [ ] Target: 500-1000 contacts with emails

### Phase 3: CRM & Tracking (Week 5)
- [ ] Build contact management UI
- [ ] Add status tracking (new, contacted, interested, etc.)
- [ ] Add notes and tagging system
- [ ] Build lead scoring algorithm
- [ ] Priority ranking system

### Phase 4: Email Campaigns (Week 6-7)
- [ ] Integrate SendGrid or AWS SES
- [ ] Build email template system
- [ ] Add tracking pixels for opens
- [ ] Add UTM parameters for clicks
- [ ] Build campaign analytics dashboard
- [ ] A/B testing system

### Phase 5: Automation (Week 8)
- [ ] Automated follow-up sequences
- [ ] Lead scoring automation
- [ ] Response detection
- [ ] Integration with CRM
- [ ] Slack notifications for hot leads

---

## Email Campaign Strategy

### Campaign 1: Initial Outreach (DONs)
**Subject**: "Solve Your Staffing Crisis in 24 Hours"

**Body**:
```
Hi [First Name],

I noticed [Facility Name] on the Maryland Health Department's registry.

Are you tired of:
❌ Last-minute call-outs
❌ Paying $150+/hour for agency nurses
❌ Spending hours on credentialing

VettedMe connects you with pre-credentialed RNs, LPNs, and CNAs instantly:
✅ Verified credentials (instant check, not 2-week wait)
✅ $0.07 per verification (100x cheaper than traditional)
✅ Available 24/7 for same-day shifts

Book a 15-min demo: [Calendar Link]

Best,
[Your Name]
VettedMe Team
```

### Campaign 2: HR Directors
**Subject**: "Cut Your Credentialing Time from 2 Weeks to 2 Minutes"

**Focus**: Speed + cost savings

### Campaign 3: Administrators/CEOs
**Subject**: "Healthcare Staffing Platform - $0.07 per Verification"

**Focus**: ROI + compliance

---

## Compliance & Legal

### CAN-SPAM Act Requirements
✅ Accurate "From" name and email
✅ Clear subject line (not deceptive)
✅ Include physical postal address
✅ Unsubscribe link in every email
✅ Honor unsubscribe requests within 10 days

### GDPR (if applicable)
✅ Data processing agreement
✅ Opt-in consent for EU residents
✅ Right to erasure (delete data on request)

### Best Practices
- Don't send to personal emails (@gmail, @yahoo)
- Focus on work emails (@facility.com)
- Warm up email domain (start slow, ramp up)
- Max 200-300 emails/day initially
- Monitor bounce rates (keep < 5%)
- Monitor spam complaints (keep < 0.1%)

---

## Success Metrics

### Lead Generation KPIs
- **Facilities scraped**: Target 200-500 in PG County
- **Contacts found**: Target 500-1000 decision-makers
- **Email match rate**: Target 60-80%
- **Email verification rate**: Target 90%+
- **Confidence score**: Target average 0.7+

### Campaign KPIs
- **Open rate**: Target 25-35% (industry avg: 20%)
- **Click rate**: Target 3-5% (industry avg: 2%)
- **Reply rate**: Target 1-2%
- **Meeting booking rate**: Target 0.5-1%
- **Conversion rate**: Target 10-20% of meetings → paying customers

### Revenue Metrics
- **Cost per lead**: Target $2-5
- **Cost per meeting**: Target $100-200
- **Cost per acquisition**: Target $500-1000
- **Customer lifetime value**: Target $5000-10000
- **ROI**: Target 5-10x

---

## Next Steps

1. **Fix server startup issue** (Priority 1)
2. **Run migration**: `alembic upgrade head`
3. **Register marketing router** in `app/main.py`
4. **Start scraping**: Run PG County scraper
5. **Enrich contacts**: Find emails for all DONs
6. **Launch Campaign 1**: Email 100 DONs
7. **Track results**: Monitor opens, clicks, replies
8. **Iterate**: Improve messaging based on data

---

## Integration with Passport System

Once a facility signs up:
1. **Issue facility passport** (organization credential)
2. **Issue staff passports** (individual credentials)
3. **Verify instantly** when they apply for shifts
4. **Track usage**: Bill $0.07 per verification
5. **Upsell**: Healthcare staffing marketplace

**Revenue Model**:
- Lead generation → Passport sales → Verification fees → Marketplace commission

---

## Tools & Services to Sign Up For

### Required
1. **Hunter.io** - Email finding ($49/month for 1000 searches)
2. **ZeroBounce** - Email verification ($16 for 2000 verifications)
3. **SendGrid** or **AWS SES** - Email sending (free tier available)

### Optional (for advanced scraping)
4. **Bright Data** - Proxy network for web scraping ($500/month)
5. **Phantombuster** - LinkedIn/Facebook automation ($59/month)
6. **Apify** - Web scraping platform ($49/month)

### Free Alternatives
- **Selenium** + **BeautifulSoup** (manual scraping)
- **Google Custom Search API** (100 free queries/day)
- **LinkedIn Sales Navigator** (manual search)

---

## Expected Timeline

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Scrape facilities | 200-500 facilities in DB |
| 2 | Find contacts | 500-1000 contacts with titles |
| 3 | Enrich emails | 300-500 verified emails |
| 4 | Build CRM | Contact management UI |
| 5-6 | Email campaigns | 3 campaigns sent |
| 7 | Track & iterate | Meetings booked |
| 8 | Automate | Follow-up sequences live |

**Goal**: 10-20 facility sign-ups by end of September
**Revenue**: $500-2000/month in verification fees (assuming 1000-3000 verifications/month at $0.07 each)

---

## Questions?

Contact: [Your Email]

"""Marketing Engine tables

Revision ID: 013_marketing_engine
Revises: 012_sms_opt_out
Create Date: 2026-07-14 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_marketing_engine'
down_revision = '012_sms_opt_out'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Healthcare Facilities table
    op.create_table(
        'healthcare_facilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('facility_type', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=True),
        sa.Column('zip_code', sa.String(), nullable=True),
        sa.Column('county', sa.String(), nullable=True),
        sa.Column('beds', sa.Integer(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('website', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('cms_id', sa.String(), nullable=True),
        sa.Column('md_license_number', sa.String(), nullable=True),
        sa.Column('google_place_id', sa.String(), nullable=True),
        sa.Column('linkedin_url', sa.String(), nullable=True),
        sa.Column('facebook_url', sa.String(), nullable=True),
        sa.Column('twitter_url', sa.String(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('data_quality_score', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_healthcare_facilities_name', 'healthcare_facilities', ['name'])
    op.create_index('ix_healthcare_facilities_city', 'healthcare_facilities', ['city'])
    op.create_index('ix_healthcare_facilities_zip_code', 'healthcare_facilities', ['zip_code'])
    op.create_index('ix_healthcare_facilities_county', 'healthcare_facilities', ['county'])
    op.create_index('ix_healthcare_facilities_cms_id', 'healthcare_facilities', ['cms_id'], unique=True)
    op.create_index('ix_healthcare_facilities_md_license', 'healthcare_facilities', ['md_license_number'], unique=True)
    op.create_index('ix_healthcare_facilities_google_place', 'healthcare_facilities', ['google_place_id'], unique=True)

    # Contact Leads table
    op.create_table(
        'contact_leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('linkedin_url', sa.String(), nullable=True),
        sa.Column('facebook_url', sa.String(), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=True),
        sa.Column('email_verification_date', sa.DateTime(), nullable=True),
        sa.Column('email_verification_service', sa.String(), nullable=True),
        sa.Column('email_deliverable', sa.Boolean(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('data_source', sa.String(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('contacted', sa.Boolean(), nullable=True),
        sa.Column('first_contact_date', sa.DateTime(), nullable=True),
        sa.Column('last_contact_date', sa.DateTime(), nullable=True),
        sa.Column('contact_count', sa.Integer(), nullable=True),
        sa.Column('responded', sa.Boolean(), nullable=True),
        sa.Column('first_response_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['healthcare_facilities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contact_leads_facility_id', 'contact_leads', ['facility_id'])
    op.create_index('ix_contact_leads_full_name', 'contact_leads', ['full_name'])
    op.create_index('ix_contact_leads_title', 'contact_leads', ['title'])
    op.create_index('ix_contact_leads_email', 'contact_leads', ['email'])
    op.create_index('ix_contact_leads_linkedin', 'contact_leads', ['linkedin_url'], unique=True)
    op.create_index('ix_contact_leads_confidence', 'contact_leads', ['confidence_score'])
    op.create_index('ix_contact_leads_contacted', 'contact_leads', ['contacted'])
    op.create_index('ix_contact_leads_responded', 'contact_leads', ['responded'])
    op.create_index('ix_contact_leads_status', 'contact_leads', ['status'])

    # Email Campaigns table
    op.create_table(
        'email_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('from_name', sa.String(), nullable=True),
        sa.Column('from_email', sa.String(), nullable=True),
        sa.Column('reply_to', sa.String(), nullable=True),
        sa.Column('target_titles', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('target_facility_types', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('min_confidence_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('total_recipients', sa.Integer(), nullable=True),
        sa.Column('sent_count', sa.Integer(), nullable=True),
        sa.Column('delivered_count', sa.Integer(), nullable=True),
        sa.Column('opened_count', sa.Integer(), nullable=True),
        sa.Column('clicked_count', sa.Integer(), nullable=True),
        sa.Column('replied_count', sa.Integer(), nullable=True),
        sa.Column('bounced_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_campaigns_status', 'email_campaigns', ['status'])

    # Campaign Sends table
    op.create_table(
        'campaign_sends',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('first_click_at', sa.DateTime(), nullable=True),
        sa.Column('replied_at', sa.DateTime(), nullable=True),
        sa.Column('bounced_at', sa.DateTime(), nullable=True),
        sa.Column('opens_count', sa.Integer(), nullable=True),
        sa.Column('clicks_count', sa.Integer(), nullable=True),
        sa.Column('bounce_reason', sa.String(), nullable=True),
        sa.Column('tracking_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['email_campaigns.id'], ),
        sa.ForeignKeyConstraint(['contact_id'], ['contact_leads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_campaign_sends_campaign_id', 'campaign_sends', ['campaign_id'])
    op.create_index('ix_campaign_sends_contact_id', 'campaign_sends', ['contact_id'])
    op.create_index('ix_campaign_sends_sent_at', 'campaign_sends', ['sent_at'])
    op.create_index('ix_campaign_sends_tracking_id', 'campaign_sends', ['tracking_id'], unique=True)

    # Campaign Facilities association table
    op.create_table(
        'campaign_facilities',
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['email_campaigns.id'], ),
        sa.ForeignKeyConstraint(['facility_id'], ['healthcare_facilities.id'], ),
        sa.PrimaryKeyConstraint('campaign_id', 'facility_id')
    )

    # Scraper Jobs table
    op.create_table(
        'scraper_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_type', sa.String(), nullable=False),
        sa.Column('target', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('facilities_found', sa.Integer(), nullable=True),
        sa.Column('contacts_found', sa.Integer(), nullable=True),
        sa.Column('emails_found', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scraper_jobs_job_type', 'scraper_jobs', ['job_type'])
    op.create_index('ix_scraper_jobs_status', 'scraper_jobs', ['status'])


def downgrade() -> None:
    op.drop_table('campaign_sends')
    op.drop_table('campaign_facilities')
    op.drop_table('email_campaigns')
    op.drop_table('scraper_jobs')
    op.drop_table('contact_leads')
    op.drop_table('healthcare_facilities')

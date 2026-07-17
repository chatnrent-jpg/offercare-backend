"""zkTLS Platform Foundation - Phase 1 & 2

Revision ID: 042_zktls_platform_schema
Revises: 041_webhook_system
Create Date: 2026-07-16 12:19:00.000000

This migration creates the complete zkTLS credential verification platform:

Phase 1 (Free Badges):
- Users can create free accounts
- Verify LinkedIn and Healthcare credentials via Reclaim Protocol
- Public shareable badge profiles

Phase 2 (B2B API):
- Developer API keys
- Usage tracking for metered billing
- Stripe integration for monthly invoicing

Timeline:
- Free Badges Launch: August 15, 2026
- B2B API Launch: September 15, 2026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '042_zktls_platform_schema'
down_revision = '041_webhook_system'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create all zkTLS platform tables.
    
    Tables created:
    1. users - Core authentication (reusing existing if present)
    2. public_profiles - Public badge portfolios
    3. credentials - zkTLS verified badges
    4. reclaim_sessions - Reclaim Protocol session tracking
    5. developer_profiles - API keys for B2B
    6. usage_logs - Metered billing tracking
    7. billing_periods - Monthly Stripe invoices
    8. badge_views - Analytics
    """
    
    # ========================================================================
    # Enable UUID extension if not already enabled
    # ========================================================================
    
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    
    
    # ========================================================================
    # Table 1: Users (Core Authentication)
    # ========================================================================
    
    # Check if users table already exists (might exist from previous migrations)
    # If it exists, we'll add missing columns. If not, create it.
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'users' not in existing_tables:
        # Create users table from scratch
        op.create_table(
            'users',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('full_name', sa.String(255)),
            sa.Column('username', sa.String(50), unique=True, index=True),
            sa.Column('profile_image_url', sa.Text),
            sa.Column('stripe_customer_id', sa.String(255), index=True),
            sa.Column('is_email_verified', sa.Boolean, server_default='false'),
            sa.Column('is_active', sa.Boolean, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'))
        )
        
        # Create indexes
        op.create_index('idx_users_email', 'users', ['email'])
        op.create_index('idx_users_username', 'users', ['username'])
        op.create_index('idx_users_stripe', 'users', ['stripe_customer_id'])
    else:
        # Users table exists, add missing columns if they don't exist
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'username' not in existing_columns:
            op.add_column('users', sa.Column('username', sa.String(50), unique=True))
            op.create_index('idx_users_username', 'users', ['username'])
        
        if 'profile_image_url' not in existing_columns:
            op.add_column('users', sa.Column('profile_image_url', sa.Text))
        
        if 'stripe_customer_id' not in existing_columns:
            op.add_column('users', sa.Column('stripe_customer_id', sa.String(255)))
            op.create_index('idx_users_stripe', 'users', ['stripe_customer_id'])
        
        if 'is_email_verified' not in existing_columns:
            op.add_column('users', sa.Column('is_email_verified', sa.Boolean, server_default='false'))
    
    
    # ========================================================================
    # Table 2: Public Profiles (Shareable Badge Portfolios)
    # ========================================================================
    
    op.create_table(
        'public_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        
        # Display Settings
        sa.Column('display_name', sa.String(255)),
        sa.Column('bio', sa.Text),
        sa.Column('website_url', sa.Text),
        sa.Column('twitter_handle', sa.String(50)),
        sa.Column('linkedin_url', sa.Text),
        
        # Badge Display Order (array of credential IDs)
        sa.Column('badge_order', postgresql.JSONB),
        
        # Visibility
        sa.Column('is_public', sa.Boolean, server_default='true', index=True),
        
        # Analytics
        sa.Column('view_count', sa.Integer, server_default='0'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    
    op.create_index('idx_public_profiles_user', 'public_profiles', ['user_id'])
    op.create_index('idx_public_profiles_public', 'public_profiles', ['is_public'])
    
    
    # ========================================================================
    # Table 3: Credentials (zkTLS Verified Badges)
    # ========================================================================
    
    op.create_table(
        'credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Provider Information
        sa.Column('provider_type', sa.String(50), nullable=False, index=True),  # LINKEDIN, MBON_HEALTHCARE
        sa.Column('reclaim_provider_id', sa.String(100), nullable=False),
        
        # Proof Data
        sa.Column('proof_data', postgresql.JSONB, nullable=False),
        sa.Column('proof_hash', sa.String(64), nullable=False, index=True),
        
        # Extracted Claims
        sa.Column('claims', postgresql.JSONB),
        
        # Verification Status
        sa.Column('is_valid', sa.Boolean, server_default='true', index=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        
        # Visibility
        sa.Column('is_public', sa.Boolean, server_default='true', index=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    
    op.create_index('idx_credentials_user', 'credentials', ['user_id'])
    op.create_index('idx_credentials_provider', 'credentials', ['provider_type'])
    op.create_index('idx_credentials_valid', 'credentials', ['is_valid'])
    op.create_index('idx_credentials_public', 'credentials', ['is_public'])
    op.create_index('idx_credentials_hash', 'credentials', ['proof_hash'])
    op.create_index('idx_credentials_user_provider', 'credentials', ['user_id', 'provider_type'])
    op.create_index('idx_credentials_user_valid', 'credentials', ['user_id', 'is_valid'])
    
    
    # ========================================================================
    # Table 4: Reclaim Sessions (Track Proof Generation)
    # ========================================================================
    
    op.create_table(
        'reclaim_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), index=True),
        
        # Reclaim Data
        sa.Column('reclaim_session_id', sa.String(255), nullable=False, index=True),
        sa.Column('provider_type', sa.String(50), nullable=False),
        
        # Status: PENDING, IN_PROGRESS, COMPLETED, FAILED
        sa.Column('status', sa.String(50), server_default='PENDING', index=True),
        sa.Column('callback_url', sa.Text),
        
        # Result
        sa.Column('proof_data', postgresql.JSONB),
        sa.Column('error_message', sa.Text),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(timezone=True))
    )
    
    op.create_index('idx_reclaim_sessions_user', 'reclaim_sessions', ['user_id'])
    op.create_index('idx_reclaim_sessions_status', 'reclaim_sessions', ['status'])
    op.create_index('idx_reclaim_sessions_reclaim_id', 'reclaim_sessions', ['reclaim_session_id'])
    
    
    # ========================================================================
    # Table 5: Developer Profiles (Phase 2 - B2B API)
    # ========================================================================
    
    op.create_table(
        'developer_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), index=True),
        
        # API Key
        sa.Column('api_key_prefix', sa.String(20), nullable=False),
        sa.Column('api_key_hash', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('api_key_name', sa.String(100)),
        
        # Rate Limiting
        sa.Column('rate_limit_rpm', sa.Integer, server_default='60'),
        sa.Column('rate_limit_daily', sa.Integer, server_default='10000'),
        
        # Status
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(timezone=True))
    )
    
    op.create_index('idx_dev_profiles_user', 'developer_profiles', ['user_id'])
    op.create_index('idx_dev_profiles_key_hash', 'developer_profiles', ['api_key_hash'])
    op.create_index('idx_dev_profiles_active', 'developer_profiles', ['is_active'])
    
    
    # ========================================================================
    # Table 6: Usage Logs (Phase 2 - Metered Billing)
    # ========================================================================
    
    op.create_table(
        'usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('developer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('developer_profiles.id', ondelete='SET NULL'), index=True),
        
        # Request Information
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer, nullable=False),
        sa.Column('response_time_ms', sa.Integer),
        
        # Billing
        sa.Column('is_billable', sa.Boolean, server_default='true', index=True),
        sa.Column('cost_cents', sa.Integer, server_default='10'),  # $0.10 = 10 cents
        
        # Metadata
        sa.Column('ip_address', postgresql.INET),
        sa.Column('user_agent', sa.Text),
        
        # Timestamp
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), index=True)
    )
    
    op.create_index('idx_usage_logs_dev', 'usage_logs', ['developer_id'])
    op.create_index('idx_usage_logs_created', 'usage_logs', ['created_at'])
    op.create_index('idx_usage_logs_billable', 'usage_logs', ['is_billable'])
    op.create_index('idx_usage_logs_dev_created', 'usage_logs', ['developer_id', 'created_at'])
    
    
    # ========================================================================
    # Table 7: Billing Periods (Phase 2 - Stripe Integration)
    # ========================================================================
    
    op.create_table(
        'billing_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('developer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('developer_profiles.id', ondelete='CASCADE'), index=True),
        
        # Period
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False, index=True),
        
        # Usage
        sa.Column('total_requests', sa.Integer, server_default='0'),
        sa.Column('billable_requests', sa.Integer, server_default='0'),
        
        # Billing
        sa.Column('amount_cents', sa.Integer, server_default='0'),
        sa.Column('stripe_invoice_id', sa.String(255)),
        sa.Column('paid_at', sa.DateTime(timezone=True)),
        
        # Timestamp
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    
    op.create_index('idx_billing_periods_dev', 'billing_periods', ['developer_id'])
    op.create_index('idx_billing_periods_dates', 'billing_periods', ['period_start', 'period_end'])
    
    
    # ========================================================================
    # Table 8: Badge Views (Analytics)
    # ========================================================================
    
    op.create_table(
        'badge_views',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('credential_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('credentials.id', ondelete='CASCADE'), index=True),
        
        # Viewer Information
        sa.Column('viewer_ip', postgresql.INET),
        sa.Column('viewer_country', sa.CHAR(2)),  # ISO country code
        sa.Column('referrer', sa.Text),
        
        # Timestamp
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), index=True)
    )
    
    op.create_index('idx_badge_views_credential', 'badge_views', ['credential_id'])
    op.create_index('idx_badge_views_created', 'badge_views', ['created_at'])
    
    
    # ========================================================================
    # Triggers: Auto-update updated_at timestamps
    # ========================================================================
    
    # Create trigger function if it doesn't exist
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Apply triggers to tables with updated_at
    if 'users' in existing_tables:
        # Only create trigger if it doesn't exist
        op.execute("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
            CREATE TRIGGER update_users_updated_at 
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
    
    op.execute("""
        CREATE TRIGGER update_credentials_updated_at 
        BEFORE UPDATE ON credentials
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    op.execute("""
        CREATE TRIGGER update_public_profiles_updated_at 
        BEFORE UPDATE ON public_profiles
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    
    # ========================================================================
    # Comments for Documentation
    # ========================================================================
    
    op.execute("COMMENT ON TABLE public_profiles IS 'Public shareable badge portfolios (vettedme.ai/@username)'")
    op.execute("COMMENT ON TABLE credentials IS 'zkTLS credential badges issued via Reclaim Protocol'")
    op.execute("COMMENT ON TABLE reclaim_sessions IS 'Track ongoing Reclaim Protocol proof generation'")
    op.execute("COMMENT ON TABLE developer_profiles IS 'Developer API keys and rate limiting (Phase 2)'")
    op.execute("COMMENT ON TABLE usage_logs IS 'API usage tracking for metered billing (Phase 2)'")
    op.execute("COMMENT ON TABLE billing_periods IS 'Monthly billing cycles and Stripe invoices (Phase 2)'")
    op.execute("COMMENT ON TABLE badge_views IS 'Analytics for badge impressions'")


def downgrade():
    """
    Drop all zkTLS platform tables.
    
    WARNING: This will delete all user credentials, badges, and billing data!
    """
    
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('badge_views')
    op.drop_table('billing_periods')
    op.drop_table('usage_logs')
    op.drop_table('developer_profiles')
    op.drop_table('reclaim_sessions')
    op.drop_table('credentials')
    op.drop_table('public_profiles')
    
    # Drop trigger function
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE')
    
    # Note: We don't drop users table as it might be used by other parts of the system
    # If you want to drop users table columns we added, uncomment:
    # op.drop_column('users', 'username')
    # op.drop_column('users', 'profile_image_url')
    # op.drop_column('users', 'stripe_customer_id')
    # op.drop_column('users', 'is_email_verified')

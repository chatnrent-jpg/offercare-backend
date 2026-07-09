"""Fix Alembic version table - Replace D-drive hash with C-drive heads."""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("ERROR: DATABASE_URL not found in environment")
    print("Make sure DATABASE_URL is set in .env file")
    sys.exit(1)

try:
    engine = create_engine(db_url)
    
    print("=" * 70)
    print("ALEMBIC VERSION FIX - Replace D-drive hash with C-drive heads")
    print("=" * 70)
    
    # Display current state
    print("\n[CURRENT STATE]")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        current = [row[0] for row in result.fetchall()]
        print(f"  Database currently has: {current}")
    
    # Define the fix
    d_drive_hash = '6d70c89a31e3'
    c_drive_heads = ['028_ai_audit_logs', '038_security_hardening_tables']
    
    print("\n[PROPOSED FIX]")
    print(f"  1. Remove D-drive merge hash: {d_drive_hash}")
    print(f"  2. Add C-drive branch heads:")
    for head in c_drive_heads:
        print(f"     - {head}")
    print("\n  This will allow 'alembic upgrade head' to apply the")
    print("  C-drive merge file: 585f0d1d3e09_merge_ai_and_production_heads.py")
    
    print("\nApply this fix? (yes/no): ", end="", flush=True)
    response = input().strip().lower()
    
    if response == 'yes':
        print("\nApplying fix...")
        with engine.begin() as conn:
            # Remove D-drive hash
            conn.execute(text(f"DELETE FROM alembic_version WHERE version_num = :hash"),
                        {"hash": d_drive_hash})
            print(f"  [OK] Removed {d_drive_hash}")
            
            # Add C-drive heads
            for head in c_drive_heads:
                conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
                            {"head": head})
                print(f"  [OK] Added {head}")
        
        print("\n[SUCCESS] Fix applied!")
        print("\nVerifying...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
            new_state = [row[0] for row in result.fetchall()]
            print("  New database state:")
            for v in new_state:
                print(f"    - {v}")
        
        print("\n" + "=" * 70)
        print("NEXT STEP: Run 'alembic upgrade head' to apply the C-drive merge")
        print("=" * 70)
    else:
        print("\nFix NOT applied. Exiting.")
        sys.exit(0)
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

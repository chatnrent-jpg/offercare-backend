"""
VettedMe Dependency Checker

Run this script to verify all required dependencies are installed correctly.
"""

import sys
from typing import List, Tuple

# Color codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def check_package(package_name: str, import_name: str = None) -> Tuple[bool, str]:
    """Check if a package is installed and return version"""
    if import_name is None:
        import_name = package_name.replace('-', '_').replace('[', '').replace(']', '')
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        return True, version
    except ImportError:
        return False, 'not installed'

def check_python_version():
    """Check Python version"""
    print_header("SYSTEM INFORMATION")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print(f"Python Version: {version_str}")
    
    if version.major == 3 and version.minor >= 10:
        print(f"{GREEN}✅ Python version is compatible (3.10+){RESET}")
        return True
    else:
        print(f"{RED}❌ Python version is too old. Need 3.10+, got {version_str}{RESET}")
        return False

def check_dependencies():
    """Check all required dependencies"""
    print_header("CHECKING DEPENDENCIES")
    
    # List of (package_name, import_name, required)
    packages = [
        # Core FastAPI
        ('fastapi', 'fastapi', True),
        ('uvicorn', 'uvicorn', True),
        ('python-multipart', 'multipart', True),
        
        # Database
        ('sqlalchemy', 'sqlalchemy', True),
        ('alembic', 'alembic', True),
        ('psycopg2-binary', 'psycopg2', True),
        
        # Authentication
        ('python-jose', 'jose', True),
        ('passlib', 'passlib', True),
        ('bcrypt', 'bcrypt', True),
        ('cryptography', 'cryptography', True),
        
        # Data Validation
        ('pydantic', 'pydantic', True),
        ('email-validator', 'email_validator', True),
        
        # HTTP Client
        ('httpx', 'httpx', False),
        ('requests', 'requests', True),
        
        # Utilities
        ('python-dotenv', 'dotenv', True),
        
        # Optional
        ('stripe', 'stripe', False),
        ('sentry-sdk', 'sentry_sdk', False),
    ]
    
    all_required_installed = True
    results = []
    
    for package_name, import_name, required in packages:
        installed, version = check_package(package_name, import_name)
        
        if installed:
            status = f"{GREEN}✅ INSTALLED{RESET}"
            results.append((package_name, version, status, True))
        else:
            if required:
                status = f"{RED}❌ MISSING (REQUIRED){RESET}"
                all_required_installed = False
            else:
                status = f"{YELLOW}⚠️  NOT INSTALLED (OPTIONAL){RESET}"
            results.append((package_name, version, status, False))
    
    # Print results
    print(f"{'Package':<25} {'Version':<15} {'Status'}")
    print("-" * 70)
    
    for package_name, version, status, installed in results:
        if installed:
            print(f"{package_name:<25} {version:<15} {status}")
        else:
            print(f"{package_name:<25} {'N/A':<15} {status}")
    
    return all_required_installed

def check_database():
    """Check database connection"""
    print_header("CHECKING DATABASE CONNECTION")
    
    try:
        import os
        from dotenv import load_dotenv
        
        # Load .env file
        load_dotenv()
        
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            print(f"{YELLOW}⚠️  DATABASE_URL not found in .env file{RESET}")
            print(f"{YELLOW}   Create a .env file with: DATABASE_URL=postgresql://user:pass@localhost:5432/vettedme{RESET}")
            return False
        
        print(f"Database URL: {database_url[:30]}...{database_url[-20:]}")
        
        # Try to connect
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        print(f"{GREEN}✅ Database connection successful{RESET}")
        return True
        
    except ImportError as e:
        print(f"{RED}❌ Missing dependencies: {e}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}❌ Database connection failed: {e}{RESET}")
        print(f"{YELLOW}   Make sure PostgreSQL is running and .env is configured correctly{RESET}")
        return False

def check_alembic():
    """Check Alembic setup"""
    print_header("CHECKING ALEMBIC MIGRATIONS")
    
    try:
        from alembic.config import Config
        from alembic import command
        import io
        
        # Check if alembic.ini exists
        import os
        if not os.path.exists('alembic.ini'):
            print(f"{RED}❌ alembic.ini not found{RESET}")
            print(f"{YELLOW}   Run: alembic init alembic{RESET}")
            return False
        
        print(f"{GREEN}✅ alembic.ini found{RESET}")
        
        # Check if versions directory exists
        if not os.path.exists('alembic/versions'):
            print(f"{RED}❌ alembic/versions directory not found{RESET}")
            return False
        
        print(f"{GREEN}✅ alembic/versions directory found{RESET}")
        
        # Count migrations
        migrations = [f for f in os.listdir('alembic/versions') if f.endswith('.py') and f != '__pycache__']
        print(f"{GREEN}✅ Found {len(migrations)} migration(s){RESET}")
        
        if '042_zktls_platform_schema.py' in migrations:
            print(f"{GREEN}✅ zkTLS migration (042) found{RESET}")
        else:
            print(f"{YELLOW}⚠️  zkTLS migration (042) not found{RESET}")
        
        return True
        
    except Exception as e:
        print(f"{RED}❌ Alembic check failed: {e}{RESET}")
        return False

def check_env_file():
    """Check .env file configuration"""
    print_header("CHECKING ENVIRONMENT CONFIGURATION")
    
    import os
    from dotenv import load_dotenv
    
    if not os.path.exists('.env'):
        print(f"{YELLOW}⚠️  .env file not found{RESET}")
        print(f"{YELLOW}   Create .env file with required environment variables{RESET}")
        return False
    
    print(f"{GREEN}✅ .env file found{RESET}")
    
    load_dotenv()
    
    required_vars = [
        'DATABASE_URL',
        'JWT_SECRET',
    ]
    
    optional_vars = [
        'RECLAIM_APP_ID',
        'RECLAIM_APP_SECRET',
        'STRIPE_SECRET_KEY',
    ]
    
    all_required_set = True
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Hide sensitive values
            if 'SECRET' in var or 'PASSWORD' in var:
                display_value = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "****"
            else:
                display_value = f"{value[:30]}..." if len(value) > 30 else value
            print(f"{GREEN}✅ {var:<25} = {display_value}{RESET}")
        else:
            print(f"{RED}❌ {var:<25} NOT SET{RESET}")
            all_required_set = False
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            display_value = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else value
            print(f"{GREEN}✅ {var:<25} = {display_value}{RESET}")
        else:
            print(f"{YELLOW}⚠️  {var:<25} NOT SET (optional for Phase 2){RESET}")
    
    return all_required_set

def print_summary(python_ok, deps_ok, db_ok, alembic_ok, env_ok):
    """Print final summary"""
    print_header("SUMMARY")
    
    checks = [
        ("Python Version", python_ok),
        ("Required Dependencies", deps_ok),
        ("Database Connection", db_ok),
        ("Alembic Setup", alembic_ok),
        ("Environment Variables", env_ok),
    ]
    
    all_ok = all(ok for _, ok in checks)
    
    for check_name, ok in checks:
        status = f"{GREEN}✅ PASS{RESET}" if ok else f"{RED}❌ FAIL{RESET}"
        print(f"{check_name:<30} {status}")
    
    print()
    
    if all_ok:
        print(f"{GREEN}{'='*70}{RESET}")
        print(f"{GREEN}🎉 ALL CHECKS PASSED! YOU'RE READY TO GO! 🎉{RESET}")
        print(f"{GREEN}{'='*70}{RESET}\n")
        
        print(f"{BLUE}Next Steps:{RESET}")
        print(f"1. Run migrations: {YELLOW}alembic upgrade head{RESET}")
        print(f"2. Start server: {YELLOW}python -m uvicorn app.main:app --reload{RESET}")
        print(f"3. Test system: {YELLOW}python test_auth_api.py{RESET}")
        print(f"4. Open browser: {YELLOW}http://localhost:8000/docs{RESET}\n")
    else:
        print(f"{RED}{'='*70}{RESET}")
        print(f"{RED}❌ SOME CHECKS FAILED - PLEASE FIX THE ISSUES ABOVE{RESET}")
        print(f"{RED}{'='*70}{RESET}\n")
        
        print(f"{BLUE}Quick Fixes:{RESET}")
        if not deps_ok:
            print(f"• Install dependencies: {YELLOW}pip install -r requirements_zktls.txt{RESET}")
        if not db_ok:
            print(f"• Create database: {YELLOW}psql -U postgres -c 'CREATE DATABASE vettedme;'{RESET}")
            print(f"• Configure .env: {YELLOW}DATABASE_URL=postgresql://postgres:password@localhost:5432/vettedme{RESET}")
        if not env_ok:
            print(f"• Create .env file with required variables (see DEPLOYMENT_CHECKLIST.md)")
        print()

def main():
    """Run all checks"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{'VettedMe zkTLS Platform - Dependency Checker':^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    python_ok = check_python_version()
    deps_ok = check_dependencies()
    db_ok = check_database()
    alembic_ok = check_alembic()
    env_ok = check_env_file()
    
    print_summary(python_ok, deps_ok, db_ok, alembic_ok, env_ok)

if __name__ == "__main__":
    main()

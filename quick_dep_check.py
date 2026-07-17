"""Quick check for missing dependencies"""

required = [
    'fastapi', 'uvicorn', 'multipart', 'sqlalchemy', 'alembic', 
    'psycopg2', 'jose', 'passlib', 'bcrypt', 'cryptography',
    'pydantic', 'email_validator', 'requests', 'dotenv'
]

missing = []
installed = []

for pkg in required:
    try:
        __import__(pkg)
        installed.append(pkg)
    except ImportError:
        missing.append(pkg)

print(f"\n✅ Installed ({len(installed)}/{len(required)}):")
for pkg in installed:
    print(f"  - {pkg}")

if missing:
    print(f"\n❌ Missing ({len(missing)}):")
    for pkg in missing:
        print(f"  - {pkg}")
    print("\nRun: pip install -r requirements_zktls.txt")
else:
    print("\n🎉 All required packages installed!")

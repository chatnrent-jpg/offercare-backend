# VettedMe zkTLS - Quick Start Guide

**Goal:** Get your system running in 15 minutes

---

## 🚀 Fast Track Installation

### 1. Install Dependencies (5 minutes)

```bash
cd C:\vettedcare.ai\vettedcare-backend

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install all dependencies
pip install -r requirements_zktls.txt
```

### 2. Setup Database (3 minutes)

```bash
# Create database
psql -U postgres -c "CREATE DATABASE vettedme;"

# Run migrations
alembic upgrade head
```

### 3. Configure Environment (2 minutes)

Create `.env` file:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/vettedme
JWT_SECRET=CHANGE_THIS_IN_PRODUCTION_USE_RANDOM_STRING
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 4. Start Backend (1 minute)

```bash
python -m uvicorn app.main:app --reload
```

**Open:** http://localhost:8000/docs

### 5. Test It (4 minutes)

```bash
# In another terminal
python test_auth_api.py
```

**Expected:** All 9 tests pass ✅

---

## ✅ That's It!

Your production-grade zkTLS platform is running.

**Next Steps:**
1. Read `WEEK1_COMPLETE.md` for details
2. Read `DEPLOYMENT_CHECKLIST.md` for production
3. Move to Week 2 (LinkedIn + Healthcare badges)

---

## 🆘 Quick Troubleshooting

### Server won't start?
```bash
# Check Python version (need 3.10+)
python --version

# Check if port 8000 is in use
netstat -an | findstr 8000
```

### Database connection fails?
```bash
# Check PostgreSQL is running
psql -U postgres -c "SELECT 1;"

# Check .env file has correct DATABASE_URL
```

### Migrations fail?
```bash
# Check current migration
alembic current

# Try fresh start
alembic downgrade base
alembic upgrade head
```

---

**Need more details?** Read `DEPLOYMENT_CHECKLIST.md`

**Ready for production?** You're almost there! 🎯

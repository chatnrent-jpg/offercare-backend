# Quick Fix Guide - Server Not Starting

## Option 1: Check Git Diff (See what changed)
```bash
git diff app/main.py
```

## Option 2: Revert app/main.py Changes
```bash
git checkout HEAD -- app/main.py
```

## Option 3: Start with Minimal main.py

If all else fails, temporarily comment out these lines in app/main.py:

```python
# Comment out these imports (line 9):
# from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

# Comment out custom /docs route (around line 468):
# @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
# async def custom_swagger_ui_html():
#     """Custom dark-themed Swagger UI"""
#     return get_swagger_ui_html(...)

# Comment out custom /redoc route (around line 478):
# @app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
# async def custom_redoc_html():
#     """Custom dark-themed ReDoc"""
#     return get_redoc_html(...)
```

Then restart:
```bash
python -m uvicorn app.main:app --reload
```

## Option 4: Use Standard FastAPI Docs

Change line 109-115 from:
```python
app = FastAPI(
    title="VettedMe.ai API",
    description="The Universal Trust Platform - Cryptographically verified digital credentials",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
)
```

To:
```python
app = FastAPI(
    title="VettedMe.ai API",
    description="The Universal Trust Platform - Cryptographically verified digital credentials",
    version="1.0.0",
    lifespan=lifespan,
    # docs_url and redoc_url will use defaults (/docs and /redoc)
)
```

This will restore the default Swagger UI and ReDoc.

"""
VettedMe zkTLS Platform - Clean Minimal Server
This is a streamlined version that ONLY loads the new zkTLS routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import ONLY the new zkTLS routers
from app.routers.auth import router as auth_router
from app.routers.credentials import router as credentials_router
from app.routers.reclaim import router as reclaim_router

# Create FastAPI app
app = FastAPI(
    title="VettedMe zkTLS Platform",
    description="Zero-Knowledge TLS Credential Verification Platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3005"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Register new zkTLS routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(credentials_router, prefix="/api/v1/credentials", tags=["Credentials"])
app.include_router(reclaim_router, prefix="/api/v1/reclaim", tags=["Reclaim Protocol"])

# Homepage route
@app.get("/")
async def homepage():
    """Serve the main homepage"""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VettedMe zkTLS Platform</title>
        <style>
            body { 
                font-family: system-ui; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: #0f172a;
                color: #e2e8f0;
            }
            h1 { color: #10b981; }
            a { color: #10b981; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .endpoint { 
                background: #1e293b; 
                padding: 10px; 
                margin: 10px 0; 
                border-radius: 5px;
                border-left: 3px solid #10b981;
            }
        </style>
    </head>
    <body>
        <h1>🚀 VettedMe zkTLS Platform</h1>
        <p>Zero-Knowledge TLS Credential Verification Platform</p>
        
        <h2>Available Endpoints:</h2>
        
        <div class="endpoint">
            <strong>📚 API Documentation:</strong><br>
            <a href="/docs">/docs</a> - Interactive API documentation (Swagger UI)
        </div>
        
        <div class="endpoint">
            <strong>🔐 Authentication:</strong><br>
            <a href="/api/v1/auth/register">POST /api/v1/auth/register</a> - Register new user<br>
            <a href="/api/v1/auth/login">POST /api/v1/auth/login</a> - Login<br>
            <a href="/api/v1/auth/me">GET /api/v1/auth/me</a> - Get current user profile
        </div>
        
        <div class="endpoint">
            <strong>🎫 Credentials:</strong><br>
            <a href="/api/v1/credentials">GET /api/v1/credentials</a> - List your credentials<br>
            <a href="/api/v1/credentials/stats/summary">GET /api/v1/credentials/stats/summary</a> - Get stats
        </div>
        
        <div class="endpoint">
            <strong>🔗 Reclaim Protocol:</strong><br>
            <a href="/api/v1/reclaim/session/start">POST /api/v1/reclaim/session/start</a> - Start verification session<br>
            <a href="/api/v1/reclaim/webhook">POST /api/v1/reclaim/webhook</a> - Webhook callback
        </div>
        
        <h2>Status: ✅ Running</h2>
    </body>
    </html>
    """)

# API status endpoint
@app.get("/api/status")
async def api_status():
    """API health check"""
    return {
        "status": "online",
        "platform": "VettedMe zkTLS",
        "version": "1.0.0",
        "routes": {
            "auth": "/api/v1/auth",
            "credentials": "/api/v1/credentials",
            "reclaim": "/api/v1/reclaim"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.core.database import get_db
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend REST API and Judicial Services for Court Case Scheduling and Hearing Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

# --- Frontend Web Routes (Aceternity UI) ---
@app.get("/", response_class=HTMLResponse, tags=["Web"])
def landing_page(request: Request):
    """Aceternity 3D Hero & Judicial Landing Page"""
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/auth", response_class=HTMLResponse, tags=["Web"])
def auth_page(request: Request):
    """Aceternity Split Auth with RBAC Demo Selectors"""
    return templates.TemplateResponse(request=request, name="auth.html")

@app.get("/dashboard", response_class=HTMLResponse, tags=["Web"])
def dashboard_page(request: Request):
    """Unified Role-Adaptive Judicial Dashboard"""
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        # Check DB connectivity
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "operational",
        "database": db_status,
        "environment": settings.ENVIRONMENT
    }

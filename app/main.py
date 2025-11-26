from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.employees import router as employees_router
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.core.logging import get_logger
from app.models.employee import Employee

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")
    logger.info("Creating database and tables...")
    # Explicitly passing models to create only necessary tables
    create_db_and_tables(Employee)
    logger.info("Database and tables created successfully")
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down...")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Include routers
app.include_router(employees_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.
    Returns service status and basic information.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

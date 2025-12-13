"""FastAPI Server for n8n Integration"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from api.routes import router
from dashboard.routes import router as dashboard_router
import uvicorn
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Crypto Trading Bot API", version="1.0.0")

# Global Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException and return JSON response"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions and return JSON response"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Check if we're in debug mode (via environment variable or app config)
    import os
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if debug_mode else "An unexpected error occurred"
        }
    )

# CORS middleware for n8n
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
# Include dashboard router FIRST so its "/" route takes precedence
app.include_router(dashboard_router)
app.include_router(router)

# Include bot control routes
from dashboard.routes_bot_control import router as bot_control_router
app.include_router(bot_control_router)

# Include training routes
from dashboard.routes_training import router as training_router
app.include_router(training_router)

# Include backtesting routes
from dashboard.routes_backtesting import router as backtesting_router
app.include_router(backtesting_router)

# Include strategy management routes
try:
    from dashboard.routes_strategies import router as strategies_router
    app.include_router(strategies_router)
    logger.info("Strategy management routes registered")
except ImportError as e:
    logger.warning(f"Strategy management routes not available: {e}")

# Serve static files for dashboard
dashboard_static = Path(__file__).parent.parent / "dashboard" / "static"
if dashboard_static.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(dashboard_static)), name="static")
        logger.info(f"Static files mounted from: {dashboard_static}")
    except Exception as e:
        logger.warning(f"Could not mount static files: {e}")

# Root endpoint removed - dashboard router handles "/" route
# If you need the API info, use /api/info or similar
@app.get("/api/info")
async def api_info():
    """API information endpoint"""
    return {"message": "Crypto Trading Bot API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from datetime import datetime
    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Health check endpoint available - use /api/v1/health for detailed checks"
    }

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()


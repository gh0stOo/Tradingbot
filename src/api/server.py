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

# Include bot control routes (SQLite-based for Docker compatibility)
try:
    from dashboard.routes_bot_control_sqlite import router as bot_control_router
    app.include_router(bot_control_router)
    logger.info("Bot control routes (SQLite-based) registered")
except ImportError:
    # Fallback to old in-memory routes if SQLite routes not available
    from dashboard.routes_bot_control import router as bot_control_router
    app.include_router(bot_control_router)
    logger.warning("Using in-memory bot control routes (SQLite routes not available)")

# Include training routes
from dashboard.routes_training import router as training_router
app.include_router(training_router)

# Include backtesting routes
from dashboard.routes_backtesting import router as backtesting_router
app.include_router(backtesting_router)

# Include WebSocket routes
from dashboard.routes_websocket import router as websocket_router
app.include_router(websocket_router)

# Include strategy management routes
try:
    from dashboard.routes_strategies import router as strategies_router
    app.include_router(strategies_router)
    logger.info("Strategy management routes registered")
except ImportError as e:
    logger.warning(f"Strategy management routes not available: {e}")

# Include settings management routes
from dashboard.routes_settings import router as settings_router
app.include_router(settings_router)
logger.info("Settings management routes registered")

# Include events monitoring routes
from dashboard.routes_events import router as events_router
app.include_router(events_router)
logger.info("Events monitoring routes registered")

# Include enhanced events routes (filtering, search, stats)
from dashboard.routes_events_enhanced import router as events_enhanced_router
app.include_router(events_enhanced_router)
logger.info("Enhanced events routes registered (filtering, search, stats)")

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
    """Health check endpoint - lightweight and fast"""
    from datetime import datetime, timezone
    return {
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Health check endpoint available - use /api/v1/health for detailed checks"
    }

# Backward-compatible status route for dashboards expecting /api/bot/status
@app.get("/api/bot/status")
async def bot_status_alias():
    """Alias to the main status endpoint."""
    try:
        from api.routes import get_status  # type: ignore
    except Exception:
        return {"status": "unknown"}
    return await get_status()  # proxy to existing implementation


def _get_bot_control_handler(handler_name: str):
    """
    Return the bot control handler (SQLite first, fallback to in-memory).
    This keeps compatibility with dashboard calls like /api/bot/start.
    """
    try:
        module = __import__("dashboard.routes_bot_control_sqlite", fromlist=[handler_name])
    except ImportError:
        module = __import__("dashboard.routes_bot_control", fromlist=[handler_name])
    return getattr(module, handler_name, None)


@app.post("/api/bot/start")
async def bot_start_alias():
    """Backward-compatible start endpoint for dashboards expecting /api/bot/start."""
    handler = _get_bot_control_handler("start_bot")
    if handler is None:
        raise HTTPException(status_code=500, detail="Bot control handler not available")
    return await handler()


@app.post("/api/bot/stop")
async def bot_stop_alias():
    """Backward-compatible stop endpoint for dashboards expecting /api/bot/stop."""
    handler = _get_bot_control_handler("stop_bot")
    if handler is None:
        raise HTTPException(status_code=500, detail="Bot control handler not available")
    return await handler()


@app.post("/api/bot/pause")
async def bot_pause_alias():
    """Backward-compatible pause endpoint for dashboards expecting /api/bot/pause."""
    handler = _get_bot_control_handler("pause_bot")
    if handler is None:
        raise HTTPException(status_code=500, detail="Bot control handler not available")
    return await handler()


@app.post("/api/bot/resume")
async def bot_resume_alias():
    """Backward-compatible resume endpoint for dashboards expecting /api/bot/resume."""
    handler = _get_bot_control_handler("resume_bot")
    if handler is None:
        raise HTTPException(status_code=500, detail="Bot control handler not available")
    return await handler()

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()


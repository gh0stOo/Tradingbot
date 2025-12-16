"""Settings API Routes - Read and update configurable parameters with persistence"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import os

from utils.config_loader import ConfigLoader
from dashboard.settings_db import get_settings_db
from dashboard.audit_trail import get_audit_trail, AuditAction

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize config loader, settings database, and audit trail
config_loader = ConfigLoader()
settings_db = get_settings_db()
audit_trail = get_audit_trail()

class SettingUpdate(BaseModel):
    key: str  # e.g., "trading.mode", "risk.paperEquity"
    value: Any

class SettingsUpdateRequest(BaseModel):
    updates: list[SettingUpdate]

# ============ SCHEMA DEFINITION ============

SETTINGS_SCHEMA = {
    "trading.mode": {
        "type": "enum",
        "label": "Trading Mode",
        "description": "PAPER (Simulated), TESTNET (Bybit Testnet), LIVE (Real Trading)",
        "options": ["PAPER", "TESTNET", "LIVE"],
        "category": "Trading",
        "readonly": False,
        "requires_restart": True
    },
    "trading.schedule_minutes": {
        "type": "integer",
        "label": "Schedule Interval (minutes)",
        "description": "How often to run trading logic",
        "min": 1,
        "max": 60,
        "category": "Trading",
        "readonly": False,
        "requires_restart": True
    },
    "risk.paperEquity": {
        "type": "number",
        "label": "Paper Trading Equity ($)",
        "description": "Starting capital for paper trading",
        "min": 1000,
        "max": 1000000,
        "category": "Risk Management",
        "readonly": False,
        "requires_restart": False
    },
    "risk.riskPct": {
        "type": "number",
        "label": "Risk Per Trade (%)",
        "description": "Risk as percentage of equity per trade",
        "min": 0.01,
        "max": 10,
        "category": "Risk Management",
        "readonly": False,
        "requires_restart": False
    },
    "risk.maxPositions": {
        "type": "integer",
        "label": "Max Open Positions",
        "description": "Maximum number of simultaneous open positions",
        "min": 1,
        "max": 50,
        "category": "Risk Management",
        "readonly": False,
        "requires_restart": False
    },
    "risk.maxExposure": {
        "type": "number",
        "label": "Max Exposure (%)",
        "description": "Maximum total exposure as fraction of equity",
        "min": 0.1,
        "max": 1.0,
        "category": "Risk Management",
        "readonly": False,
        "requires_restart": False
    },
    "risk.leverageMax": {
        "type": "number",
        "label": "Max Leverage",
        "description": "Maximum leverage for trades",
        "min": 1,
        "max": 50,
        "category": "Risk Management",
        "readonly": False,
        "requires_restart": False
    },
    "filters.minConfidence": {
        "type": "number",
        "label": "Min Signal Confidence",
        "description": "Minimum confidence threshold for trade signals (0-1)",
        "min": 0,
        "max": 1,
        "category": "Signal Filtering",
        "readonly": False,
        "requires_restart": False
    },
    "alerts.enabled": {
        "type": "boolean",
        "label": "Discord Alerts Enabled",
        "description": "Enable Discord webhook alerts for trading events",
        "category": "Alerts",
        "readonly": False,
        "requires_restart": False
    },
    "notion.enabled": {
        "type": "boolean",
        "label": "Notion Integration Enabled",
        "description": "Enable Notion database logging of trades and stats",
        "category": "Integrations",
        "readonly": False,
        "requires_restart": False
    },
    "ml.enabled": {
        "type": "boolean",
        "label": "ML Models Enabled",
        "description": "Enable machine learning signal predictions",
        "category": "Machine Learning",
        "readonly": False,
        "requires_restart": False
    }
}

# ============ GET SETTINGS ENDPOINT ============

@router.get("/api/settings")
async def get_settings() -> Dict[str, Any]:
    """Get all user-configurable settings (from database if persisted, else from config)"""
    try:
        settings = {}
        for key in SETTINGS_SCHEMA.keys():
            # Try to get from database first (persistent), fallback to config loader
            db_value = settings_db.get(key)
            value = db_value if db_value is not None else config_loader.get(key)
            settings[key] = {
                "value": value,
                "schema": SETTINGS_SCHEMA[key],
                "persisted": db_value is not None  # Flag indicating if value is persisted
            }

        return {
            "success": True,
            "settings": settings,
            "persistence": "enabled"
        }
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ GET SETTINGS SCHEMA ENDPOINT ============

@router.get("/api/settings/schema")
async def get_settings_schema() -> Dict[str, Any]:
    """Get settings schema (metadata + constraints)"""
    try:
        # Group by category
        schema_by_category = {}
        for key, schema_def in SETTINGS_SCHEMA.items():
            category = schema_def.get("category", "Other")
            if category not in schema_by_category:
                schema_by_category[category] = []

            schema_by_category[category].append({
                "key": key,
                "schema": schema_def
            })

        return {
            "success": True,
            "schema": schema_by_category
        }
    except Exception as e:
        logger.error(f"Error getting settings schema: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ UPDATE SETTINGS ENDPOINT ============

@router.post("/api/settings")
async def update_settings(request: SettingsUpdateRequest) -> Dict[str, Any]:
    """Update one or more settings with validation"""
    try:
        results = []
        requires_restart = False

        for update in request.updates:
            key = update.key
            value = update.value

            # Check if setting exists in schema
            if key not in SETTINGS_SCHEMA:
                results.append({
                    "key": key,
                    "success": False,
                    "error": f"Unknown setting: {key}"
                })
                # Log failed update attempt to audit trail
                audit_trail.log(
                    action=AuditAction.SETTING_UPDATED,
                    entity_type="settings",
                    entity_key=key,
                    old_value=None,
                    new_value=str(value),
                    result="failed",
                    error_message=f"Unknown setting: {key}"
                )
                continue

            schema = SETTINGS_SCHEMA[key]

            # Check if readonly
            if schema.get("readonly", False):
                results.append({
                    "key": key,
                    "success": False,
                    "error": "Setting is read-only"
                })
                # Log failed read-only update attempt
                audit_trail.log(
                    action=AuditAction.SETTING_UPDATED,
                    entity_type="settings",
                    entity_key=key,
                    old_value=None,
                    new_value=str(value),
                    result="failed",
                    error_message="Setting is read-only"
                )
                continue

            # Validate based on type
            validation_error = _validate_setting(key, value, schema)
            if validation_error:
                results.append({
                    "key": key,
                    "success": False,
                    "error": validation_error
                })
                # Log validation error to audit trail
                audit_trail.log(
                    action=AuditAction.SETTING_UPDATED,
                    entity_type="settings",
                    entity_key=key,
                    old_value=None,
                    new_value=str(value),
                    result="failed",
                    error_message=validation_error
                )
                continue

            # Get old value for audit trail
            old_db_value = settings_db.get(key)
            old_value_str = str(old_db_value) if old_db_value is not None else None
            new_value_str = str(value)

            # Update config in memory
            _set_nested_value(config_loader.config, key, value)

            # Persist to database
            schema_type = schema.get("type", "string")
            db_saved = settings_db.set(key, value, value_type=schema_type, updated_by="api")

            # Log successful update to audit trail
            audit_trail.log(
                action=AuditAction.SETTING_UPDATED,
                entity_type="settings",
                entity_key=key,
                old_value=old_value_str,
                new_value=new_value_str,
                result="success" if db_saved else "partial"
            )

            # Track if restart needed
            if schema.get("requires_restart", False):
                requires_restart = True

            results.append({
                "key": key,
                "success": True,
                "value": value,
                "persisted": db_saved
            })

        return {
            "success": True,
            "updates": results,
            "requires_restart": requires_restart,
            "persistence": "enabled",
            "message": "Settings updated and persisted to database" if results else "No valid updates"
        }
    except Exception as e:
        logger.error(f"Error updating settings: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

# ============ HELPER FUNCTIONS ============

def _validate_setting(key: str, value: Any, schema: Dict[str, Any]) -> Optional[str]:
    """Validate setting value against schema. Returns error message if invalid."""

    setting_type = schema.get("type", "string")

    if setting_type == "enum":
        options = schema.get("options", [])
        if value not in options:
            return f"Must be one of: {', '.join(map(str, options))}"

    elif setting_type == "boolean":
        if not isinstance(value, bool):
            return "Must be boolean (true/false)"

    elif setting_type == "integer":
        if not isinstance(value, int):
            return "Must be an integer"
        min_val = schema.get("min")
        max_val = schema.get("max")
        if min_val is not None and value < min_val:
            return f"Must be >= {min_val}"
        if max_val is not None and value > max_val:
            return f"Must be <= {max_val}"

    elif setting_type == "number":
        if not isinstance(value, (int, float)):
            return "Must be a number"
        min_val = schema.get("min")
        max_val = schema.get("max")
        if min_val is not None and value < min_val:
            return f"Must be >= {min_val}"
        if max_val is not None and value > max_val:
            return f"Must be <= {max_val}"

    return None

def _set_nested_value(config: Dict[str, Any], key: str, value: Any) -> None:
    """Set value in nested dictionary using dot notation"""
    keys = key.split(".")
    current = config

    # Navigate to parent
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    # Set the value
    current[keys[-1]] = value

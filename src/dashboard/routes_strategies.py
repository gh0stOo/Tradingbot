"""Dashboard Routes for Strategy Management"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/strategies", response_class=HTMLResponse)
async def strategies_page(request: Request):
    """Strategy management page"""
    return templates.TemplateResponse("strategies.html", {"request": request})


@router.get("/api/strategies")
async def get_strategies() -> Dict[str, Any]:
    """
    Get all strategy configurations.
    
    Returns:
        Dictionary with strategy configurations
    """
    try:
        from utils.config_loader import ConfigLoader
        
        config_loader = ConfigLoader()
        config = config_loader.config
        
        strategies_config = config.get("strategies", {})
        
        # Get strategy status from config
        strategies = {}
        for strategy_name, strategy_cfg in strategies_config.items():
            strategies[strategy_name] = {
                "name": strategy_name,
                "enabled": strategy_cfg.get("enabled", True),
                "weight": strategy_cfg.get("weight", 1.0),
                "regimes": strategy_cfg.get("regimes", ["all"]),
            }
        
        # Add event-driven strategies
        event_strategies = {
            "volatility_expansion": config.get("volatilityExpansion", {}),
            "mean_reversion": config.get("meanReversion", {}),
            "trend_continuation": config.get("trendContinuation", {}),
        }
        
        for strategy_name, strategy_cfg in event_strategies.items():
            if strategy_cfg:
                strategies[strategy_name] = {
                    "name": strategy_name,
                    "enabled": strategy_cfg.get("enabled", True),
                    "weight": strategy_cfg.get("weight", 1.0),
                }
        
        return {
            "success": True,
            "strategies": strategies,
        }
    
    except Exception as e:
        logger.error(f"Error getting strategies: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.post("/api/strategies/{strategy_name}/enable")
async def enable_strategy(strategy_name: str, enabled: bool = True) -> Dict[str, Any]:
    """
    Enable or disable a strategy.
    
    Args:
        strategy_name: Name of the strategy
        enabled: Whether to enable or disable
        
    Returns:
        Success status
    """
    try:
        from utils.config_loader import ConfigLoader
        from pathlib import Path
        
        config_loader = ConfigLoader()
        config_path = Path(config_loader.config_path) if hasattr(config_loader, 'config_path') else Path("config/config.yaml")
        
        # Load config file
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Update strategy config
        # Check in multiple locations
        updated = False
        
        if "strategies" in config_data and strategy_name in config_data["strategies"]:
            config_data["strategies"][strategy_name]["enabled"] = enabled
            updated = True
        
        # Check event-driven strategy configs
        strategy_key_map = {
            "volatility_expansion": "volatilityExpansion",
            "mean_reversion": "meanReversion",
            "trend_continuation": "trendContinuation",
        }
        
        if strategy_name in strategy_key_map:
            key = strategy_key_map[strategy_name]
            if key in config_data:
                config_data[key]["enabled"] = enabled
                updated = True
        
        if not updated:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": f"Strategy {strategy_name} not found"}
            )
        
        # Save config file
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Strategy {strategy_name} {'enabled' if enabled else 'disabled'}")
        
        return {
            "success": True,
            "strategy": strategy_name,
            "enabled": enabled,
        }
    
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_name}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.post("/api/strategies/{strategy_name}/weight")
async def update_strategy_weight(strategy_name: str, weight: float) -> Dict[str, Any]:
    """
    Update strategy weight.
    
    Args:
        strategy_name: Name of the strategy
        weight: New weight value
        
    Returns:
        Success status
    """
    try:
        from utils.config_loader import ConfigLoader
        from pathlib import Path
        
        config_loader = ConfigLoader()
        config_path = Path(config_loader.config_path) if hasattr(config_loader, 'config_path') else Path("config/config.yaml")
        
        # Load config file
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Validate weight
        if weight < 0 or weight > 2.0:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Weight must be between 0 and 2.0"}
            )
        
        # Update strategy weight
        updated = False
        if "strategies" in config_data and strategy_name in config_data["strategies"]:
            config_data["strategies"][strategy_name]["weight"] = weight
            updated = True
        
        if not updated:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": f"Strategy {strategy_name} not found"}
            )
        
        # Save config file
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Strategy {strategy_name} weight updated to {weight}")
        
        return {
            "success": True,
            "strategy": strategy_name,
            "weight": weight,
        }
    
    except Exception as e:
        logger.error(f"Error updating strategy weight: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.get("/api/risk-profile")
async def get_risk_profile() -> Dict[str, Any]:
    """Get current risk profile configuration"""
    try:
        from utils.config_loader import ConfigLoader
        
        config_loader = ConfigLoader()
        config = config_loader.config
        
        risk_config = config.get("risk", {})
        
        return {
            "success": True,
            "risk_profile": {
                "risk_per_trade_pct": risk_config.get("riskPct", 0.02) * 100,
                "max_daily_loss_pct": risk_config.get("maxDailyLoss", 0.005) * 100,
                "max_positions": risk_config.get("maxPositions", 3),
                "max_exposure_pct": risk_config.get("maxExposure", 0.5) * 100,
            },
        }
    
    except Exception as e:
        logger.error(f"Error getting risk profile: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@router.post("/api/risk-profile")
async def update_risk_profile(risk_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update risk profile configuration.
    
    Args:
        risk_profile: Risk profile data
        
    Returns:
        Success status
    """
    try:
        from utils.config_loader import ConfigLoader
        from pathlib import Path
        
        config_loader = ConfigLoader()
        config_path = Path(config_loader.config_path) if hasattr(config_loader, 'config_path') else Path("config/config.yaml")
        
        # Load config file
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Update risk config
        if "risk" not in config_data:
            config_data["risk"] = {}
        
        if "risk_per_trade_pct" in risk_profile:
            config_data["risk"]["riskPct"] = risk_profile["risk_per_trade_pct"] / 100.0
        if "max_daily_loss_pct" in risk_profile:
            config_data["risk"]["maxDailyLoss"] = risk_profile["max_daily_loss_pct"] / 100.0
        if "max_positions" in risk_profile:
            config_data["risk"]["maxPositions"] = risk_profile["max_positions"]
        if "max_exposure_pct" in risk_profile:
            config_data["risk"]["maxExposure"] = risk_profile["max_exposure_pct"] / 100.0
        
        # Save config file
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info("Risk profile updated")
        
        return {
            "success": True,
            "risk_profile": risk_profile,
        }
    
    except Exception as e:
        logger.error(f"Error updating risk profile: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


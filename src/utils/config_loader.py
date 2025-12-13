"""Configuration Loader"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ConfigLoader:
    """Load and manage configuration from YAML and environment variables"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize config loader"""
        self.config_path = Path(__file__).parent.parent.parent / config_path
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Override with environment variables
        self._apply_env_overrides()
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides - all credentials must come from env vars"""
        # Trading mode
        if os.getenv("TRADING_MODE"):
            self.config["trading"]["mode"] = os.getenv("TRADING_MODE")

        # Bybit credentials (required for live trading)
        if "bybit" not in self.config:
            self.config["bybit"] = {}

        if os.getenv("BYBIT_API_KEY"):
            self.config["bybit"]["apiKey"] = os.getenv("BYBIT_API_KEY")
        if os.getenv("BYBIT_API_SECRET"):
            self.config["bybit"]["apiSecret"] = os.getenv("BYBIT_API_SECRET")
        if os.getenv("BYBIT_TESTNET"):
            self.config["bybit"]["testnet"] = os.getenv("BYBIT_TESTNET").lower() == "true"
        if os.getenv("BYBIT_TESTNET_API_KEY"):
            self.config["bybit"]["testnetApiKey"] = os.getenv("BYBIT_TESTNET_API_KEY")
        if os.getenv("BYBIT_TESTNET_API_SECRET"):
            self.config["bybit"]["testnetApiSecret"] = os.getenv("BYBIT_TESTNET_API_SECRET")

        # Discord alerting configuration
        if os.getenv("DISCORD_ALERTS_ENABLED"):
            if "alerts" not in self.config:
                self.config["alerts"] = {}
            self.config["alerts"]["enabled"] = os.getenv("DISCORD_ALERTS_ENABLED").lower() == "true"

        if os.getenv("DISCORD_WEBHOOK_URL"):
            if "alerts" not in self.config:
                self.config["alerts"] = {}
            self.config["alerts"]["discordWebhook"] = os.getenv("DISCORD_WEBHOOK_URL")

        # Notion integration configuration
        if os.getenv("NOTION_ENABLED"):
            if "notion" not in self.config:
                self.config["notion"] = {}
            self.config["notion"]["enabled"] = os.getenv("NOTION_ENABLED").lower() == "true"

        if os.getenv("NOTION_API_KEY"):
            if "notion" not in self.config:
                self.config["notion"] = {}
            self.config["notion"]["apiKey"] = os.getenv("NOTION_API_KEY")

        if os.getenv("NOTION_DB_SIGNALS"):
            if "notion" not in self.config:
                self.config["notion"] = {}
            if "databases" not in self.config["notion"]:
                self.config["notion"]["databases"] = {}
            self.config["notion"]["databases"]["signals"] = os.getenv("NOTION_DB_SIGNALS")

        if os.getenv("NOTION_DB_EXECUTIONS"):
            if "notion" not in self.config:
                self.config["notion"] = {}
            if "databases" not in self.config["notion"]:
                self.config["notion"]["databases"] = {}
            self.config["notion"]["databases"]["executions"] = os.getenv("NOTION_DB_EXECUTIONS")

        if os.getenv("NOTION_DB_DAILY_STATS"):
            if "notion" not in self.config:
                self.config["notion"] = {}
            if "databases" not in self.config["notion"]:
                self.config["notion"]["databases"] = {}
            self.config["notion"]["databases"]["dailyStats"] = os.getenv("NOTION_DB_DAILY_STATS")

        # Database path configuration
        if os.getenv("DATABASE_PATH"):
            if "ml" not in self.config:
                self.config["ml"] = {}
            if "database" not in self.config["ml"]:
                self.config["ml"]["database"] = {}
            self.config["ml"]["database"]["path"] = os.getenv("DATABASE_PATH")

        # Logging configuration
        if os.getenv("LOG_LEVEL"):
            if "logging" not in self.config:
                self.config["logging"] = {}
            self.config["logging"]["level"] = os.getenv("LOG_LEVEL")

        if os.getenv("LOG_FILE"):
            if "logging" not in self.config:
                self.config["logging"] = {}
            self.config["logging"]["file"] = os.getenv("LOG_FILE")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        """Get config value by key"""
        return self.config[key]
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in config"""
        return key in self.config


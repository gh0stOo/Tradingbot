#!/usr/bin/env python3
"""
Health check script for Docker containers
Used by Docker healthcheck to determine if container is healthy
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_bot_worker_health():
    """Check if bot worker process is healthy"""
    try:
        # Try to import main modules
        from utils.config_loader import ConfigLoader
        from trading.bot import TradingBot
        from data.database import Database
        
        # Check config
        config_loader = ConfigLoader()
        if not config_loader.config:
            print("[FAIL] Config not loaded")
            return False
        
        # Check database
        db_path = config_loader.config.get("ml", {}).get("database", {}).get("path", "data/trading.db")
        if not os.path.exists(db_path):
            print(f"[WARN] Database not found at {db_path}, but this is OK for first run")
        else:
            db = Database(db_path)
            # Try query
            try:
                db.query("SELECT 1")
            except:
                print("[FAIL] Database not responsive")
                return False
        
        print("[OK] Bot worker is healthy")
        return True
        
    except Exception as e:
        print(f"[FAIL] Health check failed: {e}")
        return False

def check_api_server_health():
    """Check if API server is healthy"""
    try:
        import requests
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("[OK] API server is healthy")
            return True
        else:
            print(f"[FAIL] API server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] API server health check failed: {e}")
        return False

if __name__ == "__main__":
    # Determine which check to run based on service
    service = os.getenv("SERVICE", "worker")
    
    if service == "api":
        sys.exit(0 if check_api_server_health() else 1)
    elif service == "worker":
        sys.exit(0 if check_bot_worker_health() else 1)
    else:
        sys.exit(0)

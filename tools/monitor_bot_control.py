#!/usr/bin/env python3
"""Monitor bot_control table in real-time"""

import sqlite3
import time
import os
import sys

db_path = os.getenv("TRADING_DB_PATH", "data/trading.db")

def monitor():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Monitoring bot_control table (Ctrl+C to stop)...")
    print("=" * 80)
    
    try:
        while True:
            cursor.execute("""
                SELECT 
                    id,
                    desired_state,
                    actual_state,
                    datetime(last_heartbeat) as heartbeat,
                    last_error,
                    datetime(updated_at) as updated
                FROM bot_control 
                WHERE id = 1
            """)
            row = cursor.fetchone()
            
            if row:
                print(f"\r[{time.strftime('%H:%M:%S')}] "
                      f"desired={row[1]:8s} | "
                      f"actual={row[2]:8s} | "
                      f"heartbeat={row[3] or 'NULL':19s} | "
                      f"error={row[4] or 'None':20s} | "
                      f"updated={row[5] or 'NULL':19s}", end="", flush=True)
            else:
                print("\r[ERROR] bot_control row not found!", end="", flush=True)
            
            time.sleep(1)
            conn.commit()
    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        conn.close()

if __name__ == "__main__":
    monitor()


#!/bin/bash
set -e

# Docker entrypoint script with better error handling and recovery

SERVICE=${SERVICE:-api}
MAX_RETRIES=${MAX_RETRIES:-3}
RETRY_DELAY=${RETRY_DELAY:-5}

log_info() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $*"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# Trap signals for graceful shutdown
trap 'log_info "Received shutdown signal, exiting gracefully..."; exit 0' SIGTERM SIGINT

log_info "Starting Trading Bot ($SERVICE)..."
log_info "Python version: $(python --version)"
log_info "PYTHONPATH: $PYTHONPATH"

# Create required directories
mkdir -p /app/data /app/logs

# Set permissions
chmod 755 /app/data /app/logs 2>/dev/null || true

if [ "$SERVICE" = "api" ]; then
    log_info "Starting API Server..."
    exec python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
elif [ "$SERVICE" = "worker" ]; then
    log_info "Starting Bot Worker..."
    exec python src/main.py
else
    log_error "Unknown service: $SERVICE"
    exit 1
fi

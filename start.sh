#!/bin/bash
# Cloud Watchdog Service Launcher
# Description: Initializes environment and starts the watchdog service.

set -e

WORK_DIR=$(dirname "$0")
cd "$WORK_DIR"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
    exit 1
}

# Prerequisite checks
command -v python3 >/dev/null 2>&1 || error "Python 3 is required but not installed."
command -v docker >/dev/null 2>&1 || error "Docker is required but not installed."
docker ps >/dev/null 2>&1 || error "Docker permission denied. Ensure user is in 'docker' group."

# Environment setup
mkdir -p logs state

# Dependency check (silent)
if ! python3 -c "import requests, yaml, fastapi, uvicorn" >/dev/null 2>&1; then
    log "Installing dependencies..."
    pip3 install -r requirements.txt >/dev/null 2>&1 || error "Failed to install dependencies."
fi

# Configuration check
if [ ! -f "config/config.yml" ]; then
    error "Configuration file 'config/config.yml' not found."
fi

# Launch service
log "Starting Cloud Watchdog..."
export PYTHONPATH=$PYTHONPATH:.
exec python3 -m watchdog.main "$@"

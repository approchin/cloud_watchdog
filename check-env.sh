#!/bin/bash
# Cloud Watchdog Environment Validator
# Description: Validates system requirements and configuration.

set -e

# Status indicators
PASS="[OK]"
FAIL="[FAIL]"
WARN="[WARN]"

echo "Starting environment validation..."

# 1. System Requirements
echo "Checking system requirements..."

if command -v python3 >/dev/null 2>&1; then
    echo "$PASS Python 3 ($(python3 --version | cut -d' ' -f2))"
else
    echo "$FAIL Python 3 not found"
    exit 1
fi

if command -v docker >/dev/null 2>&1; then
    echo "$PASS Docker Engine"
else
    echo "$FAIL Docker Engine not found"
    exit 1
fi

# 2. Permissions
if docker ps >/dev/null 2>&1; then
    echo "$PASS Docker permissions"
else
    echo "$FAIL Docker permission denied (current user: $USER)"
    exit 1
fi

# 3. Configuration
if [ -f "config/config.yml" ]; then
    echo "$PASS Configuration file found"
else
    echo "$FAIL config/config.yml missing"
    exit 1
fi

# 4. Network Connectivity
echo "Checking network connectivity..."
if curl -s --connect-timeout 5 https://api.deepseek.com >/dev/null 2>&1; then
    echo "$PASS LLM API connectivity"
else
    echo "$WARN LLM API connectivity check failed (may affect decision engine)"
fi

echo "Validation complete."

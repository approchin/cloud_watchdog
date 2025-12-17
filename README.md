# Cloud Watchdog

![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)
![Docker](https://img.shields.io/badge/docker-sdk-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Cloud Watchdog** is an industrial-grade, edge-native container self-healing system designed for high-availability environments. It combines traditional rule-based monitoring with Large Language Model (LLM) decision-making to detect, diagnose, and recover from container failures autonomously.

## Architecture

The system implements an **OODA Loop** (Observe, Orient, Decide, Act) architecture:

1.  **Perception Layer**: Real-time monitoring via Docker Events API and resource polling (CPU/Memory).
2.  **Decision Engine**: Hybrid engine combining static rules (Circuit Breakers) and LLM-based root cause analysis (DeepSeek-V3).
3.  **Execution Layer**: Safe container operations (Restart, Stop, Inspect) with strict permission controls.

## Key Features

*   **Dual-Mode Monitoring**: Event-driven (OOM/Die) + Polling (Resource Usage).
*   **Hybrid Decision Engine**: Fast path for known issues, slow path (LLM) for complex failures.
*   **Adaptive Circuit Breaker**: Prevents restart loops and alert fatigue.
*   **Automated Forensics**: Captures logs, stats, and inspect data *before* recovery actions.
*   **Security First**: Read-only monitoring by default; execution requires explicit whitelist.

## Quick Start

### Prerequisites

*   Linux (Ubuntu 20.04+ recommended)
*   Python 3.10+
*   Docker Engine 20.10+

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/approchin/cloud_watchdog.git
    cd cloud-watchdog
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**
    Copy the example configuration and edit it:
    ```bash
    cp config/config.yml config/config.local.yml
    ```
    *   Set `api_key` for the LLM provider.
    *   Configure `notification` settings (SMTP).

4.  **Run**
    ```bash
    # Start as a background service
    nohup ./start.sh > logs/system.log 2>&1 &
    ```

## Configuration

The system is configured via `config/config.yml`. Key sections:

*   `system`: Log levels and check intervals.
*   `llm`: Provider settings (DeepSeek, OpenAI compatible).
*   `thresholds`: CPU/Memory limits for triggering alerts.
*   `executor`: Allowed actions whitelist (e.g., `RESTART`, `STOP`).

## Project Structure

```
.
├── config/                 # Configuration files
├── docs/                   # Technical documentation
├── watchdog/               # Core logic (Monitor, Evidence, Decision)
├── test-containers/        # Chaos engineering test cases
├── start.sh                # Startup script
└── requirements.txt        # Python dependencies
```

## License

MIT License. See [LICENSE](LICENSE) for details.

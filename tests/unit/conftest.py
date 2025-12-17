#!/usr/bin/env python3
"""
pytest 配置文件

提供共享的 fixtures 和配置
"""
import os
import sys
import pytest
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(autouse=True)
def reset_config():
    """每个测试前重置配置"""
    import watchdog.config as config_module
    config_module._config = None
    yield
    config_module._config = None


@pytest.fixture(autouse=True)
def reset_task_queue():
    """每个测试前重置任务队列"""
    import watchdog.agent as agent_module
    if agent_module._task_queue is not None:
        agent_module._task_queue.stop()
        agent_module._task_queue = None
    yield
    if agent_module._task_queue is not None:
        agent_module._task_queue.stop()
        agent_module._task_queue = None


@pytest.fixture
def sample_evidence():
    """示例 evidence 数据"""
    from datetime import datetime
    return {
        "event_id": "evt_test_001",
        "timestamp": datetime.now().isoformat(),
        "container": {
            "id": "abc123",
            "name": "test-container",
            "image": "test:latest",
            "status": "running",
            "running": True,
            "exit_code": 0,
            "oom_killed": False
        },
        "evidence": {
            "cpu_percent": "50.0%",
            "memory_percent": "30.0%",
            "logs_tail": "Application running normally..."
        },
        "fault_type": "UNKNOWN",
        "thresholds": {
            "cpu_warning": 70,
            "cpu_critical": 90,
            "memory_warning": 70,
            "memory_critical": 85
        }
    }


@pytest.fixture
def cpu_high_evidence(sample_evidence):
    """CPU 高负载 evidence"""
    sample_evidence["evidence"]["cpu_percent"] = "95.0%"
    sample_evidence["fault_type"] = "CPU_HIGH"
    return sample_evidence


@pytest.fixture
def crash_evidence(sample_evidence):
    """崩溃 evidence"""
    sample_evidence["container"]["status"] = "exited"
    sample_evidence["container"]["running"] = False
    sample_evidence["container"]["exit_code"] = 1
    sample_evidence["evidence"]["exit_code"] = 1
    sample_evidence["fault_type"] = "PROCESS_CRASH"
    return sample_evidence


@pytest.fixture
def oom_evidence(sample_evidence):
    """OOM evidence"""
    sample_evidence["container"]["oom_killed"] = True
    sample_evidence["evidence"]["oom_killed"] = True
    sample_evidence["fault_type"] = "OOM_KILLED"
    return sample_evidence

#!/usr/bin/env python3
"""
单元6: Monitor集成测试 (_report_issue)

测试内容：
- _report_issue 触发诊断
- 熔断机制
- 去重逻辑
- 证据收集集成
"""
import os
import sys
import time
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.monitor import ContainerMonitor
from watchdog.config import init_config


class TestReportIssue:
    """_report_issue 测试"""
    
    def setup_method(self):
        init_config()
    
    @patch('watchdog.agent.run_diagnosis')
    def test_report_issue_collects_evidence(self, mock_diagnosis):
        """测试上报时收集证据"""
        monitor = ContainerMonitor()
        # 添加到监控列表
        monitor._monitored_names.add("test-container")
        
        # 直接测试 _report_issue 调用了 run_diagnosis
        monitor._report_issue("test-container", "CPU_HIGH")
        
        # 验证 run_diagnosis 被调用
        mock_diagnosis.assert_called_once()
    
    @patch('watchdog.agent.run_diagnosis')
    def test_report_issue_triggers_diagnosis(self, mock_diagnosis):
        """测试上报触发诊断"""
        monitor = ContainerMonitor()
        monitor._monitored_names.add("test-container")
        
        monitor._report_issue("test-container", "CPU_HIGH")
        
        mock_diagnosis.assert_called_once()
        # 验证异步模式
        call_args = mock_diagnosis.call_args
        assert call_args[1]['async_mode'] == True


class TestCircuitBreaker:
    """熔断机制测试"""
    
    def setup_method(self):
        init_config()
    
    def test_should_report_first_time(self):
        """测试首次上报允许"""
        monitor = ContainerMonitor()
        result = monitor._should_report("new-container", "CPU_HIGH")
        assert result == True
    
    def test_circuit_breaker_triggers(self):
        """测试熔断触发"""
        monitor = ContainerMonitor()
        container = "frequent-container"
        
        # 模拟多次上报（需要超过阈值）
        max_attempts = monitor.config.circuit_breaker.max_restart_attempts
        for _ in range(max_attempts):
            monitor._record_report(container)
        
        # 清除最后上报时间以绕过去重检查
        monitor.last_report_time.pop(container, None)
        
        # 下一次应该被熔断
        result = monitor._should_report(container, "CPU_HIGH")
        assert result == False
        assert container in monitor.circuit_breaker_until
    
    def test_circuit_breaker_cooldown(self):
        """测试熔断冷却"""
        monitor = ContainerMonitor()
        container = "cooldown-container"
        
        # 设置过期的熔断时间
        monitor.circuit_breaker_until[container] = datetime.now() - timedelta(seconds=1)
        
        result = monitor._should_report(container, "CPU_HIGH")
        assert result == True
        assert container not in monitor.circuit_breaker_until


class TestDeduplication:
    """去重逻辑测试"""
    
    def setup_method(self):
        init_config()
    
    def test_dedup_blocks_rapid_reports(self):
        """测试快速重复上报被阻止"""
        monitor = ContainerMonitor()
        container = "rapid-container"
        
        # 第一次上报
        monitor._record_report(container)
        
        # 立即再次尝试上报应该被阻止
        result = monitor._should_report(container, "CPU_HIGH")
        assert result == False
    
    def test_dedup_allows_after_cooldown(self):
        """测试冷却后允许上报"""
        monitor = ContainerMonitor()
        container = "cooldown-container"
        
        # 设置过期的上报时间
        cooldown = monitor.config.circuit_breaker.cooldown_seconds
        monitor.last_report_time[container] = datetime.now() - timedelta(seconds=cooldown + 1)
        
        result = monitor._should_report(container, "CPU_HIGH")
        assert result == True


class TestRecordReport:
    """上报记录测试"""
    
    def setup_method(self):
        init_config()
    
    def test_record_updates_last_time(self):
        """测试记录更新最后上报时间"""
        monitor = ContainerMonitor()
        container = "test-container"
        
        before = datetime.now()
        monitor._record_report(container)
        after = datetime.now()
        
        assert container in monitor.last_report_time
        assert before <= monitor.last_report_time[container] <= after
    
    def test_record_appends_history(self):
        """测试记录追加历史"""
        monitor = ContainerMonitor()
        container = "test-container"
        
        monitor._record_report(container)
        monitor._record_report(container)
        
        assert len(monitor.report_history[container]) == 2


class TestIsMonitored:
    """监控列表检查测试"""
    
    def setup_method(self):
        init_config()
    
    def test_monitored_container(self):
        """测试监控中的容器"""
        monitor = ContainerMonitor()
        assert monitor._is_monitored("cpu-stress") == True
    
    def test_unmonitored_container(self):
        """测试不在监控列表的容器"""
        monitor = ContainerMonitor()
        assert monitor._is_monitored("random-container") == False
    
    def test_monitored_set_performance(self):
        """测试监控集合 O(1) 查询"""
        monitor = ContainerMonitor()
        # 使用 set 实现的 _monitored_names 应该是 O(1)
        assert isinstance(monitor._monitored_names, set)


class TestMonitorLifecycle:
    """Monitor 生命周期测试"""
    
    def setup_method(self):
        init_config()
    
    def test_monitor_initialization(self):
        """测试 Monitor 初始化"""
        monitor = ContainerMonitor()
        assert monitor.config is not None
        assert monitor.stop_event is not None
        assert len(monitor.threads) == 0
    
    @patch('watchdog.monitor.ContainerMonitor._polling_loop')
    @patch('watchdog.monitor.ContainerMonitor._events_loop')
    def test_monitor_start(self, mock_events, mock_polling):
        """测试 Monitor 启动"""
        monitor = ContainerMonitor()
        monitor.start()
        
        assert len(monitor.threads) == 2
        
        monitor.stop()
    
    def test_monitor_stop(self):
        """测试 Monitor 停止"""
        monitor = ContainerMonitor()
        monitor.stop_event.clear()
        monitor.stop()
        
        assert monitor.stop_event.is_set()


class TestDockerEventHandling:
    """Docker 事件处理测试"""
    
    def setup_method(self):
        init_config()
    
    @patch('watchdog.monitor.ContainerMonitor._report_issue')
    def test_handle_oom_event(self, mock_report):
        """测试 OOM 事件处理"""
        monitor = ContainerMonitor()
        # 添加测试容器到监控列表
        monitor._monitored_names.add("oom-container")
        
        event = {
            "Action": "oom",
            "Actor": {
                "Attributes": {"name": "oom-container"}
            }
        }
        
        monitor._handle_docker_event(event)
        
        mock_report.assert_called_once_with("oom-container", "OOM_KILLED")
    
    @patch('watchdog.monitor.ContainerMonitor._report_issue')
    def test_handle_die_event(self, mock_report):
        """测试 die 事件处理"""
        monitor = ContainerMonitor()
        monitor._monitored_names.add("crash-container")
        
        event = {
            "Action": "die",
            "Actor": {
                "Attributes": {"name": "crash-container", "exitCode": "1"}
            }
        }
        
        monitor._handle_docker_event(event)
        
        mock_report.assert_called_once_with("crash-container", "PROCESS_CRASH")
    
    @patch('watchdog.monitor.ContainerMonitor._report_issue')
    def test_handle_die_event_oom(self, mock_report):
        """测试 die 事件 OOM (exit code 137)"""
        monitor = ContainerMonitor()
        monitor._monitored_names.add("oom-container")
        
        event = {
            "Action": "die",
            "Actor": {
                "Attributes": {"name": "oom-container", "exitCode": "137"}
            }
        }
        
        monitor._handle_docker_event(event)
        
        mock_report.assert_called_once_with("oom-container", "OOM_KILLED")
    
    @patch('watchdog.monitor.ContainerMonitor._report_issue')
    def test_ignore_unmonitored_container(self, mock_report):
        """测试忽略未监控的容器"""
        monitor = ContainerMonitor()
        
        event = {
            "Action": "die",
            "Actor": {
                "Attributes": {"name": "unmonitored-container"}
            }
        }
        
        monitor._handle_docker_event(event)
        
        mock_report.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

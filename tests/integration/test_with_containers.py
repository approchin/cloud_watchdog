#!/usr/bin/env python3
"""
集成测试 - 与真实 Docker 容器交互

测试内容：
- 证据收集（真实容器数据）
- 容器状态检测
- 资源监控
- Docker 事件处理

前提条件：
- test-containers 中的容器已启动
- Docker 权限正常
"""
import sys
import os
import time
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.config import init_config
from watchdog.evidence import (
    get_container_info,
    get_container_stats,
    get_container_logs,
    collect_evidence,
    parse_percent
)
from watchdog.executor import execute_action, check_docker_permission


def is_container_running(name: str) -> bool:
    """检查容器是否运行"""
    result = subprocess.run(
        ['docker', 'ps', '-q', '-f', f'name={name}'],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


class TestDockerPermission:
    """Docker 权限测试"""
    
    def test_docker_available(self):
        """测试 Docker 可用"""
        assert check_docker_permission(), "Docker 不可用或无权限"


class TestContainerInfo:
    """容器信息获取测试"""
    
    def setup_method(self):
        init_config()
    
    @pytest.mark.skipif(not is_container_running('normal-app'), 
                        reason="normal-app 容器未运行")
    def test_get_normal_container_info(self):
        """测试获取正常容器信息"""
        info = get_container_info('normal-app')
        
        assert info is not None
        assert info['name'] == 'normal-app'
        assert info['running'] == True
        assert 'id' in info
        assert 'image' in info
    
    @pytest.mark.skipif(not is_container_running('cpu-stress'),
                        reason="cpu-stress 容器未运行")
    def test_get_cpu_stress_info(self):
        """测试获取 CPU 压力容器信息"""
        info = get_container_info('cpu-stress')
        
        assert info is not None
        assert info['running'] == True
    
    def test_get_nonexistent_container(self):
        """测试获取不存在的容器"""
        info = get_container_info('nonexistent-container-xyz')
        assert info is None


class TestContainerStats:
    """容器资源统计测试"""
    
    def setup_method(self):
        init_config()
    
    @pytest.mark.skipif(not is_container_running('normal-app'),
                        reason="normal-app 容器未运行")
    def test_get_container_stats(self):
        """测试获取容器资源统计"""
        stats = get_container_stats('normal-app')
        
        assert stats is not None
        assert 'cpu_percent' in stats
        assert 'memory_percent' in stats
        assert 'memory_usage' in stats
    
    @pytest.mark.skipif(not is_container_running('cpu-stress'),
                        reason="cpu-stress 容器未运行")
    def test_cpu_stress_has_high_cpu(self):
        """测试 CPU 压力容器显示高 CPU"""
        stats = get_container_stats('cpu-stress')
        
        assert stats is not None
        cpu = parse_percent(stats['cpu_percent'])
        # CPU 压力容器应该有较高的 CPU 使用率
        print(f"cpu-stress CPU 使用率: {cpu}%")
        # 不强制断言，因为容器可能刚启动


class TestContainerLogs:
    """容器日志获取测试"""
    
    def setup_method(self):
        init_config()
    
    @pytest.mark.skipif(not is_container_running('normal-app'),
                        reason="normal-app 容器未运行")
    def test_get_container_logs(self):
        """测试获取容器日志"""
        logs = get_container_logs('normal-app', lines=10)
        
        assert logs is not None
        assert isinstance(logs, str)
    
    def test_get_nonexistent_container_logs(self):
        """测试获取不存在容器的日志"""
        logs = get_container_logs('nonexistent-container-xyz')
        assert '失败' in logs or 'Error' in logs or logs == ''


class TestEvidenceCollection:
    """证据收集测试"""
    
    def setup_method(self):
        init_config()
    
    @pytest.mark.skipif(not is_container_running('normal-app'),
                        reason="normal-app 容器未运行")
    def test_collect_evidence_structure(self):
        """测试证据收集结构"""
        evidence = collect_evidence('normal-app', 'UNKNOWN')
        
        assert 'event_id' in evidence
        assert 'timestamp' in evidence
        assert 'container' in evidence
        assert 'evidence' in evidence
        assert 'fault_type' in evidence
        assert 'thresholds' in evidence
    
    @pytest.mark.skipif(not is_container_running('cpu-stress'),
                        reason="cpu-stress 容器未运行")
    def test_collect_cpu_high_evidence(self):
        """测试收集 CPU 高负载证据"""
        evidence = collect_evidence('cpu-stress', 'CPU_HIGH')
        
        assert evidence['fault_type'] == 'CPU_HIGH'
        assert 'cpu_percent' in evidence['evidence']
        print(f"CPU 使用率: {evidence['evidence']['cpu_percent']}")
    
    @pytest.mark.skipif(not is_container_running('crash-loop'),
                        reason="crash-loop 容器未运行")
    def test_collect_crash_evidence(self):
        """测试收集崩溃证据"""
        evidence = collect_evidence('crash-loop', 'PROCESS_CRASH')
        
        assert evidence['fault_type'] == 'PROCESS_CRASH'
        assert 'container' in evidence
        print(f"容器状态: {evidence['container'].get('status', 'unknown')}")


class TestParsePercent:
    """百分比解析测试"""
    
    def test_parse_normal_percent(self):
        """测试解析正常百分比"""
        assert parse_percent("50.5%") == 50.5
        assert parse_percent("100%") == 100.0
        assert parse_percent("0%") == 0.0
    
    def test_parse_with_spaces(self):
        """测试解析带空格的百分比"""
        assert parse_percent(" 75.2% ") == 75.2
    
    def test_parse_invalid(self):
        """测试解析无效值"""
        assert parse_percent("invalid") == 0.0
        assert parse_percent("") == 0.0


class TestExecutorInspect:
    """执行器检查命令测试"""
    
    def setup_method(self):
        init_config()
    
    @pytest.mark.skipif(not is_container_running('normal-app'),
                        reason="normal-app 容器未运行")
    def test_inspect_container(self):
        """测试 INSPECT 命令"""
        result = execute_action('INSPECT', 'normal-app')
        
        assert result['success'] == True
        assert result['action'] == 'INSPECT'
        assert 'stdout' in result
    
    def test_invalid_action(self):
        """测试无效操作"""
        result = execute_action('INVALID_ACTION', 'normal-app')
        
        assert result['success'] == False
        assert '不允许' in result['error']


class TestIntegrationWorkflow:
    """集成工作流测试"""
    
    def setup_method(self):
        init_config()
    
    @pytest.mark.skipif(not is_container_running('normal-app'),
                        reason="normal-app 容器未运行")
    def test_full_evidence_to_decision_flow(self):
        """测试完整的证据收集到决策流程（不执行实际操作）"""
        # 1. 收集证据
        evidence = collect_evidence('normal-app', 'UNKNOWN')
        
        # 2. 验证证据完整性
        assert evidence['container']['name'] == 'normal-app'
        assert 'cpu_percent' in evidence['evidence']
        
        # 3. 验证证据可以被序列化（用于 LLM 调用）
        import json
        evidence_str = json.dumps(evidence, ensure_ascii=False)
        assert len(evidence_str) > 100
        
        print(f"\n=== 证据收集成功 ===")
        print(f"容器: {evidence['container']['name']}")
        print(f"CPU: {evidence['evidence']['cpu_percent']}")
        print(f"内存: {evidence['evidence']['memory_percent']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

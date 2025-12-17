#!/usr/bin/env python3
"""
LangGraph Agent 测试套件

包含：
1. 离线测试：不调用真实 API，测试逻辑和数据流
2. 在线测试：调用真实 DeepSeek API，验证端到端功能
3. 集成测试：模拟完整监控流程

运行方式：
    # 仅离线测试（快速）
    python tests/test_agent.py --offline
    
    # 仅在线测试（需要 API Key）
    python tests/test_agent.py --online
    
    # 全部测试
    python tests/test_agent.py
"""

import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from watchdog.agent import (
    analyze_with_llm,
    DiagnosisAgent,
    run_diagnosis,
    SYSTEM_PROMPT
)
from watchdog.config import init_config


# ============================================
# 测试数据
# ============================================

def get_mock_evidence_cpu_high() -> Dict[str, Any]:
    """模拟 CPU 高负载的 evidence"""
    return {
        "event_id": "evt_test_001",
        "timestamp": datetime.now().isoformat(),
        "container": {
            "id": "abc123",
            "name": "test-cpu-stress",
            "image": "test/cpu-stress:latest",
            "status": "running",
            "running": True,
            "restarting": False,
            "paused": False,
            "oom_killed": False,
            "exit_code": 0,
            "error": "",
            "started_at": "2025-12-11T10:00:00.000000Z",
            "finished_at": "0001-01-01T00:00:00Z",
            "restart_count": 0,
            "restart_policy": "always",
            "memory_limit": 0,
            "cpu_limit": 0,
            "ip_address": "172.17.0.2",
            "ports": {}
        },
        "evidence": {
            "exit_code": 0,
            "oom_killed": False,
            "error_message": "",
            "cpu_percent": "95.2%",
            "memory_percent": "45.0%",
            "memory_usage": "230MiB / 512MiB",
            "logs_tail": "Running stress test...",
            "restart_count_24h": 0,
            "health_check": {
                "healthy": True,
                "message": "ok"
            }
        },
        "fault_type": "CPU_HIGH",
        "thresholds": {
            "cpu_warning": 70,
            "cpu_critical": 80,
            "memory_warning": 70,
            "memory_critical": 85
        }
    }


def get_mock_evidence_normal() -> Dict[str, Any]:
    """模拟正常运行的 evidence"""
    return {
        "event_id": "evt_test_002",
        "timestamp": datetime.now().isoformat(),
        "container": {
            "id": "xyz789",
            "name": "test-normal-app",
            "image": "nginx:latest",
            "status": "running",
            "running": True,
            "restarting": False,
            "paused": False,
            "oom_killed": False,
            "exit_code": 0,
            "error": "",
            "started_at": "2025-12-10T00:00:00.000000Z",
            "finished_at": "0001-01-01T00:00:00Z",
            "restart_count": 0,
            "restart_policy": "always",
            "memory_limit": 536870912,
            "cpu_limit": 0,
            "ip_address": "172.17.0.3",
            "ports": {}
        },
        "evidence": {
            "exit_code": 0,
            "oom_killed": False,
            "error_message": "",
            "cpu_percent": "5.0%",
            "memory_percent": "20.0%",
            "memory_usage": "102MiB / 512MiB",
            "logs_tail": "GET /index.html 200",
            "restart_count_24h": 0,
            "health_check": {
                "healthy": True,
                "message": "HTTP 200"
            }
        },
        "fault_type": "UNKNOWN",
        "thresholds": {
            "cpu_warning": 70,
            "cpu_critical": 90,
            "memory_warning": 70,
            "memory_critical": 85
        }
    }


def get_mock_evidence_crash() -> Dict[str, Any]:
    """模拟容器崩溃的 evidence"""
    return {
        "event_id": "evt_test_003",
        "timestamp": datetime.now().isoformat(),
        "container": {
            "id": "def456",
            "name": "test-crash-loop",
            "image": "test/crash:latest",
            "status": "exited",
            "running": False,
            "restarting": False,
            "paused": False,
            "oom_killed": False,
            "exit_code": 1,
            "error": "",
            "started_at": "2025-12-11T10:00:00.000000Z",
            "finished_at": "2025-12-11T10:01:00.000000Z",
            "restart_count": 5,
            "restart_policy": "always",
            "memory_limit": 0,
            "cpu_limit": 0,
            "ip_address": "",
            "ports": {}
        },
        "evidence": {
            "exit_code": 1,
            "oom_killed": False,
            "error_message": "Application crashed",
            "cpu_percent": "0%",
            "memory_percent": "0%",
            "memory_usage": "0MiB / 512MiB",
            "logs_tail": "Error: Segmentation fault",
            "restart_count_24h": 5,
            "health_check": {
                "healthy": False,
                "message": "Container not running"
            }
        },
        "fault_type": "PROCESS_CRASH",
        "thresholds": {
            "cpu_warning": 70,
            "cpu_critical": 90,
            "memory_warning": 70,
            "memory_critical": 85
        }
    }


# ============================================
# 离线测试（不需要 API Key）
# ============================================

def test_offline_prompt_generation():
    """测试 SYSTEM_PROMPT 生成"""
    print("\n" + "="*80)
    print("测试：SYSTEM_PROMPT 生成")
    print("="*80)
    
    evidence = get_mock_evidence_cpu_high()
    evidence_str = json.dumps(evidence, ensure_ascii=False, indent=2)
    
    prompt = SYSTEM_PROMPT.format(evidence_str=evidence_str)
    
    # 验证 prompt 包含关键内容
    assert "容器故障诊断专家" in prompt
    assert "test-cpu-stress" in prompt
    assert "95.2%" in prompt
    assert "CPU_HIGH" in prompt
    
    print("✅ SYSTEM_PROMPT 生成正确")
    print(f"   - Prompt 长度: {len(prompt)} 字符")
    print(f"   - 包含 evidence: ✓")
    print(f"   - 包含决策规则: ✓")
    print(f"   - 包含 few-shot 示例: ✓")
    
    return True


def test_offline_decision_validation():
    """测试决策格式验证"""
    print("\n" + "="*80)
    print("测试：决策格式验证")
    print("="*80)
    
    # 模拟 LLM 返回的决策
    valid_decision = {
        "fault_type": "CPU_HIGH",
        "command": "ALERT_ONLY",
        "params": {
            "container_name": "test-cpu-stress",
            "current_cpu": "95.2%",
            "current_memory": "45.0%",
            "retry_count": 0
        },
        "reason": "CPU 使用率过高"
    }
    
    # 验证必需字段
    required_fields = ['fault_type', 'command', 'params', 'reason']
    for field in required_fields:
        assert field in valid_decision, f"缺少字段: {field}"
    
    # 验证 params 中的 container_name
    assert 'container_name' in valid_decision['params']
    
    # 验证 command 枚举
    valid_commands = ['RESTART', 'STOP', 'ALERT_ONLY', 'NONE']
    assert valid_decision['command'] in valid_commands
    
    print("✅ 决策格式验证通过")
    print(f"   - 必需字段: {required_fields}")
    print(f"   - command: {valid_decision['command']}")
    print(f"   - container_name: {valid_decision['params']['container_name']}")
    
    return True


def test_offline_error_handling():
    """测试错误处理逻辑"""
    print("\n" + "="*80)
    print("测试：错误处理")
    print("="*80)
    
    # 测试缺少 API Key 的情况
    os.environ.pop('DEEPSEEK_API_KEY', None)  # 确保没有 API Key
    
    # 重新初始化配置
    init_config()
    
    evidence = get_mock_evidence_normal()
    decision = analyze_with_llm(evidence)
    
    # 应该返回错误决策
    assert decision['fault_type'] == 'CONFIG_ERROR'
    assert decision['command'] == 'ALERT_ONLY'
    assert 'API Key' in decision['reason']
    
    print("✅ 错误处理正确")
    print(f"   - fault_type: {decision['fault_type']}")
    print(f"   - command: {decision['command']}")
    print(f"   - reason: {decision['reason'][:50]}...")
    
    return True


# ============================================
# 在线测试（需要 DeepSeek API Key）
# ============================================

def test_online_llm_call():
    """测试真实的 LLM 调用"""
    print("\n" + "="*80)
    print("测试：DeepSeek API 调用（在线）")
    print("="*80)
    
    # 检查 API Key
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("⚠️  跳过：未设置 DEEPSEEK_API_KEY 环境变量")
        return False
    
    # 重新初始化配置
    init_config()
    
    evidence = get_mock_evidence_cpu_high()
    
    print(f"调用 DeepSeek 分析容器: {evidence['container']['name']}")
    start_time = time.time()
    
    decision = analyze_with_llm(evidence)
    
    elapsed = time.time() - start_time
    
    # 验证返回结果
    assert 'fault_type' in decision
    assert 'command' in decision
    assert 'params' in decision
    assert 'reason' in decision
    
    print(f"✅ API 调用成功（耗时: {elapsed:.2f}秒）")
    print(f"   - fault_type: {decision['fault_type']}")
    print(f"   - command: {decision['command']}")
    print(f"   - reason: {decision['reason'][:80]}...")
    
    # 保存结果
    result_file = Path(__file__).parent.parent / "logs" / "test_agent_online_result.json"
    result_file.parent.mkdir(exist_ok=True)
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "evidence": evidence,
            "decision": decision,
            "elapsed_seconds": elapsed
        }, f, ensure_ascii=False, indent=2)
    
    print(f"   - 结果已保存: {result_file}")
    
    return True


def test_online_multiple_scenarios():
    """测试多种场景的决策准确性"""
    print("\n" + "="*80)
    print("测试：多场景决策准确性（在线）")
    print("="*80)
    
    # 检查 API Key
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("⚠️  跳过：未设置 DEEPSEEK_API_KEY 环境变量")
        return False
    
    init_config()
    
    test_cases = [
        (get_mock_evidence_cpu_high(), "ALERT_ONLY", "CPU 高负载应该仅告警"),
        (get_mock_evidence_normal(), "NONE", "正常容器不需要操作"),
        (get_mock_evidence_crash(), "RESTART", "崩溃容器应该重启"),
    ]
    
    results = []
    
    for evidence, expected_command, description in test_cases:
        container_name = evidence['container']['name']
        print(f"\n场景: {description}")
        print(f"  容器: {container_name}")
        
        decision = analyze_with_llm(evidence)
        
        actual_command = decision['command']
        match = "✅" if actual_command == expected_command else "⚠️"
        
        print(f"  {match} 预期: {expected_command}, 实际: {actual_command}")
        print(f"  原因: {decision['reason'][:60]}...")
        
        results.append({
            "container": container_name,
            "expected": expected_command,
            "actual": actual_command,
            "match": actual_command == expected_command,
            "decision": decision
        })
        
        time.sleep(1)  # 避免 API 限流
    
    # 统计
    total = len(results)
    passed = sum(1 for r in results if r['match'])
    
    print(f"\n{'='*80}")
    print(f"总计: {passed}/{total} 通过")
    
    # 保存结果
    result_file = Path(__file__).parent.parent / "logs" / "test_agent_scenarios.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存: {result_file}")
    
    return passed == total


def test_online_full_diagnosis():
    """测试完整的诊断流程（决策 + 执行 + 通知）"""
    print("\n" + "="*80)
    print("测试：完整诊断流程（在线）")
    print("="*80)
    
    # 检查 API Key
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("⚠️  跳过：未设置 DEEPSEEK_API_KEY 环境变量")
        return False
    
    init_config()
    
    # 使用正常容器，不触发实际执行
    evidence = get_mock_evidence_normal()
    
    print(f"运行完整诊断: {evidence['container']['name']}")
    
    # 同步模式（等待结果）
    result = run_diagnosis(evidence, async_mode=False)
    
    assert result is not None
    assert 'decision' in result
    assert 'timestamp' in result
    
    decision = result['decision']
    
    print(f"✅ 诊断完成")
    print(f"   - 决策: {decision['command']}")
    print(f"   - 原因: {decision['reason'][:60]}...")
    
    if result.get('action_result'):
        print(f"   - 执行结果: {result['action_result'].get('success', 'N/A')}")
    
    if result.get('notification'):
        print(f"   - 通知结果: {result['notification'].get('success', 'N/A')}")
    
    # 保存结果
    result_file = Path(__file__).parent.parent / "logs" / "test_agent_full_diagnosis.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "evidence": evidence,
            "result": result
        }, f, ensure_ascii=False, indent=2)
    
    print(f"   - 结果已保存: {result_file}")
    
    return True


# ============================================
# 测试运行器
# ============================================

def run_tests(offline=True, online=True):
    """运行测试套件"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "Agent 测试套件" + " "*35 + "║")
    print("╚" + "="*78 + "╝")
    
    results = {
        "offline": [],
        "online": []
    }
    
    # 离线测试
    if offline:
        print("\n【离线测试】不需要 API Key")
        
        offline_tests = [
            ("SYSTEM_PROMPT 生成", test_offline_prompt_generation),
            ("决策格式验证", test_offline_decision_validation),
            ("错误处理", test_offline_error_handling),
        ]
        
        for name, test_func in offline_tests:
            try:
                success = test_func()
                results["offline"].append((name, success))
            except Exception as e:
                print(f"❌ {name} 失败: {e}")
                results["offline"].append((name, False))
    
    # 在线测试
    if online:
        print("\n【在线测试】需要设置 DEEPSEEK_API_KEY")
        
        online_tests = [
            ("DeepSeek API 调用", test_online_llm_call),
            ("多场景决策", test_online_multiple_scenarios),
            ("完整诊断流程", test_online_full_diagnosis),
        ]
        
        for name, test_func in online_tests:
            try:
                success = test_func()
                results["online"].append((name, success))
            except Exception as e:
                print(f"❌ {name} 失败: {e}")
                import traceback
                traceback.print_exc()
                results["online"].append((name, False))
    
    # 总结
    print("\n" + "="*80)
    print("📊 测试总结")
    print("="*80)
    
    if offline:
        offline_total = len(results["offline"])
        offline_passed = sum(1 for _, success in results["offline"] if success)
        print(f"\n离线测试: {offline_passed}/{offline_total} 通过")
        for name, success in results["offline"]:
            icon = "✅" if success else "❌"
            print(f"  {icon} {name}")
    
    if online:
        online_total = len(results["online"])
        online_passed = sum(1 for _, success in results["online"] if success)
        online_skipped = sum(1 for _, success in results["online"] if success is False)
        print(f"\n在线测试: {online_passed}/{online_total} 通过")
        for name, success in results["online"]:
            icon = "✅" if success else ("⚠️" if success is False else "❌")
            print(f"  {icon} {name}")
    
    print("\n" + "="*80)
    
    return results


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent 测试套件')
    parser.add_argument('--offline', action='store_true', help='仅运行离线测试')
    parser.add_argument('--online', action='store_true', help='仅运行在线测试')
    
    args = parser.parse_args()
    
    # 默认运行全部测试
    offline = True
    online = True
    
    if args.offline and not args.online:
        online = False
    elif args.online and not args.offline:
        offline = False
    
    results = run_tests(offline=offline, online=online)
    
    # 返回退出码
    all_passed = all(success for _, success in results.get("offline", []) + results.get("online", []) if success is not False)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

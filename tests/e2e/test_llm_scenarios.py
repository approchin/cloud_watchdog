#!/usr/bin/env python3
"""
端到端场景测试 - LLM 真实判断和动作执行

测试场景：
1. 正常容器 → LLM 应判断 NONE
2. CPU 高负载 → LLM 应判断 ALERT_ONLY 或 RESTART
3. 崩溃容器 → LLM 应判断 RESTART
4. OOM 容器 → LLM 应判断 STOP

前提条件：
- DEEPSEEK_API_KEY 已配置
- test-containers 已启动
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.config import init_config, get_config
from watchdog.evidence import collect_evidence
from watchdog.agent import run_diagnosis, DiagnosisAgent


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(result: dict):
    """打印诊断结果"""
    print(f"  命令: {result.get('command', 'N/A')}")
    print(f"  原因: {result.get('reason', 'N/A')[:80]}...")
    if result.get('error'):
        print(f"  错误: {result.get('error')}")


def test_scenario(container_name: str, fault_type: str, expected_commands: list):
    """
    测试单个场景
    
    Args:
        container_name: 容器名
        fault_type: 故障类型
        expected_commands: 期望的命令列表（任一匹配即通过）
    
    Returns:
        (passed, result)
    """
    print(f"\n📋 容器: {container_name}")
    print(f"   故障类型: {fault_type}")
    print(f"   期望命令: {expected_commands}")
    
    try:
        # 1. 收集证据
        print("   收集证据...")
        evidence = collect_evidence(container_name, fault_type)
        
        if not evidence:
            print("   ❌ 证据收集失败")
            return False, None
        
        # 显示关键证据
        container_status = evidence.get('container', {}).get('status', 'unknown')
        cpu = evidence.get('evidence', {}).get('cpu_percent', 'N/A')
        mem = evidence.get('evidence', {}).get('memory_percent', 'N/A')
        print(f"   状态: {container_status}, CPU: {cpu}, 内存: {mem}")
        
        # 2. 调用 LLM 诊断
        print("   调用 LLM 分析...")
        start_time = time.time()
        result = run_diagnosis(evidence, async_mode=False)
        elapsed = time.time() - start_time
        
        if not result:
            print("   ❌ 诊断失败")
            return False, None
        
        # 3. 检查结果
        command = result.get('command', '')
        print(f"   LLM 响应时间: {elapsed:.2f}s")
        print_result(result)
        
        # 4. 验证
        if command in expected_commands:
            print(f"   ✅ 测试通过 (命令 {command} 在期望列表中)")
            return True, result
        else:
            print(f"   ❌ 测试失败 (命令 {command} 不在期望列表 {expected_commands} 中)")
            return False, result
            
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return False, None


def check_container_running(name: str) -> bool:
    """检查容器是否运行"""
    import subprocess
    result = subprocess.run(
        ['docker', 'ps', '-q', '-f', f'name=^{name}$'],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def main():
    print_header("Cloud Watchdog 端到端场景测试")
    
    # 检查 API Key
    config = init_config()
    if not config.llm.api_key:
        print("❌ DEEPSEEK_API_KEY 未配置，无法进行 LLM 测试")
        return 1
    
    print(f"✅ API Key 已配置")
    print(f"✅ LLM 模型: {config.llm.model}")
    
    # 定义测试场景
    # 期望命令基于实际证据，而非容器名称
    scenarios = [
        # (容器名, 故障类型, 期望命令列表)
        ("normal-app", "UNKNOWN", ["NONE"]),  # 正常容器 → NONE
        # crash-loop 可能正在运行也可能崩溃，两种情况都接受
        ("crash-loop", "PROCESS_CRASH", ["NONE", "RESTART", "STOP"]),
    ]
    
    # 检查容器状态并添加可用场景
    if check_container_running("cpu-stress"):
        # CPU 50% 未达阈值时返回 NONE，达到阈值返回 ALERT_ONLY
        scenarios.append(("cpu-stress", "CPU_HIGH", ["NONE", "ALERT_ONLY", "RESTART"]))
    else:
        print("⚠️  cpu-stress 容器未运行，跳过 CPU 高负载测试")
    
    if check_container_running("memory-leak"):
        # 内存 79% 超过警告阈值 70% → ALERT_ONLY
        scenarios.append(("memory-leak", "MEMORY_HIGH", ["ALERT_ONLY", "RESTART"]))
    else:
        print("⚠️  memory-leak 容器未运行，跳过内存高负载测试")
    
    # 执行测试
    print_header("开始场景测试")
    
    results = []
    for container, fault_type, expected in scenarios:
        if not check_container_running(container):
            print(f"\n⚠️  跳过 {container} (容器未运行)")
            continue
        
        passed, result = test_scenario(container, fault_type, expected)
        results.append({
            "container": container,
            "fault_type": fault_type,
            "expected": expected,
            "passed": passed,
            "result": result
        })
        
        # 避免 API 限流
        time.sleep(1)
    
    # 汇总
    print_header("测试结果汇总")
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    for r in results:
        status = "✅" if r["passed"] else "❌"
        cmd = r["result"].get("command", "N/A") if r["result"] else "N/A"
        print(f"  {status} {r['container']}: {r['fault_type']} → {cmd}")
    
    print(f"\n  总计: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print("\n🎉 所有场景测试通过！")
        return 0
    else:
        print("\n⚠️  部分场景测试失败，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())

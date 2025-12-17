#!/usr/bin/env python3
"""
DeepSeek 完整测试 - 使用真实evidence和完整prompt
"""

import json
import sys
from pathlib import Path
import requests
from typing import Dict, Any

# DeepSeek API配置
API_KEY = "sk-76dac455bfa34a5d8c6b37d84e08ee60"
API_URL = "https://api.deepseek.com/v1/chat/completions"

# 完整的系统提示词（从DSL文件复制）
SYSTEM_PROMPT = """你是一个容器故障诊断专家。你的任务是分析容器故障证据，判断故障类型，并输出处理指令。
现在前方容器出现问题，这是前方发回的采样数据

{{EVIDENCE_STR}}

---

判断标准：
【阈值标准】
- CPU警告阈值：70%，严重阈值：90%
- 内存警告阈值：2G，严重阈值：2.5G

【决策规则】
1. 容器崩溃(exit_code非空) → command: RESTART
2. 资源使用 70%-90% → command: ALERT_ONLY
3. 资源使用 >90% → command: RESTART
4. 已重启3次仍异常 → command: STOP
5. 一切正常 → command: NONE

【举例】
证据：
{
  "event_id": "evt_20251203_131100",
  "timestamp": "2025-12-03T13:11:00.123456",
  "container": {
    "id": "def456abc789",
    "name": "cpu-stress",
    "image": "test/cpu-stress:latest",
    "status": "running",
    "running": true,
    "restarting": false,
    "paused": false,
    "oom_killed": false,
    "exit_code": 0,
    "error": "",
    "started_at": "2025-12-03T10:00:00.000000Z",
    "finished_at": "0001-01-01T00:00:00Z",
    "restart_count": 0,
    "restart_policy": "always",
    "memory_limit": 0,
    "cpu_limit": 0,
    "ip_address": "172.17.0.3",
    "ports": {}
  },
  "evidence": {
    "exit_code": 0,
    "oom_killed": false,
    "error_message": "",
    "cpu_percent": "95.2%",
    "memory_percent": "45.0%",
    "memory_usage": "230MiB / 512MiB",
    "logs_tail": "2025-12-03 13:10:55 Running stress test...\\n2025-12-03 13:10:58 CPU load: 95%",
    "restart_count_24h": 0,
    "health_check": {
      "healthy": true,
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
你的回复：
{
  "fault_type": "CPU_HIGH",
  "command": "ALERT_ONLY",
  "params": {
    "container_name": "cpu-stress",
    "current_cpu": "95.2%",
    "current_memory": "45.0%",
    "retry_count": 0
  },
  "reason": "CPU使用率95.2%超过严重阈值80%，但容器健康检查正常且未崩溃，仅告警观察"
}
---
证据：
{
  "event_id": "evt_20251203_131300",
  "timestamp": "2025-12-03T13:13:00.123456",
  "container": {
    "id": "mno345pqr678",
    "name": "normal-app",
    "image": "nginx:latest",
    "status": "running",
    "running": true,
    "restarting": false,
    "paused": false,
    "oom_killed": false,
    "exit_code": 0,
    "error": "",
    "started_at": "2025-12-01T00:00:00.000000Z",
    "finished_at": "0001-01-01T00:00:00Z",
    "restart_count": 0,
    "restart_policy": "always",
    "memory_limit": 536870912,
    "cpu_limit": 0,
    "ip_address": "172.17.0.2",
    "ports": {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "80"}]}
  },
  "evidence": {
    "exit_code": 0,
    "oom_killed": false,
    "error_message": "",
    "cpu_percent": "5.0%",
    "memory_percent": "20.0%",
    "memory_usage": "102MiB / 512MiB",
    "logs_tail": "2025-12-03 13:12:50 GET /index.html 200\\n2025-12-03 13:12:55 GET /api/health 200",
    "restart_count_24h": 0,
    "health_check": {
      "healthy": true,
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
你的回复：
{
  "fault_type": "NO_ERROR",
  "command": "NONE",
  "params": {
    "container_name": "normal-app",
    "current_cpu": "5.0%",
    "current_memory": "20.0%",
    "retry_count": 0
  },
  "reason": "容器运行正常，CPU 5.0%和内存20.0%均在阈值范围内，健康检查通过"
}"""


def call_deepseek(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """使用完整evidence调用DeepSeek API"""
    
    # 转换evidence为JSON字符串（模拟Dify的代码执行节点）
    evidence_str = json.dumps(evidence, ensure_ascii=False, indent=2)
    
    # 替换提示词中的占位符
    prompt = SYSTEM_PROMPT.replace("{{EVIDENCE_STR}}", evidence_str)
    
    # 调用API
    response = requests.post(
        API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": prompt}
            ],
            "temperature": 0
        },
        timeout=30
    )
    
    if response.status_code != 200:
        raise Exception(f"API错误 {response.status_code}: {response.text}")
    
    result = response.json()
    content = result['choices'][0]['message']['content']
    
    # 解析JSON响应
    try:
        decision = json.loads(content)
        return decision
    except json.JSONDecodeError:
        # 如果不是纯JSON，尝试提取
        print(f"⚠️  响应不是纯JSON: {content}")
        return {"error": "Invalid JSON", "raw": content}


def validate_decision(decision: Dict[str, Any]) -> tuple[bool, list]:
    """验证DeepSeek返回的决策格式"""
    errors = []
    
    # 检查必需字段
    required = ['fault_type', 'command', 'params', 'reason']
    for field in required:
        if field not in decision:
            errors.append(f"缺少字段: {field}")
    
    # 检查command枚举
    valid_commands = ['RESTART', 'STOP', 'ALERT_ONLY', 'NONE']
    if 'command' in decision and decision['command'] not in valid_commands:
        errors.append(f"无效command: {decision['command']}")
    
    # 检查fault_type枚举（模糊匹配提高鲁棒性）
    valid_faults = ['OOM_KILLED', 'CPU_HIGH', 'MEMORY_HIGH', 
                   'PROCESS_CRASH', 'CONTAINER_CRASH',
                   'HEALTH_FAIL', 'NO_ERROR', 'UNKNOWN']
    
    if 'fault_type' in decision:
        fault_type = decision['fault_type']
        # 先精确匹配
        if fault_type not in valid_faults:
            # 如果精确匹配失败，尝试模糊匹配（检查是否包含关键词）
            matched = False
            for valid_fault in valid_faults:
                # 检查是否互相包含（提高鲁棒性）
                if valid_fault in fault_type or fault_type in valid_fault:
                    matched = True
                    break
            
            if not matched:
                errors.append(f"无效fault_type: {fault_type}")
    
    # 检查params
    if 'params' in decision:
        if not isinstance(decision['params'], dict):
            errors.append("params必须是对象")
        elif 'container_name' not in decision['params']:
            errors.append("params缺少container_name")
    
    return len(errors) == 0, errors


def test_evidence_file(filepath: Path, expected_command: str = None):
    """测试单个evidence文件"""
    print(f"\n{'='*80}")
    print(f"测试: {filepath.name}")
    print('='*80)
    
    # 加载evidence
    with open(filepath, 'r', encoding='utf-8') as f:
        evidence = json.load(f)
    
    # 显示关键信息
    container_name = evidence['container']['name']
    cpu = evidence['evidence']['cpu_percent']
    mem = evidence['evidence']['memory_percent']
    status = evidence['container']['status']
    exit_code = evidence['evidence']['exit_code']
    
    print(f"📊 Evidence信息:")
    print(f"   容器: {container_name}")
    print(f"   CPU: {cpu}, 内存: {mem}")
    print(f"   状态: {status}, Exit Code: {exit_code}")
    print(f"   大小: {len(json.dumps(evidence))} 字符")
    
    # 调用DeepSeek
    print(f"\n📤 调用DeepSeek API...")
    try:
        decision = call_deepseek(evidence)
        
        print(f"\n📥 DeepSeek决策:")
        print(json.dumps(decision, ensure_ascii=False, indent=2))
        
        # 验证格式
        valid, errors = validate_decision(decision)
        
        if not valid:
            print(f"\n❌ 格式验证失败:")
            for err in errors:
                print(f"   - {err}")
            return {'status': 'INVALID', 'errors': errors, 'decision': decision}
        
        # 检查预期
        if expected_command:
            if decision['command'] == expected_command:
                print(f"\n✅ 测试通过: command={decision['command']}")
                return {'status': 'PASS', 'decision': decision}
            else:
                print(f"\n⚠️  决策不符: 预期={expected_command}, 实际={decision['command']}")
                return {'status': 'MISMATCH', 'expected': expected_command, 
                       'actual': decision['command'], 'decision': decision}
        else:
            print(f"\n✅ 格式正确: command={decision['command']}")
            return {'status': 'VALID', 'decision': decision}
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'ERROR', 'error': str(e)}


def main():
    """主测试函数"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 22 + "DeepSeek 完整测试" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    print("📋 测试说明:")
    print("   - 使用真实Docker容器收集的evidence")
    print("   - 使用完整的系统提示词（包含few-shot示例）")
    print("   - 发送完整的evidence JSON数据")
    print("   - 验证DeepSeek的决策准确性")
    print()
    
    logs_dir = Path('/home/lyb/cloud-watchdog/logs')
    
    # 定义测试用例（文件名，预期命令，描述）
    test_cases = [
        ('normal_running_20251204.json', 'NONE', '正常运行容器'),
        ('cpu_high_50percent_20251204.json', 'NONE', 'CPU 50%（未达70%警告阈值）'),
        ('memory_high_80percent_20251204.json', 'ALERT_ONLY', '内存80%（70-90%区间）'),
        ('evidence_test-crash.json', 'RESTART', '容器崩溃'),
    ]
    
    results = []
    
    for filename, expected, description in test_cases:
        filepath = logs_dir / filename
        
        if not filepath.exists():
            print(f"\n⚠️  跳过: {filename} (文件不存在)")
            continue
        
        print(f"\n场景: {description}")
        result = test_evidence_file(filepath, expected)
        result['file'] = filename
        result['description'] = description
        results.append(result)
        
        # 避免API限流
        import time
        time.sleep(2)
    
    # 输出总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    
    passed = sum(1 for r in results if r['status'] == 'PASS')
    mismatch = sum(1 for r in results if r['status'] == 'MISMATCH')
    invalid = sum(1 for r in results if r['status'] == 'INVALID')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    
    for r in results:
        icon = {
            'PASS': '✅',
            'MISMATCH': '⚠️ ',
            'INVALID': '❌',
            'ERROR': '❌',
            'VALID': 'ℹ️ '
        }.get(r['status'], '?')
        
        print(f"{icon} {r['description']:30} {r['status']}")
        if r['status'] == 'MISMATCH':
            print(f"     预期: {r['expected']} → 实际: {r['actual']}")
    
    print(f"\n总计: {passed} 通过, {mismatch} 偏差, {invalid} 格式错误, {errors} 失败")
    
    # 保存结果
    results_file = logs_dir / 'test_results_complete.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 详细结果已保存: {results_file}")
    
    return 0 if (invalid + errors) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

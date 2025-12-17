#!/usr/bin/env python3
"""
DeepSeek 真实数据测试
使用真实 Docker 容器收集的 evidence 数据测试 DeepSeek
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from watchdog.evidence import collect_evidence

# DeepSeek API Key
API_KEY = "sk-76dac455bfa34a5d8c6b37d84e08ee60"

# 系统提示词
SYSTEM_PROMPT = """你是一个容器故障诊断专家。你的任务是分析容器故障证据，判断故障类型，并输出处理指令。
现在前方容器出现问题，这是前方发回的采样数据 evidence_str（取证数据）

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
}
"""


def call_deepseek_api(evidence: dict) -> dict:
    """调用 DeepSeek API"""
    import requests
    
    evidence_str = json.dumps(evidence, ensure_ascii=False, indent=2)
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n**重要**: 你必须返回有效的 JSON 格式，不要有任何其他文本。"
            },
            {
                "role": "user",
                "content": f"证据：\n{evidence_str}\n你的回复："
            }
        ],
        "temperature": 0
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    # 打印错误详情
    if response.status_code != 200:
        print(f"   ❌ API 错误 {response.status_code}:")
        print(f"   {response.text}")
    
    response.raise_for_status()
    
    result = response.json()
    content = result['choices'][0]['message']['content']
    
    # 尝试解析 JSON
    try:
        return json.loads(content)
    except:
        # 如果不是标准 JSON，尝试提取
        print(f"   ⚠️  响应不是标准 JSON，原始内容:")
        print(f"   {content}")
        return {"error": "Invalid JSON response", "raw": content}


def validate_response(response: dict) -> tuple:
    """验证响应格式"""
    errors = []
    
    required_fields = ['fault_type', 'command', 'params', 'reason']
    for field in required_fields:
        if field not in response:
            errors.append(f"缺少必需字段: {field}")
    
    valid_commands = ['RESTART', 'STOP', 'ALERT_ONLY', 'NONE']
    if 'command' in response and response['command'] not in valid_commands:
        errors.append(f"无效的 command 值: {response['command']}")
    
    # 扩展fault_type验证（模糊匹配提高鲁棒性）
    valid_fault_types = [
        'OOM_KILLED', 'CPU_HIGH', 'MEMORY_HIGH', 
        'PROCESS_CRASH', 'CONTAINER_CRASH',
        'HEALTH_FAIL', 'NO_ERROR', 'UNKNOWN'
    ]
    
    if 'fault_type' in response:
        fault_type = response['fault_type']
        # 先精确匹配
        if fault_type not in valid_fault_types:
            # 如果精确匹配失败，尝试模糊匹配
            matched = False
            for valid_fault in valid_fault_types:
                if valid_fault in fault_type or fault_type in valid_fault:
                    matched = True
                    break
            
            if not matched:
                errors.append(f"无效的 fault_type 值: {fault_type}")
    
    if 'params' in response:
        if not isinstance(response['params'], dict):
            errors.append("params 必须是对象")
        elif 'container_name' not in response['params']:
            errors.append("params 缺少 container_name 字段")
    
    return len(errors) == 0, errors


def create_test_containers():
    """使用已有的 docker-compose 创建测试容器"""
    import subprocess
    import os
    
    print("\n" + "=" * 80)
    print("📦 使用 docker-compose 启动测试容器...")
    print("=" * 80)
    
    compose_dir = '/home/lyb/cloud-watchdog/test-containers'
    
    # 先停止并删除旧容器
    print("\n🧹 清理旧容器...")
    subprocess.run(['docker-compose', 'down'], 
                   cwd=compose_dir, 
                   capture_output=True)
    
    # 构建镜像（如果需要）
    print("\n🔨 构建测试镜像...")
    result = subprocess.run(['docker-compose', 'build'], 
                           cwd=compose_dir, 
                           capture_output=True,
                           text=True)
    if result.returncode != 0:
        print(f"   ⚠️  构建警告: {result.stderr}")
    else:
        print("   ✅ 镜像构建完成")
    
    # 启动容器
    print("\n🚀 启动测试容器...")
    result = subprocess.run(['docker-compose', 'up', '-d'], 
                           cwd=compose_dir,
                           capture_output=True,
                           text=True)
    
    if result.returncode != 0:
        print(f"   ❌ 启动失败: {result.stderr}")
        return []
    
    print("   ✅ 容器启动成功")
    
    # 定义测试场景（容器名，预期命令，描述）
    containers = [
        ('normal-app', 'NONE', '正常运行'),
        ('cpu-stress', 'RESTART', 'CPU 高负载'),
        ('memory-leak', 'ALERT_ONLY', '内存使用高'),
        ('crash-loop', 'RESTART', '进程崩溃'),
    ]
    
    print(f"\n✅ 共启动 {len(containers)} 个测试容器")
    print("⏳ 注意: cpu-stress 和 memory-leak 需要等待 30 秒后才开始压力测试")
    
    return containers


def cleanup_containers(container_names):
    """清理测试容器"""
    import subprocess
    
    print("\n" + "=" * 80)
    print("🧹 清理测试容器...")
    print("=" * 80)
    
    compose_dir = '/home/lyb/cloud-watchdog/test-containers'
    
    result = subprocess.run(['docker-compose', 'down'], 
                           cwd=compose_dir,
                           capture_output=True,
                           text=True)
    
    if result.returncode == 0:
        print(f"   ✅ 所有测试容器已清理")
    else:
        print(f"   ⚠️  清理警告: {result.stderr}")


def main():
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 18 + "DeepSeek 真实数据处理能力测试" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    print("⚠️  本测试使用真实 Docker 容器收集的 evidence 数据")
    print("⚠️  将创建多个测试容器，模拟不同故障场景")
    print()
    
    containers = None
    
    try:
        # 创建测试容器
        containers = create_test_containers()
        
        # 等待容器稳定和压力测试启动
        print("\n⏳ 等待 35 秒让容器稳定并启动压力测试...")
        print("   (cpu-stress 和 memory-leak 会在30秒后开始压力)")
        time.sleep(35)
        
        # 收集证据并测试
        print("\n" + "=" * 80)
        print("🔍 收集真实 evidence 并测试 DeepSeek...")
        print("=" * 80)
        
        results = []
        
        for i, (container_name, expected_command, description) in enumerate(containers, 1):
            print(f"\n{'=' * 80}")
            print(f"测试 {i}/{len(containers)}: {container_name} - {description}")
            print("=" * 80)
            
            # 收集真实 evidence
            print(f"\n📊 收集真实 Docker evidence...")
            try:
                evidence = collect_evidence(container_name)
                
                if not evidence:
                    print(f"   ❌ 无法收集 evidence（容器可能已退出）")
                    
                    # 对于崩溃容器，尝试 docker inspect
                    import subprocess
                    result = subprocess.run(
                        ['docker', 'inspect', container_name],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        print(f"   ⚠️  容器不存在，跳过")
                        continue
                
                # 显示证据关键信息
                print(f"   ✅ Evidence 收集成功")
                print(f"   - 容器: {evidence['container']['name']}")
                print(f"   - 状态: {evidence['container']['status']}")
                print(f"   - CPU: {evidence['evidence']['cpu_percent']}")
                print(f"   - 内存: {evidence['evidence']['memory_percent']}")
                print(f"   - Exit Code: {evidence['evidence']['exit_code']}")
                print(f"   - OOM: {evidence['evidence']['oom_killed']}")
                
                # 保存原始 evidence
                evidence_file = f'/tmp/evidence_{container_name}.json'
                with open(evidence_file, 'w', encoding='utf-8') as f:
                    json.dump(evidence, f, ensure_ascii=False, indent=2)
                print(f"   - 原始数据已保存: {evidence_file}")
                
                # 调用 DeepSeek API
                print(f"\n📤 调用 DeepSeek API...")
                print(f"   - Evidence 大小: {len(json.dumps(evidence))} 字符")
                
                response = call_deepseek_api(evidence)
                
                print(f"\n📥 DeepSeek 响应:")
                print(json.dumps(response, ensure_ascii=False, indent=2))
                
                # 验证格式
                valid, errors = validate_response(response)
                
                if not valid:
                    print(f"\n❌ 格式验证失败:")
                    for error in errors:
                        print(f"   - {error}")
                    results.append({
                        "container": container_name,
                        "description": description,
                        "status": "FORMAT_ERROR",
                        "errors": errors,
                        "evidence_file": evidence_file
                    })
                    continue
                
                # 检查决策
                command_match = response['command'] == expected_command
                
                print(f"\n{'✅' if valid else '❌'} 格式验证: {'通过' if valid else '失败'}")
                print(f"{'✅' if command_match else '⚠️ '} 决策检查:")
                print(f"   - 预期: {expected_command}")
                print(f"   - 实际: {response['command']}")
                print(f"   - 原因: {response.get('reason', 'N/A')}")
                
                results.append({
                    "container": container_name,
                    "description": description,
                    "status": "PASSED" if (valid and command_match) else "MISMATCH",
                    "expected_command": expected_command,
                    "actual_command": response['command'],
                    "response": response,
                    "evidence_file": evidence_file
                })
                
            except Exception as e:
                print(f"\n❌ 测试失败: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    "container": container_name,
                    "description": description,
                    "status": "ERROR",
                    "error": str(e)
                })
        
        # 输出总结
        print("\n" + "=" * 80)
        print("📊 测试总结")
        print("=" * 80)
        
        passed = sum(1 for r in results if r['status'] == 'PASSED')
        mismatch = sum(1 for r in results if r['status'] == 'MISMATCH')
        failed = sum(1 for r in results if r['status'] in ['FORMAT_ERROR', 'ERROR'])
        
        for result in results:
            status_map = {
                'PASSED': '✅',
                'MISMATCH': '⚠️ ',
                'FORMAT_ERROR': '❌',
                'ERROR': '❌'
            }
            icon = status_map.get(result['status'], '?')
            print(f"{icon} {result['container']}: {result['status']} - {result['description']}")
            if result['status'] == 'MISMATCH':
                print(f"     预期: {result.get('expected_command')} → 实际: {result.get('actual_command')}")
        
        print(f"\n总计: {passed} 通过, {mismatch} 决策偏差, {failed} 失败")
        print("=" * 80)
        
        # 保存详细结果
        with open('/tmp/deepseek_real_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📁 详细结果已保存: /tmp/deepseek_real_test_results.json")
        print(f"📁 原始 evidence 数据: /tmp/evidence_*.json")
        
        return 0 if failed == 0 else 1
        
    finally:
        # 清理容器
        if containers:
            cleanup_containers(containers)


if __name__ == "__main__":
    sys.exit(main())

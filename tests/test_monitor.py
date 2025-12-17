#!/usr/bin/env python3
"""
Cloud Watchdog 基本功能测试（不依赖 Dify）
测试：监控、证据收集、邮件通知
"""

import sys
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from watchdog.config import get_config
from watchdog.monitor import ContainerMonitor
from watchdog.evidence import collect_evidence
from watchdog.notifier import send_email, format_alert_email

def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("📋 测试 1: 配置加载")
    print("=" * 60)
    
    try:
        config = get_config()
        print(f"✅ 配置加载成功")
        print(f"   - 日志级别: {config.system.log_level}")
        print(f"   - 检查间隔: {config.system.check_interval_seconds}s")
        print(f"   - 邮件发送: {'启用' if config.email.enabled else '禁用'}")
        print(f"   - 监控容器数: {len(config.containers)}")
        for name in config.containers:
            print(f"     • {name}")
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def test_docker_connection():
    """测试 Docker 连接"""
    print("\n" + "=" * 60)
    print("🐳 测试 2: Docker 连接")
    print("=" * 60)
    
    try:
        import subprocess
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            print(f"✅ Docker 连接正常")
            lines = result.stdout.strip().split('\n')
            print(f"   - 运行中容器数: {len(lines) - 1}")
            return True
        else:
            print(f"❌ Docker 命令失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Docker 连接失败: {e}")
        return False

def test_evidence_collection():
    """测试证据收集"""
    print("\n" + "=" * 60)
    print("🔍 测试 3: 证据收集（需要有运行中的容器）")
    print("=" * 60)
    
    try:
        import subprocess
        import json
        
        # 获取第一个运行中的容器
        result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'],
                              capture_output=True,
                              text=True)
        
        containers = result.stdout.strip().split('\n')
        containers = [c for c in containers if c]
        
        if not containers:
            print("⚠️  没有运行中的容器，跳过此测试")
            return True
        
        test_container = containers[0]
        print(f"   测试容器: {test_container}")
        
        evidence = collect_evidence(test_container)
        
        if evidence:
            print(f"✅ 证据收集成功")
            print(f"   - 容器状态: {evidence.get('container', {}).get('status', 'unknown')}")
            print(f"   - CPU: {evidence.get('evidence', {}).get('cpu_percent', 'N/A')}")
            print(f"   - 内存: {evidence.get('evidence', {}).get('memory_percent', 'N/A')}")
            print(f"   - 日志行数: {len(evidence.get('evidence', {}).get('logs_tail', []))}")
            
            # 保存证据到文件
            import json
            with open('/tmp/test_evidence.json', 'w') as f:
                json.dump(evidence, f, indent=2, ensure_ascii=False)
            print(f"   - 完整证据已保存到: /tmp/test_evidence.json")
            return True
        else:
            print(f"❌ 证据收集失败")
            return False
            
    except Exception as e:
        print(f"❌ 证据收集异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_email_notification():
    """测试邮件通知"""
    print("\n" + "=" * 60)
    print("📧 测试 4: 邮件通知")
    print("=" * 60)
    
    try:
        config = get_config()
        
        if not config.email.enabled:
            print("⚠️  邮件通知已禁用，跳过此测试")
            return True
        
        # 构造测试告警数据
        test_data = {
            "type": "alert",
            "container_name": "test-container",
            "fault_type": "HEALTH_CHECK_FAILED",
            "reason": "健康检查失败",
            "current_cpu": "95.5%",
            "current_memory": "88.2%"
        }
        
        subject, email_body = format_alert_email(test_data)
        
        print(f"   发送测试邮件到: {config.email.recipients}")
        result = send_email(
            subject="[测试] Cloud Watchdog 告警通知",
            body=email_body,
            recipients=config.email.recipients
        )
        
        if result.get("success"):
            print(f"✅ 邮件发送成功")
            return True
        else:
            print(f"❌ 邮件发送失败: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ 邮件通知异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_monitoring_loop():
    """测试监控循环（短时间运行）"""
    print("\n" + "=" * 60)
    print("🔄 测试 5: 监控循环（运行 30 秒）")
    print("=" * 60)
    
    try:
        monitor = ContainerMonitor()
        
        print("   启动监控...")
        monitor.start()
        
        print("   监控运行中，请观察输出...")
        print("   （将运行 30 秒后自动停止）")
        
        # 运行 30 秒
        for i in range(30):
            time.sleep(1)
            if (i + 1) % 10 == 0:
                print(f"   ... {i + 1}秒")
        
        print("   停止监控...")
        monitor.stop()
        
        print(f"✅ 监控循环测试完成")
        return True
        
    except KeyboardInterrupt:
        print("\n   用户中断")
        monitor.stop()
        return True
    except Exception as e:
        print(f"❌ 监控循环异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试流程"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "Cloud Watchdog 基本功能测试" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    results = []
    
    # 测试 1: 配置加载
    results.append(("配置加载", test_config_loading()))
    
    # 测试 2: Docker 连接
    results.append(("Docker 连接", test_docker_connection()))
    
    # 测试 3: 证据收集
    results.append(("证据收集", test_evidence_collection()))
    
    # 测试 4: 邮件通知
    results.append(("邮件通知", test_email_notification()))
    
    # 测试 5: 监控循环
    print("\n是否运行监控循环测试（30秒）？[y/N]: ", end='')
    try:
        choice = input().strip().lower()
        if choice == 'y':
            results.append(("监控循环", test_monitoring_loop()))
    except:
        print("跳过监控循环测试")
    
    # 输出测试总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print(f"\n   总计: {passed}/{total} 通过")
    print("=" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())

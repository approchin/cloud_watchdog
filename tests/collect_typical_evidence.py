#!/usr/bin/env python3
"""
典型故障场景 Evidence 收集脚本

用途：
    收集各种典型故障场景的Docker容器evidence数据，用于：
    1. DeepSeek决策测试
    2. 监控系统验证
    3. 故障诊断学习

使用方法：
    python3 collect_typical_evidence.py

输出：
    logs/*.json - 各种典型场景的evidence数据
"""

import subprocess
import time
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))  # tests/ -> cloud-watchdog/
from watchdog.evidence import collect_evidence


class TypicalEvidenceCollector:
    """典型Evidence收集器"""
    
    def __init__(self, logs_dir='logs'):
        # logs目录在项目根目录，不是tests/下
        self.logs_dir = Path(__file__).parent.parent / logs_dir
        self.logs_dir.mkdir(exist_ok=True)
        self.results = []
    
    def _run_docker_cmd(self, container_name, command, silent=True):
        """在容器中执行命令"""
        cmd = ['docker', 'exec', container_name, 'sh', '-c', command]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=10
        )
        if not silent and result.returncode != 0:
            print(f"  ⚠️  命令执行警告: {result.stderr}")
        return result
    
    def _save_evidence(self, evidence, scenario_name, description=""):
        """保存evidence到文件"""
        if not evidence:
            print(f"  ❌ evidence为空，跳过保存")
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{scenario_name}_{timestamp}.json"
        filepath = self.logs_dir / filename
        
        # 添加元数据
        evidence['_metadata'] = {
            'scenario': scenario_name,
            'description': description,
            'collected_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(evidence, f, ensure_ascii=False, indent=2)
        
        print(f"  📁 保存: {filename}")
        
        # 显示关键指标
        cpu = evidence['evidence'].get('cpu_percent', 'N/A')
        mem = evidence['evidence'].get('memory_percent', 'N/A')
        status = evidence['container'].get('status', 'N/A')
        exit_code = evidence['evidence'].get('exit_code', 'N/A')
        
        print(f"  📊 CPU: {cpu}, 内存: {mem}, 状态: {status}, 退出码: {exit_code}")
        
        return str(filepath)
    
    def collect_normal_running(self):
        """场景1: 正常运行容器"""
        print("\n" + "=" * 80)
        print("【场景1】正常运行容器")
        print("=" * 80)
        print("描述: CPU和内存都在正常范围，容器稳定运行")
        print("-" * 80)
        
        evidence = collect_evidence('normal-app')
        filepath = self._save_evidence(
            evidence, 
            'normal_running',
            'CPU < 10%, 内存 < 10%, 容器正常运行'
        )
        
        self.results.append({
            'scenario': '正常运行',
            'expected_command': 'NONE',
            'file': filepath
        })
    
    def collect_cpu_high_50(self):
        """场景2: CPU 50% (未达警告阈值70%)"""
        print("\n" + "=" * 80)
        print("【场景2】CPU 50% - 未达警告阈值")
        print("=" * 80)
        print("描述: CPU使用50%，低于70%警告阈值，应判断为正常")
        print("-" * 80)
        
        # 使用默认配置的cpu-stress (2 workers)
        print("  ⏳ 等待5秒确保压力稳定...")
        time.sleep(5)
        
        evidence = collect_evidence('cpu-stress')
        filepath = self._save_evidence(
            evidence,
            'cpu_50percent',
            'CPU约50%，cpus限制0.5核心，2个worker'
        )
        
        self.results.append({
            'scenario': 'CPU 50%',
            'expected_command': 'NONE',
            'file': filepath
        })
    
    def collect_cpu_high_100(self):
        """场景3: CPU 100% (达到limit上限，应告警)"""
        print("\n" + "=" * 80)
        print("【场景3】CPU 100% - 打满limit上限")
        print("=" * 80)
        print("描述: CPU打满到limit (0.5核=50%)，但因为是100%利用率应告警")
        print("-" * 80)
        
        # 增加CPU worker数量打满
        print("  🔧 临时增加CPU worker到4个...")
        self._run_docker_cmd(
            'cpu-stress',
            'pkill stress-ng && nohup stress-ng --cpu 4 --timeout 0 > /dev/null 2>&1 &'
        )
        
        print("  ⏳ 等待10秒让CPU打满...")
        time.sleep(10)
        
        evidence = collect_evidence('cpu-stress')
        filepath = self._save_evidence(
            evidence,
            'cpu_100percent',
            'CPU 100%使用，4个worker争抢0.5核心'
        )
        
        # 恢复原状
        print("  🔄 恢复为2个worker...")
        self._run_docker_cmd(
            'cpu-stress',
            'pkill stress-ng && nohup stress-ng --cpu 2 --timeout 0 > /dev/null 2>&1 &'
        )
        
        self.results.append({
            'scenario': 'CPU 100%',
            'expected_command': 'ALERT_ONLY',
            'file': filepath
        })
    
    def collect_memory_high_80(self):
        """场景4: 内存 80% (70-90%区间，应告警)"""
        print("\n" + "=" * 80)
        print("【场景4】内存 80% - 告警区间")
        print("=" * 80)
        print("描述: 内存使用80%，在70-90%告警区间")
        print("-" * 80)
        
        # 使用默认配置 (200M / 256M limit)
        print("  ⏳ 等待5秒确保内存稳定...")
        time.sleep(5)
        
        evidence = collect_evidence('memory-leak')
        filepath = self._save_evidence(
            evidence,
            'memory_80percent',
            '内存200M/256M约80%，在告警区间'
        )
        
        self.results.append({
            'scenario': '内存 80%',
            'expected_command': 'ALERT_ONLY',
            'file': filepath
        })
    
    def collect_memory_high_95(self):
        """场景5: 内存 95% (接近limit，高风险)"""
        print("\n" + "=" * 80)
        print("【场景5】内存 95% - 接近OOM")
        print("=" * 80)
        print("描述: 内存使用95%，非常接近limit，高风险需重启")
        print("-" * 80)
        
        # 增加内存分配到240M (95%)
        print("  🔧 临时增加内存分配到240M...")
        self._run_docker_cmd(
            'memory-leak',
            'pkill stress-ng && nohup stress-ng --vm 1 --vm-bytes 240M --timeout 0 > /dev/null 2>&1 &'
        )
        
        print("  ⏳ 等待15秒让内存升高...")
        time.sleep(15)
        
        evidence = collect_evidence('memory-leak')
        filepath = self._save_evidence(
            evidence,
            'memory_95percent',
            '内存240M/256M约95%，接近OOM风险'
        )
        
        # 恢复原状
        print("  🔄 恢复为200M...")
        self._run_docker_cmd(
            'memory-leak',
            'pkill stress-ng && nohup stress-ng --vm 1 --vm-bytes 200M --timeout 0 > /dev/null 2>&1 &'
        )
        
        self.results.append({
            'scenario': '内存 95%',
            'expected_command': 'RESTART',
            'file': filepath
        })
    
    def collect_container_crash(self):
        """场景6: 容器崩溃 (exit_code != 0)"""
        print("\n" + "=" * 80)
        print("【场景6】容器崩溃")
        print("=" * 80)
        print("描述: 容器以非0退出码退出，需要重启")
        print("-" * 80)
        
        # crash-loop容器会自动崩溃，等待它崩溃
        print("  ⏳ 等待crash-loop容器崩溃...")
        
        # 先检查当前状态
        for i in range(10):
            evidence = collect_evidence('crash-loop')
            if evidence and evidence['container']['status'] == 'exited':
                print(f"  ✅ 容器已崩溃 (尝试 {i+1}/10)")
                break
            time.sleep(3)
        else:
            print("  ⚠️  容器未崩溃，收集当前状态")
        
        evidence = collect_evidence('crash-loop')
        filepath = self._save_evidence(
            evidence,
            'container_crash',
            '容器崩溃，exit_code=1'
        )
        
        self.results.append({
            'scenario': '容器崩溃',
            'expected_command': 'RESTART',
            'file': filepath
        })
    
    def collect_oom_killed(self):
        """场景7: OOM被杀 (超过内存limit)"""
        print("\n" + "=" * 80)
        print("【场景7】OOM Killed - 内存超限被杀")
        print("=" * 80)
        print("描述: 内存超过limit被Docker OOM Killer杀掉")
        print("-" * 80)
        
        # 创建临时容器，分配超过limit的内存
        print("  🔧 创建临时OOM测试容器...")
        
        # 先清理可能存在的旧容器
        subprocess.run(['docker', 'rm', '-f', 'test-oom'], 
                      capture_output=True)
        
        # 创建一个会OOM的容器 (limit 64M, 尝试分配 100M)
        result = subprocess.run([
            'docker', 'run', '-d',
            '--name', 'test-oom',
            '--memory', '64m',
            '--restart', 'no',
            'alpine:latest',
            'sh', '-c', 
            'echo "Allocating memory..." && '
            'dd if=/dev/zero of=/tmp/fill bs=1M count=100 || exit 137'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"  ❌ 容器创建失败: {result.stderr}")
            return
        
        print("  ⏳ 等待10秒让OOM发生...")
        time.sleep(10)
        
        evidence = collect_evidence('test-oom')
        filepath = self._save_evidence(
            evidence,
            'oom_killed',
            '容器因内存超限被OOM Killer杀掉'
        )
        
        # 清理
        print("  🧹 清理测试容器...")
        subprocess.run(['docker', 'rm', '-f', 'test-oom'], 
                      capture_output=True)
        
        self.results.append({
            'scenario': 'OOM Killed',
            'expected_command': 'RESTART',
            'file': filepath
        })
    
    def collect_high_restart_count(self):
        """场景8: 高频重启 (24小时内重启多次)"""
        print("\n" + "=" * 80)
        print("【场景8】频繁重启 - 应触发熔断")
        print("=" * 80)
        print("描述: 容器在短时间内多次重启，应判断为STOP")
        print("-" * 80)
        
        # 创建一个频繁重启的容器
        print("  🔧 创建频繁重启测试容器...")
        
        subprocess.run(['docker', 'rm', '-f', 'test-restart-loop'], 
                      capture_output=True)
        
        # 创建容器，每5秒崩溃一次，restart策略会自动重启
        subprocess.run([
            'docker', 'run', '-d',
            '--name', 'test-restart-loop',
            '--restart', 'always',
            'alpine:latest',
            'sh', '-c', 
            'while true; do echo "Running..."; sleep 5; exit 1; done'
        ], capture_output=True)
        
        print("  ⏳ 等待30秒累积重启次数...")
        time.sleep(30)
        
        evidence = collect_evidence('test-restart-loop')
        
        if evidence:
            restart_count = evidence['container'].get('restart_count', 0)
            print(f"  📊 重启次数: {restart_count}")
        
        filepath = self._save_evidence(
            evidence,
            'high_restart_count',
            f'容器频繁重启，累积次数: {restart_count if evidence else "N/A"}'
        )
        
        # 清理
        print("  🧹 清理测试容器...")
        subprocess.run(['docker', 'rm', '-f', 'test-restart-loop'], 
                      capture_output=True)
        
        self.results.append({
            'scenario': '频繁重启',
            'expected_command': 'STOP',
            'file': filepath
        })
    
    def print_summary(self):
        """打印收集总结"""
        print("\n" + "=" * 80)
        print("📊 Evidence 收集总结")
        print("=" * 80)
        
        print(f"\n共收集 {len(self.results)} 个典型场景:\n")
        
        for i, result in enumerate(self.results, 1):
            icon = "✅" if result['file'] else "❌"
            print(f"{i}. {icon} {result['scenario']:20} 预期: {result['expected_command']:12}")
            if result['file']:
                print(f"   📁 {result['file']}")
        
        print(f"\n📁 所有数据保存在: {self.logs_dir}/")
        print(f"📝 可用于测试: python3 test_deepseek_complete.py")


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 22 + "典型 Evidence 收集工具" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    print("⚠️  注意事项:")
    print("   1. 需要先启动测试容器: cd test-containers && docker-compose up -d")
    print("   2. 某些场景会临时修改容器配置，收集后会恢复")
    print("   3. 收集过程约需 2-3 分钟")
    print()
    
    input("按 Enter 开始收集...")
    
    collector = TypicalEvidenceCollector()
    
    try:
        # 按优先级收集各种场景
        collector.collect_normal_running()
        collector.collect_cpu_high_50()
        collector.collect_cpu_high_100()
        collector.collect_memory_high_80()
        collector.collect_memory_high_95()
        collector.collect_container_crash()
        collector.collect_oom_killed()
        collector.collect_high_restart_count()
        
        # 打印总结
        collector.print_summary()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        return 1
    except Exception as e:
        print(f"\n\n❌ 收集失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

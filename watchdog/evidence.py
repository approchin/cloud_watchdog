"""
证据收集模块
"""
import json
import shlex
from datetime import datetime
from typing import Dict, Any, Optional
from .config import get_config
from .utils import run_command
from . import security


def get_container_info(container_name: str) -> Optional[Dict[str, Any]]:
    """获取容器基本信息"""
    code, stdout, stderr = run_command([
        'docker', 'inspect', 
        '--format', '{{json .}}',
        container_name
    ])
    
    if code != 0:
        return None
    
    try:
        info = json.loads(stdout)
        state = info.get("State", {})
        host_config = info.get("HostConfig", {})
        network = info.get("NetworkSettings", {})
        
        return {
            "id": info.get("Id", "")[:12],
            "name": container_name,
            "image": info.get("Config", {}).get("Image", ""),
            # 状态信息
            "status": state.get("Status", ""),
            "running": state.get("Running", False),
            "restarting": state.get("Restarting", False),
            "paused": state.get("Paused", False),
            "oom_killed": state.get("OOMKilled", False),  # OOM 判断关键
            "exit_code": state.get("ExitCode", 0),
            "error": state.get("Error", ""),  # 错误原因（如端口冲突）
            "started_at": state.get("StartedAt", ""),
            "finished_at": state.get("FinishedAt", ""),
            # 重启信息
            "restart_count": info.get("RestartCount", 0),
            "restart_policy": host_config.get("RestartPolicy", {}).get("Name", "no"),
            # 资源限制
            "memory_limit": host_config.get("Memory", 0),
            "cpu_limit": host_config.get("NanoCpus", 0),
            # 网络信息
            "ip_address": network.get("IPAddress", ""),
            "ports": network.get("Ports", {})
        }
    except json.JSONDecodeError:
        return None


def get_container_stats(container_name: str) -> Optional[Dict[str, Any]]:
    """获取容器资源使用情况"""
    code, stdout, stderr = run_command([
        'docker', 'stats', '--no-stream',
        '--format', '{{json .}}',
        container_name
    ])
    
    if code != 0:
        return None
    
    try:
        stats = json.loads(stdout)
        return {
            "cpu_percent": stats.get("CPUPerc", "0%"),
            "memory_usage": stats.get("MemUsage", ""),
            "memory_percent": stats.get("MemPerc", "0%"),
            "net_io": stats.get("NetIO", ""),
            "block_io": stats.get("BlockIO", "")
        }
    except json.JSONDecodeError:
        return None


def get_container_logs(container_name: str, lines: int = 50) -> str:
    """获取容器最近日志"""
    code, stdout, stderr = run_command([
        'docker', 'logs', '--tail', str(lines),
        container_name
    ])
    
    if code != 0:
        return f"获取日志失败: {stderr}"
    
    logs = stdout if stdout else stderr
    return logs[:2000]


def check_container_health(container_name: str, health_config: Dict) -> Dict[str, Any]:
    """检查容器健康状态"""
    check_type = health_config.get("type", "")
    
    if check_type == "http":
        return _check_http_health(health_config)
    elif check_type == "tcp":
        return _check_tcp_health(health_config)
    elif check_type == "command":
        return _check_command_health(container_name, health_config)
    else:
        return {"healthy": True, "message": "无健康检查配置"}


def _check_http_health(config: Dict) -> Dict[str, Any]:
    """HTTP 健康检查"""
    import urllib.request
    import urllib.error
    
    endpoint = config.get("endpoint", "")
    expected_status = config.get("expected_status", 200)
    timeout = config.get("timeout_seconds", 5)
    
    try:
        req = urllib.request.Request(endpoint)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == expected_status:
                return {"healthy": True, "message": f"HTTP {response.status}"}
            else:
                return {"healthy": False, "message": f"HTTP {response.status}, 期望 {expected_status}"}
    except urllib.error.URLError as e:
        return {"healthy": False, "message": f"连接失败: {e.reason}"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def _check_tcp_health(config: Dict) -> Dict[str, Any]:
    """TCP 端口健康检查"""
    import socket
    
    host = config.get("host", "localhost")
    port = config.get("port", 80)
    timeout = config.get("timeout_seconds", 5)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return {"healthy": True, "message": f"TCP {host}:{port} 可达"}
        else:
            return {"healthy": False, "message": f"TCP {host}:{port} 不可达"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def _check_command_health(container_name: str, config: Dict) -> Dict[str, Any]:
    """命令健康检查"""
    command = config.get("command", "")
    expected_output = config.get("expected_output", "")
    timeout = config.get("timeout_seconds", 5)
    
    code, stdout, stderr = run_command(
        ['docker', 'exec', container_name] + shlex.split(command),
        timeout=timeout
    )
    
    if code == 0 and expected_output in stdout:
        return {"healthy": True, "message": stdout[:100]}
    else:
        return {"healthy": False, "message": f"命令返回: {stdout or stderr}"}


def collect_evidence(container_name: str, fault_type: str = "UNKNOWN") -> Dict[str, Any]:
    """收集完整证据包"""
    config = get_config()
    container_config = config.get_container(container_name)
    
    container_info = get_container_info(container_name) or {
        "name": container_name,
        "status": "unknown"
    }
    
    stats = get_container_stats(container_name) or {
        "cpu_percent": "0%",
        "memory_percent": "0%"
    }
    
    logs = get_container_logs(container_name, config.system.evidence_log_lines)
    
    # 新增：安全与网络取证
    security_issues = []
    injection_patterns = security.check_logs_for_injection(logs)
    if injection_patterns:
        security_issues.append(f"发现注入攻击特征: {injection_patterns}")
        
    malicious_procs = security.check_processes(container_name)
    if malicious_procs:
        security_issues.append(f"发现恶意进程: {malicious_procs}")
        
    active_ips = get_network_connections(container_name)
    
    health_result = {"healthy": True, "message": ""}
    if container_config and container_config.health_check:
        health_result = check_container_health(container_name, container_config.health_check)
    
    evidence = {
        "event_id": f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "container": container_info,
        "evidence": {
            "exit_code": container_info.get("exit_code"),
            "oom_killed": container_info.get("oom_killed", False),  # OOM 判断
            "error_message": container_info.get("error", ""),  # Docker 错误原因
            "cpu_percent": stats.get("cpu_percent", "0%"),
            "memory_percent": stats.get("memory_percent", "0%"),
            "memory_usage": stats.get("memory_usage", ""),
            "logs_tail": logs,
            "security_issues": security_issues,  # 新增字段
            "active_connections": active_ips,    # 新增字段
            "restart_count_24h": container_info.get("restart_count", 0),
            "health_check": health_result
        },
        "fault_type": fault_type,
        "thresholds": {
            "cpu_warning": config.thresholds.cpu_warning,
            "cpu_critical": config.thresholds.cpu_critical,
            "memory_warning": config.thresholds.memory_warning,
            "memory_critical": config.thresholds.memory_critical
        }
    }
    
    return evidence


def parse_percent(value: str) -> float:
    """解析百分比字符串为浮点数"""
    try:
        return float(value.replace('%', '').strip())
    except:
        return 0.0


def parse_memory_mb(mem_str: str) -> float:
    """
    解析内存字符串，返回 MB 数值
    输入格式示例: "100MiB / 1GiB" 或 "500MB"
    """
    try:
        # 取斜杠前的部分: "100MiB / 1GiB" -> "100MiB"
        used_part = mem_str.split('/')[0].strip()
        
        # 移除单位并计算
        if 'GiB' in used_part:
            return float(used_part.replace('GiB', '')) * 1024
        elif 'MiB' in used_part:
            return float(used_part.replace('MiB', ''))
        elif 'KiB' in used_part:
            return float(used_part.replace('KiB', '')) / 1024
        elif 'GB' in used_part:
            return float(used_part.replace('GB', '')) * 1000
        elif 'MB' in used_part:
            return float(used_part.replace('MB', ''))
        elif 'KB' in used_part:
            return float(used_part.replace('KB', '')) / 1000
        elif 'B' in used_part:
            return float(used_part.replace('B', '')) / 1024 / 1024
        else:
            return float(used_part)
    except (ValueError, AttributeError):
        return 0.0


def get_network_connections(container_name: str) -> Dict[str, int]:
    """
    获取容器的活跃网络连接 (IP及其连接数)
    返回格式: {"192.168.1.5": 10, "10.0.0.1": 2}
    """
    # 尝试使用 netstat
    code, stdout, stderr = run_command([
        'docker', 'exec', container_name, 
        'netstat', '-ntu'
    ])
    
    ip_counts = {}
    if code == 0:
        # 解析 netstat 输出
        # Proto Recv-Q Send-Q Local Address           Foreign Address         State
        # tcp        0      0 172.17.0.2:80           192.168.1.5:54321       ESTABLISHED
        lines = stdout.split('\n')
        for line in lines:
            # 跳过 Header 行 (包含 "Active Internet" 或 "Proto")
            if "Active Internet" in line or "Proto" in line:
                continue
            
            # 只处理 tcp/udp 开头的行
            if not (line.startswith('tcp') or line.startswith('udp')):
                continue
                
            parts = line.split()
            # 确保有足够字段且状态为 ESTABLISHED
            if len(parts) >= 6 and parts[5] == 'ESTABLISHED':
                foreign_addr = parts[4]
                ip = foreign_addr.split(':')[0]
                if ip and ip != '127.0.0.1' and not ip.startswith('::'):
                    ip_counts[ip] = ip_counts.get(ip, 0) + 1
    
    return ip_counts





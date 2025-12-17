"""
命令执行模块
"""
import subprocess
import time
import shlex
from datetime import datetime
from typing import Dict, Any
from .config import get_config
from .evidence import get_container_info, get_container_stats, check_container_health


COMMAND_TEMPLATES = {
    "RESTART": "docker restart {container_name}",
    "STOP": "docker stop {container_name}",
    "INSPECT": "docker inspect {container_name}",
    "COMMIT": "docker commit {container_name}",
}

# COMMIT 频率限制
COMMIT_COOLDOWN_SECONDS = 3600  # 同一容器 1 小时内最多 COMMIT 一次
last_commit_time: Dict[str, datetime] = {}


def execute_action(command: str, container_name: str, max_retries: int = None) -> Dict[str, Any]:
    """
    执行容器操作命令
    
    对于 RESTART 命令：
    - 最多重试 max_retries 次（默认从配置读取）
    - 每次重启后等待 restart_delay_seconds 秒再检测
    - 如果所有重试失败，停止容器并告警
    """
    config = get_config()
    container_config = config.get_container(container_name)
    command_upper = command.upper()
    
    # 检查是否允许的操作（白名单 + 模板存在）
    if command_upper not in config.executor.allowed_actions or command_upper not in COMMAND_TEMPLATES:
        return {
            "success": False,
            "action": command,
            "container": container_name,
            "error": f"不允许的操作: {command}",
            "timestamp": datetime.now().isoformat()
        }
    
    # RESTART 命令的重试逻辑
    if command_upper == "RESTART":
        return _execute_restart_with_retry(container_name, container_config, max_retries)
    
    # COMMIT 命令 (取证)
    if command_upper == "COMMIT":
        return _execute_commit(container_name)
    
    # 其他命令直接执行
    return _execute_single_command(command_upper, container_name, COMMAND_TEMPLATES[command_upper])


def _execute_commit(container_name: str) -> Dict[str, Any]:
    """
    执行容器 Commit 操作 (取证)
    包含轻量级内存取证：在 commit 前 dump 运行时状态到文件系统
    生成镜像名: {container_name}_evidence_{timestamp}
    """
    # 检查频率限制
    if container_name in last_commit_time:
        elapsed = (datetime.now() - last_commit_time[container_name]).total_seconds()
        if elapsed < COMMIT_COOLDOWN_SECONDS:
            return {
                "success": False, 
                "action": "COMMIT",
                "container": container_name,
                "error": f"COMMIT 冷却中，剩余 {int(COMMIT_COOLDOWN_SECONDS - elapsed)} 秒",
                "timestamp": datetime.now().isoformat()
            }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_tag = f"{container_name}_evidence_{timestamp}"
    
    # 1. 轻量级内存取证 (Runtime Dump)
    # 将进程列表、网络连接、环境变量写入容器内的 /tmp 目录
    # 这样 commit 后的镜像就会包含这些信息
    dump_cmd = [
        "docker", "exec", container_name, 
        "/bin/sh", "-c", 
        "ps auxf > /tmp/evidence_ps.txt 2>&1; netstat -anp > /tmp/evidence_net.txt 2>&1; env > /tmp/evidence_env.txt 2>&1"
    ]
    
    dump_result = {"success": False, "error": ""}
    try:
        subprocess.run(dump_cmd, capture_output=True, timeout=10)
        dump_result["success"] = True
    except Exception as e:
        dump_result["error"] = str(e)
    
    # 2. 执行 Commit
    commit_cmd = ["docker", "commit", container_name, image_tag]
    
    # 更新最后提交时间（无论成功与否，都进入冷却，防止 DoS）
    last_commit_time[container_name] = datetime.now()
    
    try:
        result = subprocess.run(commit_cmd, capture_output=True, text=True, timeout=60)
        success = result.returncode == 0
        
        return {
            "success": success,
            "action": "COMMIT",
            "container": container_name,
            "image_tag": image_tag,
            "runtime_dump": dump_result,
            "output": result.stdout.strip() if success else result.stderr.strip(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "action": "COMMIT",
            "container": container_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def _execute_single_command(command: str, container_name: str, template: str) -> Dict[str, Any]:
    """执行单次命令（STOP/INSPECT）"""
    cmd = template.format(container_name=container_name)
    
    try:
        result = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        success = result.returncode == 0
        
        # STOP 需要验证
        verification = None
        if command == "STOP":
            time.sleep(3)
            info = get_container_info(container_name)
            is_stopped = info is None or not info.get("running", False)
            verification = {
                "is_stopped": is_stopped,
                "reason": "容器已停止" if is_stopped else "容器仍在运行"
            }
        
        return {
            "success": success,
            "action": command,
            "container": container_name,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "verification": verification,
            "timestamp": datetime.now().isoformat()
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "action": command,
            "container": container_name,
            "error": "命令执行超时",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "action": command,
            "container": container_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def _execute_restart_with_retry(container_name: str, container_config, max_retries: int = None) -> Dict[str, Any]:
    """
    执行重启操作，带重试逻辑
    
    流程：
    1. 重启容器
    2. 等待 restart_delay_seconds 秒
    3. 检测容器状态和健康检查
    4. 如果失败，重复步骤 1-3（最多 max_retries 次）
    5. 所有重试失败后，停止容器并返回失败
    """
    config = get_config()
    
    # 从容器配置获取参数，否则使用默认值
    if container_config and container_config.policy:
        policy = container_config.policy
        if max_retries is None:
            max_retries = policy.get('max_retries', 3)
        delay_seconds = policy.get('restart_delay_seconds', 10)
    else:
        if max_retries is None:
            max_retries = 3
        delay_seconds = 10
    
    attempts = []
    template = COMMAND_TEMPLATES["RESTART"]
    cmd = template.format(container_name=container_name)
    
    for attempt in range(1, max_retries + 1):
        attempt_result = {
            "attempt": attempt,
            "timestamp": datetime.now().isoformat()
        }
        
        # 执行重启
        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                attempt_result["restart_success"] = False
                attempt_result["error"] = result.stderr.strip()
                attempts.append(attempt_result)
                continue
            
            attempt_result["restart_success"] = True
            
        except Exception as e:
            attempt_result["restart_success"] = False
            attempt_result["error"] = str(e)
            attempts.append(attempt_result)
            continue
        
        # 等待容器启动
        time.sleep(delay_seconds)
        
        # 检测容器状态
        info = get_container_info(container_name)
        if not info or not info.get("running"):
            attempt_result["running"] = False
            attempt_result["reason"] = "容器未运行"
            attempts.append(attempt_result)
            continue
        
        attempt_result["running"] = True
        
        # 获取资源使用
        stats = get_container_stats(container_name)
        if stats is None:
            attempt_result["success"] = False
            attempt_result["reason"] = "无法获取容器资源状态"
            attempts.append(attempt_result)
            continue

        cpu_str = stats.get("cpu_percent")
        mem_str = stats.get("memory_percent")
        
        if cpu_str is None or mem_str is None:
            attempt_result["success"] = False
            attempt_result["reason"] = "容器资源数据不完整"
            attempts.append(attempt_result)
            continue
            
        from .evidence import parse_percent
        cpu_val = parse_percent(cpu_str)
        mem_val = parse_percent(mem_str)
        
        attempt_result["cpu_percent"] = cpu_str
        attempt_result["memory_percent"] = mem_str
        
        # 健康检查
        health_result = {"healthy": True, "message": ""}
        if container_config and container_config.health_check:
            health_result = check_container_health(container_name, container_config.health_check)
        
        attempt_result["health_check"] = health_result
        
        # 失败原因标记 (0: 正常, 1: 不健康, 2: 高CPU, 3: 高内存)
        failure_flag = 0
        failure_reason = ""
        
        if not health_result.get("healthy", True):
            failure_flag = 1
            failure_reason = f"健康检查失败: {health_result.get('message')}"
        elif cpu_val > 65:
            failure_flag = 2
            failure_reason = f"CPU 使用率过高 ({cpu_str} > 65%)"
        elif mem_val > 65:
            failure_flag = 3
            failure_reason = f"内存使用率过高 ({mem_str} > 65%)"
            
        if failure_flag > 0:
            attempt_result["success"] = False
            attempt_result["failure_flag"] = failure_flag
            attempt_result["reason"] = failure_reason
            attempts.append(attempt_result)
            continue
            
        attempts.append(attempt_result)
        
        # 成功恢复
        return {
            "success": True,
            "action": "RESTART",
            "container": container_name,
            "is_recovered": True,
            "total_attempts": attempt,
            "attempts": attempts,
            "timestamp": datetime.now().isoformat()
        }
    
    # 所有重试失败，停止容器
    stop_result = _execute_single_command("STOP", container_name, COMMAND_TEMPLATES["STOP"])
    
    return {
        "success": False,
        "action": "RESTART",
        "container": container_name,
        "is_recovered": False,
        "total_attempts": max_retries,
        "attempts": attempts,
        "final_action": "STOP",
        "stop_result": stop_result,
        "reason": f"重启 {max_retries} 次后仍未恢复，已停止容器",
        "timestamp": datetime.now().isoformat()
    }


def _execute_commit(container_name: str) -> Dict[str, Any]:
    """
    执行容器取证 (Commit)
    1. 导出运行时状态 (ps, netstat, env) 到容器内临时文件
    2. 执行 docker commit 生成镜像
    3. 停止容器
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    image_name = f"forensics_{container_name}_{timestamp}"
    
    # 1. 导出运行时状态 (Runtime Dump)
    # 尝试在容器内执行命令，将结果写入 /tmp/forensics_dump.txt
    # 注意：如果容器内没有 ps/netstat 命令，可能会失败，但这不影响 commit
    dump_cmds = [
        "echo '=== PROCESSES ===' > /tmp/forensics_dump.txt",
        "ps auxf >> /tmp/forensics_dump.txt || ps -ef >> /tmp/forensics_dump.txt || echo 'ps failed' >> /tmp/forensics_dump.txt",
        "echo '\n=== NETWORK ===' >> /tmp/forensics_dump.txt",
        "netstat -anp >> /tmp/forensics_dump.txt || ss -anp >> /tmp/forensics_dump.txt || echo 'netstat failed' >> /tmp/forensics_dump.txt",
        "echo '\n=== ENV ===' >> /tmp/forensics_dump.txt",
        "env >> /tmp/forensics_dump.txt"
    ]
    
    dump_cmd_str = " && ".join(dump_cmds)
    
    try:
        subprocess.run(
            f"docker exec {container_name} sh -c \"{dump_cmd_str}\"",
            shell=True,
            timeout=10,
            capture_output=True
        )
    except Exception as e:
        # 即使 dump 失败，也要继续 commit
        pass

    # 2. 执行 Commit
    commit_cmd = f"docker commit {container_name} {image_name}"
    try:
        result = subprocess.run(
            commit_cmd.split(),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        commit_success = result.returncode == 0
        
        # 3. 停止容器 (隔离)
        stop_result = _execute_single_command("STOP", container_name, COMMAND_TEMPLATES["STOP"])
        
        return {
            "success": commit_success,
            "action": "COMMIT",
            "container": container_name,
            "image_name": image_name if commit_success else None,
            "stop_result": stop_result,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "action": "COMMIT",
            "container": container_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def check_docker_permission() -> bool:
    """检查 Docker 执行权限"""
    try:
        result = subprocess.run(
            ['docker', 'ps'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

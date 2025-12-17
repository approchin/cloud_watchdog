"""
Docker 监控模块
"""
import subprocess
import time
import json
import requests
import logging
import select
from datetime import datetime, timedelta
from typing import Dict, Any, List
from threading import Thread, Event
from collections import deque

from .config import get_config
from .evidence import (
    collect_evidence, 
    get_container_info, 
    get_container_stats,
    check_container_health,
    parse_percent,
    parse_memory_mb,
    get_container_logs
)
from . import security

logger = logging.getLogger(__name__)


class ContainerMonitor:
    """容器监控器"""
    
    def __init__(self):
        self.config = get_config()
        self.stop_event = Event()
        self.threads: List[Thread] = []
        
        # 趋势分析历史数据 {container_name: deque([(time, mem_mb), ...])}
        self.stats_history: Dict[str, deque] = {}
        
        # 熔断和去重状态
        self.report_history: Dict[str, List[datetime]] = {}  # 容器上报历史
        self.circuit_breaker_until: Dict[str, datetime] = {}  # 熔断截止时间
        self.last_report_time: Dict[str, datetime] = {}  # 最后上报时间（去重）
        
        # 构建容器名称集合，提升 _is_monitored 查询效率
        self._monitored_names: set = {c.name for c in self.config.containers}
    
    def start(self):
        """启动监控"""
        logger.info("启动容器监控...")
        
        polling_thread = Thread(target=self._polling_loop, daemon=True)
        polling_thread.start()
        self.threads.append(polling_thread)
        
        events_thread = Thread(target=self._events_loop, daemon=True)
        events_thread.start()
        self.threads.append(events_thread)
        
        logger.info("监控已启动")
    
    def stop(self):
        """停止监控"""
        logger.info("停止容器监控...")
        # event.set + thread.join = 优雅退出 让线程有充分时间善后
        # stop_event.set() -> 通知线程退出 -> join() 等待线程结束
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)
        logger.info("监控已停止")
    
    def _polling_loop(self):
        """定时轮询检查"""
        check_count = 0
        
        while not self.stop_event.is_set():
            try:
                check_count += 1
                self._check_all_containers_alive()
                
                resource_interval = self.config.system.resource_check_interval_seconds // self.config.system.check_interval_seconds
                if check_count % max(1, resource_interval) == 0:
                    self._check_all_containers_resources()
                
            except Exception as e:
                logger.error(f"轮询检查异常: {e}")
            
            self.stop_event.wait(self.config.system.check_interval_seconds)
    
    def _events_loop(self):
        """Docker 事件监听"""
        while not self.stop_event.is_set():
            try:
                process = subprocess.Popen(
                    ['docker', 'events', '--format', '{{json .}}',
                     '--filter', 'type=container',
                     '--filter', 'event=die',
                     '--filter', 'event=oom'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                
                while not self.stop_event.is_set():
                    # 使用 select 设置超时，避免阻塞
                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if ready:
                        line = process.stdout.readline()
                        if not line:
                            break
                        
                        try:
                            event = json.loads(line.strip())
                            self._handle_docker_event(event)
                        except json.JSONDecodeError:
                            continue
                    elif process.poll() is not None:
                        # 进程已退出
                        break
                
                process.terminate()
                process.wait()
                
            except Exception as e:
                logger.error(f"Docker 事件监听异常: {e}")
                time.sleep(5)
    
    def _handle_docker_event(self, event: Dict[str, Any]):
        """处理 Docker 事件"""
        action = event.get("Action", "")
        actor = event.get("Actor", {})
        attributes = actor.get("Attributes", {})
        container_name = attributes.get("name", "")
        
        if not self._is_monitored(container_name):
            return
        
        logger.warning(f"检测到容器事件: {container_name} - {action}")
        
        if action == "oom":
            fault_type = "OOM_KILLED"
        elif action == "die":
            exit_code = attributes.get("exitCode", "0")
            fault_type = "OOM_KILLED" if exit_code == "137" else "PROCESS_CRASH"
        else:
            fault_type = "UNKNOWN"
        
        self._report_issue(container_name, fault_type)
    
    def _check_all_containers_alive(self):
        """检查所有监控容器的存活状态"""
        for container_config in self.config.containers:
            container_name = container_config.name
            
            try:
                info = get_container_info(container_name)
                
                if info is None:
                    logger.warning(f"容器不存在: {container_name}")
                    continue
                
                if not info.get("running", False):
                    logger.warning(f"容器未运行: {container_name}")
                    self._report_issue(container_name, "PROCESS_CRASH")
                    continue
                
                if container_config.health_check:
                    health = check_container_health(container_name, container_config.health_check)
                    if not health.get("healthy", True):
                        logger.warning(f"容器健康检查失败: {container_name}")
                        self._report_issue(container_name, "HEALTH_FAIL")
                
            except Exception as e:
                logger.error(f"检查容器 {container_name} 失败: {e}")
    
    def _check_all_containers_resources(self):
        """检查所有监控容器的资源使用"""
        for container_config in self.config.containers:
            container_name = container_config.name
            
            try:
                stats = get_container_stats(container_name)
                if stats is None:
                    logger.warning(f"无法获取容器 {container_name} 的资源状态，跳过本次检查")
                    continue
                
                cpu_str = stats.get("cpu_percent")
                memory_str = stats.get("memory_percent")
                
                if cpu_str is None or memory_str is None:
                    logger.warning(f"容器 {container_name} 资源数据不完整")
                    continue
                
                cpu_percent = parse_percent(cpu_str)
                memory_percent = parse_percent(memory_str)
                memory_mb = parse_memory_mb(stats.get("memory_usage", "0MB"))
                
                # 趋势分析
                self._check_trend(container_name, memory_mb, memory_percent)
                
                # 安全检查
                self._check_security(container_name)
                
                thresholds = container_config.thresholds or {}
                cpu_critical = thresholds.get("cpu_percent_critical", self.config.thresholds.cpu_critical)
                memory_critical = thresholds.get("memory_percent_critical", self.config.thresholds.memory_critical)
                
                if cpu_percent >= cpu_critical:
                    logger.warning(f"容器 CPU 严重超标: {container_name} - {cpu_percent}%")
                    self._report_issue(container_name, "CPU_HIGH")
                
                if memory_percent >= memory_critical:
                    logger.warning(f"容器内存严重超标: {container_name} - {memory_percent}%")
                    self._report_issue(container_name, "MEMORY_HIGH")
                
            except Exception as e:
                logger.error(f"检查容器资源 {container_name} 失败: {e}")

    def _check_trend(self, container_name: str, memory_mb: float, memory_percent: float):
        """
        分析内存增长趋势 (Trend Analysis)
        如果发现内存持续快速增长，且占用率较高，则报警
        """
        if container_name not in self.stats_history:
            self.stats_history[container_name] = deque(maxlen=10)  # 保留最近10次记录
        
        history = self.stats_history[container_name]
        now = datetime.now()
        history.append((now, memory_mb))
        
        # 至少需要3个点，且跨度超过1分钟才开始分析
        if len(history) < 3:
            return
            
        first_time, first_mem = history[0]
        last_time, last_mem = history[-1]
        
        time_diff_minutes = (last_time - first_time).total_seconds() / 60.0
        if time_diff_minutes < 1.0:
            return
            
        # 计算斜率 (MB/min)
        slope = (last_mem - first_mem) / time_diff_minutes
        
        # 阈值：增长速度 > 10MB/min 且 内存占用 > 50%
        # 注意：这里应该从配置读取，暂时硬编码作为演示
        if slope > 10.0 and memory_percent > 50.0:
            logger.warning(f"检测到内存泄漏趋势: {container_name} 增长速率 {slope:.2f} MB/min, 当前占用 {memory_percent}%")
            # 使用特殊的故障类型，触发 Agent 的分析逻辑
            self._report_issue(container_name, "MEMORY_LEAK_SUSPECTED")

    def _check_security(self, container_name: str):
        """
        执行安全检查 (Security Forensics)
        1. 检查日志中的攻击特征 (SQL注入, XSS等)
        2. 检查异常进程 (挖矿, 反弹shell等)
        """
        # 1. 日志检查
        logs = get_container_logs(container_name, 100)
        injection_patterns = security.check_logs_for_injection(logs)
        if injection_patterns:
            logger.warning(f"检测到攻击日志: {container_name} - {injection_patterns}")
            # 触发 Agent 分析，故障类型为 SECURITY_LOG_ALERT
            self._report_issue(container_name, "SECURITY_LOG_ALERT")
            
        # 2. 进程检查
        malicious_procs = security.check_processes(container_name)
        if malicious_procs:
            logger.critical(f"检测到恶意进程: {container_name} - {malicious_procs}")
            # 触发 Agent 分析，故障类型为 MALICIOUS_PROCESS
            self._report_issue(container_name, "MALICIOUS_PROCESS")

    def _is_monitored(self, container_name: str) -> bool:
        """检查容器是否在监控列表中（O(1) 查询）"""
        return container_name in self._monitored_names
    
    def _should_report(self, container_name: str, fault_type: str) -> bool:
        """
        检查是否应该上报（熔断 + 去重逻辑）
        
        返回 True 表示可以上报，False 表示跳过
        """
        now = datetime.now()
        cb_config = self.config.circuit_breaker
        
        # 1. 检查是否在熔断冷却期
        if container_name in self.circuit_breaker_until:
            until = self.circuit_breaker_until[container_name]
            if now < until:
                logger.warning(f"容器 {container_name} 处于熔断状态，跳过上报（剩余 {(until - now).seconds} 秒）")
                return False
            else:
                # 冷却期结束，清除熔断状态
                del self.circuit_breaker_until[container_name]
                self.report_history[container_name] = []
                logger.info(f"容器 {container_name} 熔断冷却期结束，恢复上报")
        
        # 2. 去重：短时间内同一问题不重复上报（使用 cooldown_seconds）
        cooldown = cb_config.cooldown_seconds
        if container_name in self.last_report_time:
            elapsed = (now - self.last_report_time[container_name]).total_seconds()
            if elapsed < cooldown:
                logger.debug(f"容器 {container_name} 距上次上报仅 {elapsed:.0f} 秒，跳过（冷却 {cooldown} 秒）")
                return False
        
        # 3. 检查时间窗口内上报次数，决定是否触发熔断
        if container_name not in self.report_history:
            self.report_history[container_name] = []
        
        # 清理过期记录
        window_start = now - timedelta(seconds=cb_config.window_seconds)
        self.report_history[container_name] = [
            t for t in self.report_history[container_name] if t > window_start
        ]
        
        # 检查是否达到阈值
        if len(self.report_history[container_name]) >= cb_config.max_restart_attempts:
            # 触发熔断
            self.circuit_breaker_until[container_name] = now + timedelta(seconds=cb_config.window_seconds)
            logger.error(f"容器 {container_name} 在 {cb_config.window_seconds} 秒内上报 {cb_config.max_restart_attempts} 次，触发熔断！")
            return False
        
        return True
    
    def _record_report(self, container_name: str):
        """记录上报"""
        now = datetime.now()
        self.last_report_time[container_name] = now
        if container_name not in self.report_history:
            self.report_history[container_name] = []
        self.report_history[container_name].append(now)
    
    def _report_issue(self, container_name: str, fault_type: str):
        """触发诊断和处理流程（使用 LangGraph Agent）"""
        # 熔断 + 去重检查
        if not self._should_report(container_name, fault_type):
            return
        
        try:
            # 收集证据
            evidence = collect_evidence(container_name, fault_type)
            
            logger.info(f"触发诊断: {container_name} - {fault_type}")
            
            # 使用 LangGraph Agent 进行诊断和处理（异步模式）
            from .agent import run_diagnosis
            run_diagnosis(evidence, async_mode=True)
            
            # 记录上报时间（用于熔断和去重）
            self._record_report(container_name)
            logger.info(f"诊断任务已提交: {container_name}")
                
        except Exception as e:
            logger.error(f"触发诊断异常: {e}")


_monitor_instance = None

def start_monitor():
    """启动监控（便捷函数）"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ContainerMonitor()
        _monitor_instance.start()
    return _monitor_instance

def stop_monitor():
    global _monitor_instance
    if _monitor_instance is not None:
        _monitor_instance.stop()
        _monitor_instance = None

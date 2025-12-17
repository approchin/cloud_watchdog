# Cloud Watchdog 代码审阅问题清单

## 问题 1：readline 阻塞导致无法优雅退出

**文件：** `watchdog/monitor.py`

**位置：** `_events_loop` 方法

**问题描述：**
```python
while not self.stop_event.is_set():
    line = process.stdout.readline()  # 阻塞调用！
```

`readline()` 是阻塞调用，当没有 docker 事件时会一直等待。即使 `stop_event.set()` 被调用，线程也无法立即响应，因为它卡在 `readline()` 上。

**影响：**
- 优雅退出失败，`join(timeout=5)` 超时
- `process.terminate()` 和 `process.wait()` 可能未执行
- docker events 子进程可能变成孤儿进程

**建议修复：**
```python
import select

def _events_loop(self):
    while not self.stop_event.is_set():
        process = subprocess.Popen(...)
        
        while not self.stop_event.is_set():
            # 使用 select 设置超时
            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if ready:
                line = process.stdout.readline()
                if not line:
                    break
                # 处理事件...
            # 如果没有数据，循环继续，可以检查 stop_event
        
        process.terminate()
        process.wait()
```

**严重程度：** 中

---

## 问题 2：获取容器状态失败时使用默认值 0%

**文件：** `watchdog/monitor.py`

**位置：** `_check_all_containers_resources` 方法

**问题描述：**
```python
cpu_percent = parse_percent(stats.get("cpu_percent", "0%"))
memory_percent = parse_percent(stats.get("memory_percent", "0%"))
```

当 docker stats 获取失败时，使用 "0%" 作为默认值。这会导致监控系统把"获取失败"误判为"资源使用正常"。

**影响：**
- 容器可能已经出问题（无法获取状态），但监控认为一切正常
- 隐藏了潜在的故障

**建议修复：**
```python
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
```

**严重程度：** 中

---

## 问题 3：start_monitor 函数缺少单例保护

**文件：** `watchdog/monitor.py`

**位置：** `start_monitor` 函数

**问题描述：**
```python
def start_monitor():
    monitor = ContainerMonitor()
    monitor.start()
    return monitor
```

每次调用都会创建新的监控器实例，如果被多次调用会导致重复监控。

**建议修复：**
```python
_monitor_instance = None

def start_monitor():
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
```

**严重程度：** 低

---

## 问题 4：配置文件硬编码敏感信息

**文件：** `config/config.yml`

**问题描述：**
```yaml
api_key: "sk-76dac455bfa34a5d8c6b37d84e08ee60"
password: "kwetgithifdodeje"
```

API Key 和邮箱密码直接写在配置文件中，如果代码上传到 Git 仓库会导致密钥泄露。

**建议修复：**
```yaml
api_key: "${DEEPSEEK_API_KEY}"
password: "${EMAIL_PASSWORD}"
```

并确保 `_resolve_env` 函数被正确调用。

**严重程度：** 高

---

## 问题 5：Windows 平台兼容性问题

**文件：** `watchdog/main.py`

**问题描述：**
1. Windows 不支持 SIGTERM 信号
2. Windows 用户没有文件日志

**建议修复：**
```python
signal.signal(signal.SIGINT, signal_handler)
if sys.platform != 'win32':
    signal.signal(signal.SIGTERM, signal_handler)
```

**严重程度：** 低（如果只部署在 Linux 上）

---

---

## 问题 6：security_rules.yml 路径硬编码

**文件：** `watchdog/evidence.py`

**位置：** `_load_security_rules` 函数

**问题描述：**
```python
rule_file = "config/security_rules.yml"
```

路径是相对于当前工作目录的，如果程序从其他目录启动会找不到文件。

**建议修复：**
```python
import os
# 使用相对于模块的路径
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rule_file = os.path.join(base_dir, "config", "security_rules.yml")
```

**严重程度：** 中

---

## 问题 7：netstat 解析逻辑有 bug

**文件：** `watchdog/evidence.py`

**位置：** `get_network_connections` 函数

**问题描述：**
```python
for line in lines[2:]:  # 跳过 header
    parts = line.split()
    if len(parts) >= 5 and parts[5] == 'ESTABLISHED':
```

问题：
1. 跳过 2 行 header，但 netstat 输出格式可能不同（有的只有 1 行 header）
2. `parts[5]` 索引可能越界（检查 `len(parts) >= 5` 但访问 `parts[5]` 需要 `len >= 6`）
3. 不同系统的 netstat 输出格式不同

**建议修复：**
```python
if len(parts) >= 6 and parts[5] == 'ESTABLISHED':
    # 或者使用更健壮的解析方式
```

**严重程度：** 中

---

## 问题 8：command.split() 不安全

**文件：** `watchdog/evidence.py`

**位置：** `_check_command_health` 函数

**问题描述：**
```python
code, stdout, stderr = run_command(
    ['docker', 'exec', container_name] + command.split(),
    timeout=timeout
)
```

`command.split()` 无法正确处理带引号的参数，例如：
- `echo "hello world"` 会被拆成 `['echo', '"hello', 'world"']`

**建议修复：**
```python
import shlex
code, stdout, stderr = run_command(
    ['docker', 'exec', container_name] + shlex.split(command),
    timeout=timeout
)
```

**严重程度：** 低

---

## 问题 6：check_count 无限增长

**文件：** `watchdog/monitor.py`

**位置：** `_polling_loop` 方法

**问题描述：**
```python
check_count = 0
while not self.stop_event.is_set():
    check_count += 1  # 永远增长，虽然 Python 整数无上限，但不是好习惯
```

**建议修复：**
```python
check_count = 0
while not self.stop_event.is_set():
    check_count += 1
    if check_count % resource_interval == 0:
        self._check_all_containers_resources()
        check_count = 0  # 重置
```

**严重程度：** 低（实际影响很小，但代码规范问题）

---

## 待确认问题

- [ ] docker stats 在什么情况下会返回 None？需要在服务器上测试
- [ ] 熔断状态是否需要持久化到文件？当前重启后会丢失
- [ ] security_rules.yml 文件是否存在？如果不存在，默认规则是否足够？

---

## 问题 9：generate_daily_summary 使用错误的参数名

**文件：** `watchdog/agent.py`

**位置：** `generate_daily_summary` 函数

**问题描述：**
```python
llm = ChatOpenAI(
    model=config.llm.model_name,  # 错误！应该是 model
    temperature=0.3,
    openai_api_key=config.llm.api_key,  # 错误！应该是 api_key
    openai_api_base=config.llm.base_url  # 错误！应该是 base_url
)
```

但在 `analyze_evidence` 函数中使用的是：
```python
llm = ChatOpenAI(
    model=config.llm.model,  # 正确
    api_key=config.llm.api_key,  # 正确
    base_url=config.llm.base_url,  # 正确
)
```

两处代码不一致，`generate_daily_summary` 使用了错误的参数名。

**建议修复：**
```python
llm = ChatOpenAI(
    model=config.llm.model,
    api_key=config.llm.api_key,
    base_url=config.llm.base_url,
    temperature=0.3,
    timeout=config.llm.timeout_seconds,
    max_retries=config.llm.max_retries
)
```

**严重程度：** 高（会导致每日报告功能完全失败）

---

## 问题 10：history.jsonl 路径硬编码

**文件：** `watchdog/agent.py`

**位置：** `_append_to_history` 和 `generate_daily_summary` 函数

**问题描述：**
```python
history_file = "data/history.jsonl"
```

与问题 6 相同，相对路径在不同工作目录下会出问题。

**严重程度：** 中

---

## 问题 11：DiagnosisTaskQueue.stop() 未使用标准多线程退出方法

**文件：** `watchdog/agent.py`

**位置：** `DiagnosisTaskQueue.stop` 方法

**问题描述：**
```python
def stop(self):
    self.running = False
    while not self.queue.empty():
        try:
            self.queue.get_nowait()
        except:
            break
    logger.info("[TaskQueue] 已停止")
```

没有使用标准的 `stop + join` 多线程等待退出方法。如果工作线程正在执行 LLM 调用（可能需要 10+ 秒），会被强制终止。

**影响：**
- LLM 调用可能被中断
- 诊断结果可能丢失
- 历史记录可能不完整

**建议修复：**
使用标准的 stop + join 模式：
```python
def stop(self):
    self.running = False
    # 标准做法：等待所有工作线程结束
    for worker in self.workers:
        worker.join(timeout=30)  # 最多等 30 秒
    self.workers.clear()
    logger.info("[TaskQueue] 已停止")
```

**严重程度：** 中（可能导致数据丢失）

---

## 问题 12：_append_to_history 中 container_name 字段取值错误

**文件：** `watchdog/agent.py`

**位置：** `_append_to_history` 方法

**问题描述：**
```python
record = {
    "container": result.get("container_name"),  # 但 result 中没有这个字段！
    ...
}
```

查看 `diagnose` 方法的返回值：
```python
return {
    "decision": ...,
    "command": ...,
    "reason": ...,
    ...
}
```

返回的字典中没有 `container_name` 字段，所以 `result.get("container_name")` 永远是 None。

**建议修复：**
在 `diagnose` 返回值中添加 `container_name`：
```python
return {
    "container_name": container_name,  # 添加这行
    "decision": final_state.get("decision", {}),
    ...
}
```

**严重程度：** 中（历史记录中容器名会丢失）

---

## 问题 13：_execute_commit 函数定义了两次

**文件：** `watchdog/executor.py`

**问题描述：**
文件中 `_execute_commit` 函数被定义了两次（第 47 行和第 195 行），第二个定义会覆盖第一个。

两个版本的实现略有不同：
- 第一个版本：生成镜像名格式 `{container_name}_evidence_{timestamp}`
- 第二个版本：生成镜像名格式 `forensics_{container_name}_{timestamp}`，且会自动停止容器

**建议修复：**
删除其中一个，保留功能更完整的版本（第二个）。

**严重程度：** 中（代码冗余，可能导致混淆）

---

## 问题 14：shell=True 存在命令注入风险

**文件：** `watchdog/executor.py`

**位置：** `_execute_commit` 函数（第二个版本）

**问题描述：**
```python
subprocess.run(
    f"docker exec {container_name} sh -c \"{dump_cmd_str}\"",
    shell=True,  # 危险！
    ...
)
```

如果 `container_name` 包含特殊字符（如 `; rm -rf /`），可能导致命令注入。

**建议修复：**
```python
subprocess.run(
    ['docker', 'exec', container_name, 'sh', '-c', dump_cmd_str],
    shell=False,
    ...
)
```

**严重程度：** 高（安全漏洞）

---

## 问题 15：重启后检测阈值与告警阈值不一致

**文件：** `watchdog/executor.py`

**位置：** `_execute_restart_with_retry` 函数

**问题描述：**
```python
elif cpu_val > 65:  # 硬编码 65%
    failure_flag = 2
    failure_reason = f"CPU 使用率过高 ({cpu_str} > 65%)"
elif mem_val > 65:  # 硬编码 65%
    failure_flag = 3
```

但在 agent.py 的 SYSTEM_PROMPT 中：
- CPU 警告阈值：70%
- 内存警告阈值：70%

阈值不一致会导致：重启后 CPU 66% 被判定为"恢复失败"，但正常监控时 66% 不会触发告警。

**建议修复：**
从配置读取阈值，或至少与 SYSTEM_PROMPT 保持一致。

**严重程度：** 中（逻辑不一致）

---

## 问题 16：SMTP 连接未使用 with 语句

**文件：** `watchdog/notifier.py`

**位置：** `send_email` 函数

**问题描述：**
```python
server = smtplib.SMTP_SSL(...)
server.login(...)
server.sendmail(...)
server.quit()
```

如果 `login` 或 `sendmail` 抛出异常，`server.quit()` 不会被执行，导致连接泄漏。

**建议修复：**
```python
try:
    if config.email.use_ssl:
        server = smtplib.SMTP_SSL(config.email.smtp_server, config.email.smtp_port)
    else:
        server = smtplib.SMTP(config.email.smtp_server, config.email.smtp_port)
        server.starttls()
    
    try:
        server.login(config.email.sender, config.email.password)
        server.sendmail(config.email.sender, recipients, msg.as_string())
    finally:
        server.quit()  # 确保关闭连接
```

或使用 contextlib：
```python
from contextlib import contextmanager

@contextmanager
def smtp_connection(config):
    if config.email.use_ssl:
        server = smtplib.SMTP_SSL(...)
    else:
        server = smtplib.SMTP(...)
        server.starttls()
    try:
        yield server
    finally:
        server.quit()
```

**严重程度：** 低（连接泄漏，但不会立即崩溃）

---

## 问题 17：邮件发送没有重试机制

**文件：** `watchdog/notifier.py`

**问题描述：**
邮件发送失败后直接返回错误，没有重试。网络抖动可能导致重要告警丢失。

**建议修复：**
添加简单的重试逻辑：
```python
import time

def send_email(..., max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            # 发送邮件...
            return {"success": True, ...}
        except smtplib.SMTPException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            return {"success": False, "error": str(e)}
```

**严重程度：** 低（可靠性问题）

---

## 问题 18：API 没有认证机制

**文件：** `watchdog/api.py`

**问题描述：**
`/action` 接口可以执行 RESTART/STOP 等危险操作，但没有任何认证。任何能访问这个端口的人都可以停止容器。

**建议修复：**
添加 API Key 认证：
```python
from fastapi import Header, HTTPException, Depends
import os

API_KEY = os.getenv("WATCHDOG_API_KEY", "")

def verify_api_key(x_api_key: str = Header(...)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key

@app.post("/action")
def action_endpoint(request: ActionRequest, api_key: str = Depends(verify_api_key)):
    ...
```

**严重程度：** 高（安全漏洞）

---

## 问题 19：/action 接口没有速率限制

**文件：** `watchdog/api.py`

**问题描述：**
恶意用户可以频繁调用 `/action` 接口，导致容器被反复重启。

**建议修复：**
使用 slowapi 或自定义中间件添加速率限制。

**严重程度：** 中（安全问题）

---

## 问题 20：collect_evidence 违反单一职责原则

**文件：** `watchdog/evidence.py`

**位置：** `collect_evidence` 函数

**问题描述：**
```python
# 新增：安全与网络取证
security_issues = []
injection_patterns = check_logs_for_injection(container_name)
malicious_procs = check_processes(container_name)
active_ips = get_network_connections(container_name)
```

`collect_evidence` 本应只负责收集容器运行状态证据，但混入了：
- 安全日志检查（注入攻击检测）
- 恶意进程检测
- 网络连接分析

这违反了单一职责原则（SRP），导致：
- 函数职责不清晰
- 难以单独测试和维护
- 如果只需要基本证据，也会执行所有安全检查（性能浪费）

**建议修复：**
将安全检查拆分为独立模块：
```python
# evidence.py - 只负责基本证据
def collect_evidence(container_name, fault_type):
    ...

# security.py - 独立的安全检查模块
def collect_security_evidence(container_name):
    return {
        "injection_patterns": check_logs_for_injection(container_name),
        "malicious_processes": check_processes(container_name),
        "active_connections": get_network_connections(container_name)
    }
```

**严重程度：** 中（架构问题）

---

## 问题 21：collect_evidence 获取失败时使用危险默认值

**文件：** `watchdog/evidence.py`

**位置：** `collect_evidence` 函数

**问题描述：**
```python
container_info = get_container_info(container_name) or {
    "name": container_name,
    "status": "unknown"
}

stats = get_container_stats(container_name) or {
    "cpu_percent": "0%",
    "memory_percent": "0%"
}
```

与问题 2 类似，当获取失败时：
- container_info 返回 "status": "unknown" - 这个还算合理
- stats 返回 "0%" - 这是危险的，把"获取失败"伪装成"资源使用为零"

**影响：**
- LLM Agent 收到的证据包含虚假数据
- 可能导致错误的诊断结论

**建议修复：**
```python
stats = get_container_stats(container_name)
if stats is None:
    stats = {
        "cpu_percent": "N/A",
        "memory_percent": "N/A",
        "fetch_failed": True
    }
```

**严重程度：** 中

---

## 问题 22：get_network_connections 依赖容器内 netstat

**文件：** `watchdog/evidence.py`

**位置：** `get_network_connections` 函数

**问题描述：**
```python
code, stdout, stderr = run_command([
    'docker', 'exec', container_name, 
    'netstat', '-ntu'
])
```

代码注释提到"需要容器内有 netstat/ss"，但：
1. 很多精简镜像（alpine、distroless）没有 netstat
2. 如果命令失败，函数静默返回空列表，不报错
3. 没有文档说明这个依赖

**待确认：**
- [ ] 生产环境的容器镜像是否包含 netstat？
- [ ] 如果没有，是否需要改用其他方式（如 nsenter 从宿主机查看）？

**建议修复：**
1. 在部署文档中明确说明依赖
2. 或者添加 fallback 逻辑：
```python
# 先尝试 netstat
code, stdout, stderr = run_command(['docker', 'exec', container_name, 'netstat', '-ntu'])
if code != 0:
    # fallback 到 ss
    code, stdout, stderr = run_command(['docker', 'exec', container_name, 'ss', '-ntu'])
if code != 0:
    logger.warning(f"容器 {container_name} 无法获取网络连接（缺少 netstat/ss）")
    return []
```

**严重程度：** 低（功能降级，不会崩溃）


---

## 问题 23：get_network_connections 去重导致无法检测 DDoS 攻击

**文件：** `watchdog/evidence.py`

**位置：** `get_network_connections` 函数

**问题描述：**
```python
ips = set()  # 使用 set 去重
...
ips.add(ip)
...
return list(ips)  # 返回去重后的 IP 列表
```

**严重问题：**
1. DDoS 攻击时，一个 IP 可能有成千上万个连接
2. 去重后，LLM 只看到"有这个 IP"，看不到"这个 IP 连了 10000 次"
3. 攻击特征被完全隐藏！

**函数名误导：**
- 函数名叫 `get_network_connections`（获取网络连接）
- 实际返回的是"去重后的 IP 列表"
- 名不副实

**影响：**
- LLM 无法识别 DDoS 攻击
- 无法区分正常流量和异常流量
- 安全分析功能形同虚设

**建议修复：**
```python
from collections import Counter

def get_network_connections(container_name: str) -> dict:
    """返回 IP 连接统计，而不是去重列表"""
    ...
    ip_counter = Counter()
    for line in lines:
        # 解析逻辑...
        if ip:
            ip_counter[ip] += 1
    
    return {
        "unique_ips": len(ip_counter),
        "total_connections": sum(ip_counter.values()),
        "top_ips": ip_counter.most_common(10),  # 连接数最多的前10个IP
        "all_ips": dict(ip_counter)
    }
```

这样 LLM 就能看到：
- "192.168.1.100 有 5000 个连接" → 可能是 DDoS
- "总共 50 个 IP，10000 个连接" → 异常

**严重程度：** 高（安全功能失效）


---

## 问题 24：check_container_health 函数名与功能不符

**文件：** `watchdog/evidence.py`

**位置：** `check_container_health` 函数

**问题描述：**
```python
def check_container_health(container_name: str, health_config: Dict):
    if check_type == "http":
        return _check_http_health(health_config)  # 检查的是服务，不是容器！
    elif check_type == "tcp":
        return _check_tcp_health(health_config)   # 检查的是服务，不是容器！
    elif check_type == "command":
        return _check_command_health(...)         # 这才是真正检查容器内部
```

**概念混淆：**
- "容器健康" = 容器进程是否存活、资源是否正常（用 docker inspect/stats）
- "服务健康" = HTTP 端点能否响应、TCP 端口是否可连接

函数名叫 `check_container_health`，但 HTTP/TCP 检查的是**服务层面**，不是容器层面。

**当前建议修复：**
简化函数，只保留真正的容器内部检查：
```python
def check_container_health(container_name: str, health_config: Dict) -> Dict[str, Any]:
    """检查容器内部健康状态（通过 docker exec 执行命令）"""
    command = health_config.get("command", "")
    if not command:
        return {"healthy": True, "message": "无健康检查命令配置"}
    
    expected_output = health_config.get("expected_output", "")
    timeout = health_config.get("timeout_seconds", 5)
    
    code, stdout, stderr = run_command(
        ['docker', 'exec', container_name] + shlex.split(command),
        timeout=timeout
    )
    
    if code == 0 and expected_output in stdout:
        return {"healthy": True, "message": stdout[:100]}
    else:
        return {"healthy": False, "message": f"命令返回: {stdout or stderr}"}
```

删除 `_check_http_health` 和 `_check_tcp_health`，因为它们检查的是服务层面，不属于"容器健康检查"的职责。

**未来优化方向：**
如果需要完整的系统健康检测，应该设计多层次健康检查架构（见下方架构说明）。

**严重程度：** 中（架构设计问题，功能可用但概念混乱）


---

## 问题 25：_worker_loop 异常处理过于宽泛

**文件：** `watchdog/agent.py`

**位置：** `DiagnosisTaskQueue._worker_loop` 方法

**问题描述：**
```python
def _worker_loop(self):
    while self.running:
        try:
            task = self.queue.get(timeout=1)
            self._process_task(agent, task)
            self.queue.task_done()
        except Exception:  # 吞掉所有异常！
            pass
```

`except Exception: pass` 会吞掉所有异常，包括：
- `queue.Empty`（正常情况）
- `KeyError`、`TypeError`（代码 bug）
- `ConnectionError`（网络问题）
- 其他严重错误

导致问题被静默忽略，难以排查。

**建议修复：**
```python
from queue import Empty

def _worker_loop(self):
    agent = DiagnosisAgent()
    
    while self.running:
        try:
            task = self.queue.get(timeout=1)
        except Empty:
            continue  # 队列空，正常情况
        
        try:
            self._process_task(agent, task)
            self.queue.task_done()
        except Exception as e:
            logger.error(f"[TaskQueue] 任务处理失败: {e}", exc_info=True)
```

**严重程度：** 中（影响问题排查）

---

## 问题 26：get_diagnosis_graph 单例有竞态条件（trade-off）

**文件：** `watchdog/agent.py`

**位置：** `get_diagnosis_graph` 函数

**问题描述：**
```python
_diagnosis_graph = None

def get_diagnosis_graph():
    global _diagnosis_graph
    if _diagnosis_graph is None:  # 多线程可能同时进入
        _diagnosis_graph = build_diagnosis_graph()
    return _diagnosis_graph
```

多线程环境下，可能同时创建多个 graph 实例。

**分析：**
这是一个 trade-off 问题：
- graph 资源较小，即使创建多个也不会占用太多资源
- 加锁反而可能降低效率
- 实际场景中并发创建的概率很低

**结论：** 当前实现可接受，记录备查即可。

**严重程度：** 低（可接受的 trade-off）

---

## 问题 27：generate_daily_summary 放在 agent.py 违反单一职责

**文件：** `watchdog/agent.py`

**位置：** `generate_daily_summary` 函数

**问题描述：**
`agent.py` 的职责是"容器故障诊断"，但 `generate_daily_summary` 是"报告生成"功能，两者职责不同。

**当前结构：**
```
agent.py
├── DiagnosisAgent（诊断）
├── DiagnosisTaskQueue（任务队列）
└── generate_daily_summary（报告生成）← 不属于这里
```

**建议修复：**
将报告生成功能拆分到独立模块：
```
watchdog/
├── agent.py          # 只负责诊断
├── reporter.py       # 新文件：报告生成
│   └── generate_daily_summary()
│   └── generate_weekly_summary()
└── scheduler.py      # 新文件：定时任务
```

**严重程度：** 低（架构问题，功能可用）


---

## 问题 28：DiagnosisTaskQueue.stop() 未使用标准多线程退出模式

**文件：** `watchdog/agent.py`

**位置：** `DiagnosisTaskQueue.stop` 方法

**问题描述：**
```python
def stop(self):
    self.running = False
    while not self.queue.empty():
        try:
            self.queue.get_nowait()
        except:
            break
    logger.info("[TaskQueue] 已停止")
```

只设置标志和清空队列，但不等待工作线程真正结束。如果工作线程正在执行 LLM 调用（可能需要 10+ 秒），会被 daemon 线程机制强制终止。

**建议修复：**
使用标准的 stop + join 模式：
```python
def stop(self):
    self.running = False
    # 等待所有工作线程结束
    for worker in self.workers:
        worker.join(timeout=30)  # 最多等 30 秒
    self.workers.clear()
    logger.info("[TaskQueue] 已停止")
```

**严重程度：** 中（可能导致任务被中断）


---

## 问题 28：executor 中 stats 获取失败使用 0% 默认值

**文件：** `watchdog/executor.py`

**位置：** `_execute_restart_with_retry` 函数

**问题描述：**
```python
stats = get_container_stats(container_name)
cpu_str = stats.get("cpu_percent", "0%") if stats else "0%"
mem_str = stats.get("memory_percent", "0%") if stats else "0%"
```

与问题 2、21 相同，获取失败时使用 0% 作为默认值，可能导致：
- 重启后实际资源获取失败，但被判定为"资源正常"
- 错误地认为重启成功

**严重程度：** 中

---

## 问题 29：cmd.split() 处理容器名不安全

**文件：** `watchdog/executor.py`

**位置：** `_execute_single_command` 和 `_execute_restart_with_retry` 函数

**问题描述：**
```python
cmd = template.format(container_name=container_name)
result = subprocess.run(cmd.split(), ...)
```

如果容器名包含空格或特殊字符，`split()` 会错误拆分。

**建议修复：**
直接使用列表，不要用字符串模板：
```python
if command == "RESTART":
    cmd = ['docker', 'restart', container_name]
elif command == "STOP":
    cmd = ['docker', 'stop', container_name]
```

**严重程度：** 低（容器名通常不含空格，但不规范）


---

## 问题 30：COMMIT 操作缺乏独立的频率限制

**文件：** `watchdog/monitor.py`, `watchdog/executor.py`

**问题描述：**

COMMIT 是高危操作（生成镜像 + 停止容器），但缺乏独立的防滥用机制：

1. **熔断机制不区分故障类型**：
```python
def _should_report(self, container_name: str, fault_type: str) -> bool:
    # fault_type 参数传进来了，但没有使用！
```

2. **COMMIT 没有独立的频率限制**：
   - 如果攻击者能反复触发安全检测，可能导致：
   - 反复 COMMIT → 磁盘爆满（每次生成一个镜像）
   - 反复 STOP → Self-DoS

3. **没有镜像清理机制**：
   - 取证镜像会一直累积
   - 没有自动清理旧镜像的逻辑

**攻击场景：**
攻击者在容器日志中反复写入恶意进程名（如 "xmrig"），触发 SECURITY_INCIDENT → COMMIT，导致磁盘被镜像填满。

**建议修复：**
```python
# 1. 为 COMMIT 添加独立的频率限制
COMMIT_COOLDOWN_SECONDS = 3600  # 同一容器 1 小时内最多 COMMIT 一次
last_commit_time: Dict[str, datetime] = {}

def _execute_commit(container_name: str):
    if container_name in last_commit_time:
        elapsed = (datetime.now() - last_commit_time[container_name]).seconds
        if elapsed < COMMIT_COOLDOWN_SECONDS:
            return {"success": False, "error": "COMMIT 冷却中"}
    
    # 执行 COMMIT...
    last_commit_time[container_name] = datetime.now()

# 2. 添加镜像清理机制
def cleanup_old_forensics_images(max_age_days: int = 7):
    # 清理超过 N 天的取证镜像
    pass
```

**严重程度：** 高（可能导致 Self-DoS）

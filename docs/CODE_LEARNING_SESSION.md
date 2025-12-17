# Cloud Watchdog 代码学习与审查

> 让我们一起深入理解这个基于 LLM 的容器故障诊断系统的设计思路和代码实现

---

## 📚 学习路线图

```
1. 整体架构理解
   ↓
2. 配置系统设计
   ↓
3. 监控核心实现（双线程）
   ↓
4. 证据收集机制
   ↓
5. 命令执行与重试
   ↓
6. API 接口设计
   ↓
7. 通知系统
   ↓
8. 熔断机制深入
```

---

## 1️⃣ 整体架构理解

### 系统架构图

```
                     ┌─────────────────┐
                     │  Docker Daemon  │
                     └────────┬────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
    docker ps           docker events        docker stats
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  ContainerMonitor  │◄─── config.yml
                    │   (双线程监控)      │◄─── watchlist.yml
                    └─────────┬──────────┘
                              │
                  ┌───────────┼───────────┐
                  │           │           │
                  ▼           ▼           ▼
           轮询线程     事件监听线程    熔断控制
                  │           │           │
                  └───────────┼───────────┘
                              │
                    ┌─────────▼──────────┐
                    │   collect_evidence │
                    │    (证据收集)       │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Dify Workflow    │
                    │    (LLM 诊断)      │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │   FastAPI /action  │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Executor         │
                    │  (RESTART 重试)    │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Notifier         │
                    │   (邮件通知)       │
                    └────────────────────┘
```

### 核心设计思想

**问题**：传统监控系统依赖固定规则，无法应对复杂故障

**解决方案**：引入 LLM 智能决策
1. 监控系统收集完整证据
2. 发送到 Dify Workflow 进行分析
3. LLM 根据证据判断故障类型
4. 返回修复命令（RESTART/STOP）
5. 系统执行命令并验证

---

## 2️⃣ 配置系统设计 (`config.py`)

### 为什么使用 dataclass？

```python
@dataclass
class CircuitBreakerConfig:
    max_restart_attempts: int = 3
    window_seconds: int = 300
    cooldown_seconds: int = 1800
    on_exceed: str = "stop_and_notify"
    state_file: str = "/opt/watchdog/state/breaker_state.json"
```

**设计思想**：
- ✅ **类型安全**：`max_restart_attempts: int` 明确类型
- ✅ **默认值**：新手友好，开箱即用
- ✅ **自动生成方法**：`__init__`, `__repr__` 等
- ✅ **IDE 支持**：自动补全、类型检查

### 配置加载策略

```python
class Config:
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # 默认配置目录：相对于代码位置
            config_dir = Path(__file__).parent.parent / "config"
        
        self.config_dir = Path(config_dir)
        self._load_config()      # 加载主配置
        self._load_watchlist()   # 加载监控列表
```

**为什么这样设计？**
- ✅ **灵活性**：可以指定配置目录，也可以用默认值
- ✅ **可测试性**：单元测试时可以传入测试配置
- ✅ **部署友好**：生产环境可以用 `--config-dir` 参数

### 全局单例模式

```python
_config: Config = None

def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config()
    return _config
```

**为什么用单例？**
- ✅ **避免重复加载**：配置只读取一次
- ✅ **全局访问**：所有模块共享同一份配置
- ❌ **缺点**：单元测试时需要重置

**更好的设计**：依赖注入（DI）
```python
# 推荐但更复杂的方式
class ContainerMonitor:
    def __init__(self, config: Config):
        self.config = config
```

---

## 3️⃣ 监控核心 (`monitor.py`) - 双线程设计

### 为什么用双线程？

**场景一：轮询检测**
- 定期检查所有容器状态（30秒）
- 定期检查资源使用（60秒）
- 适合：状态变化、资源超限

**场景二：事件监听**
- 实时监听 Docker 事件（die/oom）
- 即时响应，无延迟
- 适合：进程崩溃、OOM Kill

**为什么不用单线程？**
- ❌ 轮询会阻塞事件监听
- ❌ 事件可能漏掉（轮询间隙）
- ✅ 双线程：互补，覆盖所有场景

### 线程启动代码

```python
def start(self):
    """启动监控"""
    logger.info("启动容器监控...")
    
    # 线程 1：轮询检测
    polling_thread = Thread(target=self._polling_loop, daemon=True)
    polling_thread.start()
    self.threads.append(polling_thread)
    
    # 线程 2：事件监听
    events_thread = Thread(target=self._events_loop, daemon=True)
    events_thread.start()
    self.threads.append(events_thread)
    
    logger.info("监控已启动")
```

**为什么用 daemon=True？**
- ✅ **守护线程**：主程序退出时自动结束
- ✅ **避免僵尸进程**：不会阻止程序退出
- ❌ **缺点**：强制退出可能丢失数据

**更好的设计**：优雅退出
```python
def stop(self):
    """停止监控"""
    self.stop_event.set()  # 通知线程退出
    for thread in self.threads:
        thread.join(timeout=5)  # 等待线程完成
```

### 轮询线程实现

```python
def _polling_loop(self):
    """定时轮询检查"""
    check_count = 0
    
    while not self.stop_event.is_set():
        try:
            check_count += 1
            self._check_all_containers_alive()  # 每次都检查存活
            
            # 资源检查频率更低（降低系统开销）
            resource_interval = (
                self.config.system.resource_check_interval_seconds 
                // self.config.system.check_interval_seconds
            )
            if check_count % max(1, resource_interval) == 0:
                self._check_all_containers_resources()
            
        except Exception as e:
            logger.error(f"轮询检查异常: {e}")
        
        # 可中断的等待
        self.stop_event.wait(self.config.system.check_interval_seconds)
```

**设计亮点**：
1. **不同检查频率**：存活 30s，资源 60s
2. **可中断等待**：`stop_event.wait()` 比 `time.sleep()` 更优雅
3. **异常不退出**：捕获异常，继续运行

### 事件监听线程

```python
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
                text=True
            )
            
            while not self.stop_event.is_set():
                line = process.stdout.readline()
                if not line:
                    break
                
                event = json.loads(line.strip())
                self._handle_docker_event(event)
            
            process.terminate()
            
        except Exception as e:
            logger.error(f"Docker 事件监听异常: {e}")
            time.sleep(5)  # 失败后等待重试
```

**为什么不用 Docker SDK？**
- ✅ `docker events` 更简单，无需额外依赖
- ✅ JSON 格式易于解析
- ❌ **缺点**：进程管理更复杂

**Docker SDK 方式**（备选）：
```python
import docker
client = docker.from_env()
for event in client.events(decode=True, filters={'type': 'container'}):
    self._handle_docker_event(event)
```

---

## 4️⃣ 证据收集 (`evidence.py`)

### 为什么需要完整证据？

**问题**：传统监控只上报"容器挂了"，LLM 无法判断

**解决方案**：收集完整上下文
```python
evidence = {
    "container": {
        "name": "crash-loop",
        "status": "exited",
        "exit_code": 137,        # 137 = OOM Kill
        "oom_killed": True,      # 关键信息
        "restart_count": 5,
        "memory_limit": 256MB
    },
    "evidence": {
        "cpu_percent": "15%",
        "memory_percent": "98%",  # 接近 100%
        "logs_tail": "OutOfMemoryError..."  # 日志证据
    }
}
```

LLM 看到这些信息后：
- ✅ 识别出 OOM 问题
- ✅ 建议增加内存限制
- ✅ 决定 STOP（而非 RESTART，避免循环）

### 三种健康检查

#### 1. HTTP 健康检查
```python
def _check_http_health(config: Dict) -> Dict[str, Any]:
    endpoint = config.get("endpoint", "")
    expected_status = config.get("expected_status", 200)
    
    with urllib.request.urlopen(endpoint, timeout=5) as response:
        if response.status == expected_status:
            return {"healthy": True}
```

**适用场景**：Web 服务、API 服务

#### 2. TCP 端口检查
```python
def _check_tcp_health(config: Dict) -> Dict[str, Any]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host, port))
    
    return {"healthy": result == 0}
```

**适用场景**：数据库、Redis、消息队列

#### 3. 命令健康检查
```python
def _check_command_health(container_name: str, config: Dict):
    code, stdout, stderr = run_command(
        ['docker', 'exec', container_name] + command.split()
    )
    
    return {"healthy": code == 0 and expected_output in stdout}
```

**适用场景**：自定义检查逻辑

---

## 5️⃣ 命令执行 (`executor.py`) - RESTART 重试机制

### 核心设计：失败重试 + 健康验证

```python
def _execute_restart_with_retry(container_name, config, max_retries=3):
    for attempt in range(1, max_retries + 1):
        # 1. 执行 docker restart
        subprocess.run(['docker', 'restart', container_name])
        
        # 2. 等待容器启动
        time.sleep(delay_seconds)
        
        # 3. 验证容器状态
        info = get_container_info(container_name)
        if not info or not info.get("running"):
            continue  # 失败，进入下一次重试
        
        # 4. 健康检查
        health_result = check_container_health(...)
        if health_result.get("healthy", True):
            return {"success": True, "is_recovered": True}
    
    # 所有重试失败，停止容器
    stop_result = _execute_single_command("STOP", ...)
    return {"success": False, "final_action": "STOP"}
```

**为什么这样设计？**
1. **重试机制**：临时故障可能自动恢复
2. **健康验证**：确保真正恢复，而非假启动
3. **失败降级**：重试无效时停止容器，避免资源浪费

### 白名单设计

```python
COMMAND_TEMPLATES = {
    "RESTART": "docker restart {container_name}",
    "STOP": "docker stop {container_name}",
    "INSPECT": "docker inspect {container_name}",
}

def execute_action(command, container_name):
    if command not in config.executor.allowed_actions:
        return {"success": False, "error": "不允许的操作"}
```

**为什么需要白名单？**
- ✅ **安全性**：防止 LLM 返回危险命令（rm -rf）
- ✅ **可控性**：只执行预定义的安全操作
- ✅ **审计性**：所有操作都有记录

---

## 6️⃣ API 接口 (`api.py`) - FastAPI 设计

### 为什么用 FastAPI？

```python
from fastapi import FastAPI
from pydantic import BaseModel

class ActionRequest(BaseModel):
    command: str
    container_name: str

@app.post("/action")
def action_endpoint(request: ActionRequest):
    result = execute_action(request.command, request.container_name)
    return ActionResponse(**result)
```

**优势**：
- ✅ **自动验证**：Pydantic 自动验证请求格式
- ✅ **自动文档**：访问 `/docs` 查看 Swagger UI
- ✅ **类型安全**：Python 类型提示
- ✅ **高性能**：基于 Starlette 和 Uvicorn

---

## 7️⃣ 熔断机制深入

### 为什么需要熔断？

**问题场景**：
```
18:00:00 容器崩溃 → 上报 Dify → RESTART
18:01:00 容器崩溃 → 上报 Dify → RESTART
18:02:00 容器崩溃 → 上报 Dify → RESTART
...（无限循环）
```

**后果**：
- ❌ 刷爆 Dify API
- ❌ 刷爆邮件
- ❌ 系统资源浪费

### 三层防护

#### 第一层：去重（cooldown）
```python
if container_name in self.last_report_time:
    elapsed = (now - self.last_report_time[container_name]).total_seconds()
    if elapsed < cooldown_seconds:
        return False  # 跳过上报
```

**作用**：短时间内同一问题只上报一次

#### 第二层：时间窗口统计
```python
# 清理过期记录
window_start = now - timedelta(seconds=window_seconds)
self.report_history[container_name] = [
    t for t in self.report_history[container_name] if t > window_start
]

# 检查是否达到阈值
if len(self.report_history[container_name]) >= max_restart_attempts:
    # 触发熔断
```

**作用**：5分钟内重启3次触发熔断

#### 第三层：熔断冷却期
```python
if container_name in self.circuit_breaker_until:
    until = self.circuit_breaker_until[container_name]
    if now < until:
        logger.warning(f"容器处于熔断状态，跳过上报")
        return False
```

**作用**：熔断后30分钟内不上报 Dify，但继续监控

---

## 🎯 代码审查要点

### 优秀设计
1. ✅ **双线程监控**：轮询 + 事件，覆盖全面
2. ✅ **熔断机制**：三层防护，防止刷屏
3. ✅ **重试逻辑**：健康验证 + 失败降级
4. ✅ **白名单设计**：安全可控
5. ✅ **完整证据**：为 LLM 提供足够上下文

### 可改进点
1. ⚠️ **全局单例**：考虑依赖注入
2. ⚠️ **异常处理**：部分场景可以更细致
3. ⚠️ **测试覆盖**：缺少单元测试
4. ⚠️ **配置热更新**：目前需要重启
5. ⚠️ **监控自身**：监控系统本身可能挂掉

---

## 📝 下一步学习

1. **运行项目**：实际体验监控流程
2. **调试代码**：断点调试，理解执行流程
3. **模拟故障**：测试各种故障场景
4. **阅读日志**：理解系统行为
5. **改进代码**：尝试优化某个模块

---

**准备好一起深入代码了吗？从哪个模块开始？**

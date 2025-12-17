# Cloud Watchdog 代码审查指南

**目标**: 兼顾学习和审阅，从底层到高层，理解系统架构

---

## 审查路径总览

```
第1层: 配置层 (理解系统如何被配置)
    ↓
第2层: 数据层 (理解数据如何流动)
    ↓
第3层: 核心决策层 (理解 LangGraph Agent)
    ↓
第4层: 执行层 (理解动作如何被执行)
    ↓
第5层: 监控层 (理解系统如何感知问题)
    ↓
第6层: 入口层 (理解系统如何启动)
```

---

## 第1层: 配置层 ⏱️ 15分钟

### 文件: `watchdog/config.py`

**学习目标**:
- 理解 Python dataclass 的使用
- 理解 YAML 配置加载
- 理解环境变量解析 (`${VAR}` 语法)
- 理解单例模式 (`get_config()`)

**审查要点**:
```python
# 关键类
- LLMConfig        # LLM 配置
- CircuitBreakerConfig  # 熔断配置
- ContainerConfig  # 容器配置
- Config           # 主配置类

# 关键方法
- _resolve_env()   # 环境变量解析
- get_container()  # 获取容器配置
```

**配合文件**:
- `config/config.yml` - 主配置
- `config/watchlist.yml` - 监控容器列表

---

## 第2层: 数据层 ⏱️ 20分钟

### 文件: `watchdog/evidence.py`

**学习目标**:
- 理解 Docker CLI 交互 (`subprocess`)
- 理解 JSON 解析
- 理解数据聚合模式

**审查要点**:
```python
# 核心函数
- get_container_info()   # docker inspect
- get_container_stats()  # docker stats
- get_container_logs()   # docker logs
- collect_evidence()     # 聚合所有证据

# 健康检查
- http_health_check()
- tcp_health_check()
- command_health_check()
```

**数据流**:
```
Docker API → get_container_*() → collect_evidence() → Dict
```

---

## 第3层: 核心决策层 ⭐⭐⭐ ⏱️ 40分钟

### 文件: `watchdog/agent.py`

**这是最重要的文件，体现 LangGraph 架构**

**学习目标**:
- 理解 LangGraph StateGraph
- 理解 TypedDict 状态定义
- 理解节点函数设计
- 理解条件路由

**审查顺序**:

#### 3.1 状态定义
```python
class DiagnosisState(TypedDict):
    evidence: Dict[str, Any]      # 输入
    command: str                  # LLM 决策
    action_result: Optional[...]  # 执行结果
```

#### 3.2 系统提示词
```python
SYSTEM_PROMPT = """你是一个容器故障诊断专家..."""
# 关注: 阈值标准、决策规则、输出格式
```

#### 3.3 节点函数
```python
# 按执行顺序审查
1. analyze_evidence()      # LLM 调用节点
2. execute_action_node()   # 执行操作节点
3. send_alert_node()       # 发送告警节点
4. no_action_node()        # 无操作节点
5. error_handler_node()    # 错误处理节点
```

#### 3.4 条件路由
```python
def route_by_command(state) -> str:
    # 根据 command 决定下一个节点
    # RESTART/STOP → execute_action
    # ALERT_ONLY → send_alert
    # NONE → no_action
```

#### 3.5 Graph 构建
```python
def build_diagnosis_graph():
    workflow = StateGraph(DiagnosisState)
    workflow.add_node(...)
    workflow.add_conditional_edges(...)
    return workflow.compile()
```

**关键理解**:
```
                    ┌─────────────────┐
                    │ analyze_evidence │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ route_by_command │
                    └────────┬────────┘
          ┌──────────────┬───┴───┬──────────────┐
          ▼              ▼       ▼              ▼
    execute_action  send_alert  no_action  error_handler
          │              │       │              │
          └──────────────┴───┬───┴──────────────┘
                             ▼
                            END
```

---

## 第4层: 执行层 ⏱️ 15分钟

### 文件: `watchdog/executor.py`

**学习目标**:
- 理解命令执行模式
- 理解重试机制
- 理解权限检查

**审查要点**:
```python
# 核心函数
- execute_action()         # 执行容器操作
- check_docker_permission()  # 检查 Docker 权限

# 支持的操作
- RESTART: 重启容器
- STOP: 停止容器
- INSPECT: 检查容器
```

### 文件: `watchdog/notifier.py`

**学习目标**:
- 理解邮件发送 (`smtplib`)
- 理解 HTML 模板格式化

**审查要点**:
```python
# 通知类型
- alert: 告警通知
- action_result: 执行结果通知
- recovery: 恢复通知
- circuit_break: 熔断通知
```

---

## 第5层: 监控层 ⏱️ 25分钟

### 文件: `watchdog/monitor.py`

**学习目标**:
- 理解多线程编程 (`threading`)
- 理解 Docker 事件监听
- 理解熔断机制
- 理解去重逻辑

**审查要点**:
```python
class ContainerMonitor:
    # 双线程架构
    - _polling_loop()    # 轮询线程 (定时检查)
    - _events_loop()     # 事件线程 (实时监听)
    
    # 核心方法
    - _report_issue()    # 触发诊断
    - _should_report()   # 熔断+去重检查
    - _handle_docker_event()  # 处理 Docker 事件
```

**关键理解**:
```
Docker Events ─────┐
                   ├──→ _report_issue() ──→ agent.run_diagnosis()
Polling Loop ──────┘
```

---

## 第6层: 入口层 ⏱️ 10分钟

### 文件: `watchdog/main.py`

**学习目标**:
- 理解命令行参数解析 (`argparse`)
- 理解信号处理 (`signal`)
- 理解服务启动流程

**审查要点**:
```python
def main():
    # 1. 解析参数
    # 2. 初始化配置
    # 3. 检查 Docker 权限
    # 4. 启动监控
    # 5. 启动 API 服务
```

### 文件: `watchdog/api.py`

**学习目标**:
- 理解 FastAPI 路由
- 理解 REST API 设计

---

## 审查检查清单

### 代码质量
- [ ] 函数职责单一
- [ ] 错误处理完善
- [ ] 日志记录充分
- [ ] 类型注解完整

### 架构设计
- [ ] LangGraph 节点划分合理
- [ ] 状态流转清晰
- [ ] 扩展性考虑 (多 Agent)

### 安全性
- [ ] API Key 不硬编码
- [ ] 敏感信息不日志输出
- [ ] Docker 操作有权限控制

### 可维护性
- [ ] 配置外部化
- [ ] 常量有注释说明
- [ ] 复杂逻辑有文档

---

## 推荐审查时间: 约 2 小时

| 层级 | 时间 | 重点 |
|-----|------|------|
| 第1层 配置层 | 15分钟 | 快速过 |
| 第2层 数据层 | 20分钟 | 理解证据收集 |
| **第3层 决策层** | **40分钟** | **核心，仔细看** |
| 第4层 执行层 | 15分钟 | 理解动作执行 |
| 第5层 监控层 | 25分钟 | 理解触发机制 |
| 第6层 入口层 | 10分钟 | 快速过 |

---

*准备好了就开始吧！建议从第1层开始，按顺序审查。*

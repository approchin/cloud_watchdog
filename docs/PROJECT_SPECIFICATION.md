# 云原生故障诊断与自愈系统 - 项目规划书

> 项目代号：Cloud Watchdog  
> 版本：v1.0  
> 最后更新：2025-12-01  
> 状态：设计完成，待开发

---

## 目录

1. [项目背景](#1-项目背景)
2. [项目目标](#2-项目目标)
3. [技术选型](#3-技术选型)
4. [系统架构](#4-系统架构)
5. [详细设计](#5-详细设计)
6. [配置规范](#6-配置规范)
7. [接口定义](#7-接口定义)
8. [实施计划](#8-实施计划)
9. [风险评估](#9-风险评估)
10. [验收标准](#10-验收标准)

---

## 1. 项目背景

### 1.1 现状分析

| 项目 | 当前状态 |
|------|----------|
| 服务器环境 | 腾讯云 4核CPU / 3.3GB内存 |
| 容器化程度 | Docker 部署多个业务容器 |
| 监控现状 | 无自动化监控，依赖人工巡检 |
| 故障响应 | 发现问题后人工登录服务器排查 |
| 平均修复时间 | 30分钟 ~ 数小时（取决于人员响应速度） |

### 1.2 痛点问题

1. **响应滞后**：故障发生后无法第一时间发现，依赖用户反馈
2. **排查低效**：每次故障都需要人工登录服务器，重复执行相同的排查命令
3. **知识孤岛**：故障排查经验在个人脑中，无法沉淀和复用
4. **夜间无人值守**：非工作时间故障无法及时处理

### 1.3 方案对比与决策

| 维度 | 方案A：确定性工作流 | 方案B：多智能体协作 |
|------|---------------------|---------------------|
| 核心思路 | SOP 数字化，固定流程 | LLM 推理，动态决策 |
| 技术栈 | Shell + Dify Workflow | CrewAI + DeepSeek API |
| 响应速度 | 秒级 | 15-30秒（多轮推理） |
| 稳定性 | 极高 | 存在幻觉风险 |
| 开发周期 | 1-2周 | 2-3个月 |
| 资源占用 | 极低 | 较高 |
| 可维护性 | 需手动维护流程图 | 自适应但难调试 |

**最终决策**：采用方案A作为第一阶段交付，方案B作为远期演进目标。

**决策理由**：
- 资源受限（3.3GB内存）
- 首次落地需快速验证价值
- 稳定性优先于智能化
- "能跑的系统 > 跑不起来的架构"

---

## 2. 项目目标

### 2.1 核心目标

构建一套能够**自动发现异常、收集证据、执行修复、通知相关人员**的运维自动化系统。

### 2.2 量化指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 故障发现时间 | 10分钟+ | < 1分钟 |
| 平均修复时间（MTTR） | 30分钟+ | < 5分钟（自动修复场景） |
| 人工介入率 | 100% | < 30% |
| 夜间故障响应 | 无 | 100%覆盖 |

### 2.3 项目边界

**本期包含**：
- Docker 容器存活检测
- 容器资源使用监控（CPU/内存）
- 容器自动重启（带熔断机制）
- 飞书/邮箱通知

**本期不包含**：
- 多容器并发故障处理
- 宿主机级别监控
- 日志智能分析（LLM）
- 自定义修复脚本执行

---

## 3. 技术选型

### 3.1 巡检员（Watchdog）

| 候选方案 | 优点 | 缺点 | 结论 |
|----------|------|------|------|
| Shell 脚本 | 极轻量（~5MB） | 复杂逻辑难维护 | ❌ |
| Python 脚本 | 开发快、易调试 | 稍重（~30MB） | ✅ 采用 |
| Go 二进制 | 性能好、单文件 | 开发慢、需编译 | 后期演进 |

**最终选择**：Python 3.x 单文件脚本

**依赖库**：
```
requests>=2.28.0    # HTTP 请求（对接 Dify）
pyyaml>=6.0         # 解析配置文件
```

### 3.2 决策引擎

| 候选方案 | 优点 | 缺点 | 结论 |
|----------|------|------|------|
| 硬编码 if/else | 最简单 | 不可视化、难维护 | ❌ |
| Dify Workflow | 可视化、低代码 | 需部署 Dify 服务 | ✅ 采用 |
| n8n | 功能丰富 | 资源占用大 | ❌ |

**最终选择**：Dify Workflow

**理由**：
- 可视化流程编排
- 支持 Webhook 触发
- 支持 HTTP 节点调用外部接口
- 国产开源，文档友好

### 3.3 通知渠道

| 候选方案 | 实时性 | 接入难度 | 成本 | 结论 |
|----------|--------|----------|------|------|
| 飞书 Webhook | 秒级推送 | 极简 | 免费 | ✅ 主通道 |
| 邮箱 SMTP | 可能延迟 | 中等 | 免费 | ✅ 备用通道 |
| 短信 | 秒级 | 需对接API | 付费 | ❌ 不采用 |
| 企业微信 | 秒级 | 中等 | 免费 | 可选 |

**最终选择**：飞书（主）+ 邮箱（备）

### 3.4 技术栈全景图

```
┌─────────────────────────────────────────────────────────┐
│                     技术栈总览                           │
├─────────────────────────────────────────────────────────┤
│  监控层    │  Python 3.x + docker CLI                   │
│  决策层    │  Dify Workflow (Docker 部署)               │
│  通知层    │  飞书 Webhook + SMTP                       │
│  配置管理  │  YAML 文件                                 │
│  状态存储  │  JSON 文件（熔断状态）                      │
│  容器运行时│  Docker Engine                             │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 系统架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        宿主机 (腾讯云 4C/3.3G)                        │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    巡检员 (watchdog.py)                        │ │
│  │                       内存占用 < 50MB                          │ │
│  │                                                               │ │
│  │  ┌─────────────────┐     ┌─────────────────┐                 │ │
│  │  │  定时轮询线程    │     │  事件监听线程    │                 │ │
│  │  │  (30s/2min)     │     │  (docker events) │                 │ │
│  │  └────────┬────────┘     └────────┬────────┘                 │ │
│  │           │                       │                           │ │
│  │           └───────────┬───────────┘                           │ │
│  │                       ▼                                       │ │
│  │           ┌───────────────────────┐                           │ │
│  │           │ 异常检测 + 强制全量同步│                           │ │
│  │           └───────────┬───────────┘                           │ │
│  │                       ▼                                       │ │
│  │           ┌───────────────────────┐                           │ │
│  │           │ 批量取证模块          │                           │ │
│  │           │ - docker logs         │                           │ │
│  │           │ - docker stats        │                           │ │
│  │           │ - docker inspect      │                           │ │
│  │           └───────────┬───────────┘                           │ │
│  │                       │                                       │ │
│  │                       ▼ HTTP POST                             │ │
│  └───────────────────────┼───────────────────────────────────────┘ │
│                          │                                         │
│  ┌───────────────────────▼───────────────────────────────────────┐ │
│  │                 Dify 工作流容器                                │ │
│  │                                                               │ │
│  │  [Webhook] → [解析证据] → [熔断判断] → [执行动作] → [通知]    │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ 业务容器1 │ │ 业务容器2 │ │ Redis    │ │ Nginx    │   ...       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流图

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 容器异常  │───▶│ 巡检员   │───▶│ 取证     │───▶│ Dify     │───▶│ 通知     │
│          │    │ 检测     │    │ 收集     │    │ 决策     │    │ 用户     │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                     │                               │
                     ▼                               ▼
              ┌──────────┐                    ┌──────────┐
              │ 配置文件  │                    │ 执行动作  │
              │ YAML     │                    │ 重启/停止 │
              └──────────┘                    └──────────┘
```

### 4.3 组件职责

| 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| 事件监听器 | 实时捕获容器状态变化 | docker events | 异常事件 |
| 定时轮询器 | 周期性检查资源使用 | docker stats | 资源数据 |
| 取证模块 | 收集故障现场信息 | 容器名 | 证据包 JSON |
| Dify 工作流 | 决策是否修复及如何修复 | 证据包 | 执行指令 |
| 通知模块 | 发送告警信息 | 告警内容 | 飞书/邮件 |

---

## 5. 详细设计

### 5.1 检测机制

#### 5.1.1 双模式检测

| 模式 | 实现方式 | 触发条件 | 检测内容 |
|------|----------|----------|----------|
| 事件监听 | `docker events --filter` | 容器状态变化 | die, oom, stop |
| 定时轮询 | cron 定时执行 | 每30秒/2分钟 | 存活、资源使用 |

#### 5.1.2 检测指标

| 指标 | 命令 | 阈值（警告） | 阈值（严重） |
|------|------|--------------|--------------|
| 容器存活 | `docker inspect -f '{{.State.Running}}'` | - | false |
| CPU 使用率 | `docker stats --no-stream` | > 80% | > 95% |
| 内存使用率 | `docker stats --no-stream` | > 70% | > 85% |
| 健康检查 | `curl` / `redis-cli ping` | 非预期响应 | 连续3次失败 |

#### 5.1.3 关键逻辑：事件触发强制同步

```
事件监听捕获异常
       │
       ▼
立刻触发全量健康检查（不等待定时器）
       │
       ▼
汇总所有异常容器
       │
       ▼
批量取证并上报
```

**目的**：避免事件监听和定时轮询的时序漏洞，确保不遗漏并发故障。

### 5.2 熔断机制

#### 5.2.1 设计原则

- 容器异常时允许自动重启
- 短时间内反复异常则触发熔断，停止自动操作
- 熔断后必须人工介入

#### 5.2.2 熔断规则

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_restart_attempts | 3 | 最大重启次数 |
| window_seconds | 300 | 计数窗口（5分钟） |
| on_exceed | stop_and_notify | 超限后动作 |

#### 5.2.3 熔断状态机

```
                    ┌─────────┐
                    │  正常   │
                    └────┬────┘
                         │ 发生异常
                         ▼
                    ┌─────────┐
             ┌──────│ 重试中  │◀─────┐
             │      └────┬────┘      │
             │           │           │ 重试成功
             │           │ 重试失败  │ 重置计数
             │           ▼           │
             │      ┌─────────┐      │
             │      │ 计数+1  │──────┘
             │      └────┬────┘
             │           │ 计数 >= 3
             │           ▼
             │      ┌─────────┐
             └──────│  熔断   │
                    └─────────┘
                         │
                         ▼
                    人工介入恢复
```

#### 5.2.4 熔断状态存储

```json
// /var/watchdog/breaker_state.json
{
  "app-backend": {
    "restart_count": 2,
    "last_restart_time": "2025-12-01T15:30:00Z",
    "status": "warning"
  },
  "redis-cache": {
    "restart_count": 3,
    "last_restart_time": "2025-12-01T15:35:00Z",
    "status": "circuit_break"
  }
}
```

### 5.3 取证模块

#### 5.3.1 取证内容

| 证据类型 | 命令 | 用途 |
|----------|------|------|
| 容器日志 | `docker logs --tail 50` | 分析错误原因 |
| 资源快照 | `docker stats --no-stream` | 确认资源状态 |
| 容器详情 | `docker inspect` | 获取配置和状态 |
| 退出码 | `docker inspect -f '{{.State.ExitCode}}'` | 判断异常类型 |

#### 5.3.2 证据包格式

```json
{
  "event_id": "evt_20251201_153000_abc123",
  "timestamp": "2025-12-01T15:30:00Z",
  "host": "tencent-cloud-001",
  "issues": [
    {
      "container": {
        "name": "app-backend",
        "id": "abc123def456",
        "image": "myapp:v1.2.0"
      },
      "fault_type": "CONTAINER_DIED",
      "severity": "critical",
      "evidence": {
        "exit_code": 137,
        "logs_tail": "... killed by OOM ...",
        "last_stats": {
          "cpu_percent": "2.5%",
          "memory_usage": "512MiB / 512MiB",
          "memory_percent": "100%"
        },
        "restart_count": 1,
        "breaker_status": "warning"
      }
    }
  ]
}
```

### 5.4 Dify 工作流设计

#### 5.4.1 节点列表

| 节点序号 | 节点类型 | 节点名称 | 功能 |
|----------|----------|----------|------|
| 1 | Webhook | 接收告警 | 接收巡检员的 HTTP POST |
| 2 | Code | 解析证据 | 解析 JSON，提取关键信息 |
| 3 | Condition | 熔断判断 | 判断是否已熔断 |
| 4 | Condition | 故障类型判断 | 区分 died/resource/health |
| 5 | HTTP Request | 执行重启 | 调用 Docker API 或 SSH |
| 6 | Code | 更新熔断计数 | 写入状态文件 |
| 7 | HTTP Request | 发送飞书 | 调用飞书 Webhook |
| 8 | HTTP Request | 发送邮件（备用） | 调用邮件 API |
| 9 | End | 结束 | 流程结束 |

#### 5.4.2 决策逻辑流程图

```
[Webhook 接收]
      │
      ▼
[解析证据包]
      │
      ▼
[遍历每个异常容器]
      │
      ├──▶ 已熔断？ ──是──▶ [跳过，记录日志]
      │         │
      │        否
      │         ▼
      │    [查询重启计数]
      │         │
      │         ├──▶ 计数 >= 3？ ──是──▶ [标记熔断] ──▶ [生成严重告警]
      │         │                                              │
      │        否                                              │
      │         ▼                                              │
      │    [故障类型判断]                                       │
      │         │                                              │
      │         ├── DIED ──▶ [执行重启] ──▶ [计数+1]           │
      │         │                              │               │
      │         ├── RESOURCE ──▶ [仅告警，不重启]              │
      │         │                              │               │
      │         └── HEALTH ──▶ [执行重启] ──▶ [计数+1]         │
      │                                        │               │
      │                                        ▼               │
      │                              [等待30秒验证]            │
      │                                        │               │
      │                              恢复？─是─▶ [重置计数]    │
      │                                   │                    │
      │                                  否                    │
      │                                   ▼                    │
      └───────────────────────────────────┴────────────────────┘
                                          │
                                          ▼
                                   [汇总处理结果]
                                          │
                                          ▼
                                   [生成通知内容]
                                          │
                                          ▼
                                   [发送飞书通知]
                                          │
                                     失败？─是─▶ [发送邮件备用]
                                          │
                                          ▼
                                       [结束]
```

### 5.5 通知模块

#### 5.5.1 飞书消息卡片格式

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {"content": "🚨 容器异常告警", "tag": "plain_text"},
      "template": "red"
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**服务器**: tencent-cloud-001\n**时间**: 2025-12-01 15:30:00"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**异常容器**: app-backend\n**故障类型**: 容器崩溃 (OOM Killed)\n**处理结果**: 已自动重启 (第2次)"
        }
      },
      {
        "tag": "note",
        "elements": [
          {"tag": "plain_text", "content": "⚠️ 该容器已重启2次，再次异常将触发熔断"}
        ]
      }
    ]
  }
}
```

#### 5.5.2 通知级别

| 级别 | 触发条件 | 通知内容 |
|------|----------|----------|
| INFO | 自动修复成功 | 简短通知，已恢复 |
| WARNING | 重启次数 >= 2 | 提醒关注 |
| CRITICAL | 熔断触发 | 需要人工介入 |

---

## 6. 配置规范

### 6.1 目录结构

```
/opt/watchdog/
├── watchdog.py           # 巡检员主程序
├── config/
│   ├── config.yml        # 全局配置
│   └── watchlist.yml     # 监控容器清单
├── state/
│   └── breaker_state.json # 熔断状态存储
├── logs/
│   └── watchdog.log      # 运行日志
└── requirements.txt      # Python 依赖
```

### 6.2 config.yml 完整定义

```yaml
# ============================================
# Cloud Watchdog 全局配置
# ============================================

# 系统配置
system:
  # 轻量检查间隔（秒）- 检查容器存活
  check_interval_seconds: 30
  
  # 资源检查间隔（秒）- 检查 CPU/内存
  resource_check_interval_seconds: 120
  
  # 取证时抓取日志行数
  evidence_log_lines: 50
  
  # 日志级别：DEBUG, INFO, WARNING, ERROR
  log_level: "INFO"
  
  # 日志文件路径
  log_file: "/opt/watchdog/logs/watchdog.log"

# 熔断策略
circuit_breaker:
  # 最大重启次数
  max_restart_attempts: 3
  
  # 计数窗口（秒）- 超过此时间重置计数
  window_seconds: 300
  
  # 超限后动作：stop_and_notify / notify_only
  on_exceed: "stop_and_notify"
  
  # 状态文件路径
  state_file: "/opt/watchdog/state/breaker_state.json"

# Dify 对接配置
dify:
  # Webhook URL
  webhook_url: "http://localhost:8080/v1/workflows/webhook/xxx"
  
  # API Key（建议使用环境变量）
  api_key: "${DIFY_API_KEY}"
  
  # 请求超时（秒）
  timeout_seconds: 30

# 通知配置
notification:
  # 主通知渠道：feishu / email
  primary: "feishu"
  
  # 飞书配置
  feishu:
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx"
  
  # 邮箱配置（备用）
  email:
    enabled: true
    smtp_server: "smtp.qq.com"
    smtp_port: 465
    use_ssl: true
    sender: "alert@example.com"
    # 密码建议使用环境变量
    password: "${EMAIL_PASSWORD}"
  
  # 通知接收人
  recipients:
    - "admin1@company.com"
    - "admin2@company.com"
  
  # 通知策略
  policy:
    # 触发通知的事件类型
    notify_on:
      - "container_died"
      - "resource_exceeded"
      - "health_check_failed"
      - "circuit_break"
    
    # 静默时段（可选，格式 HH:MM）
    quiet_hours:
      enabled: false
      start: "23:00"
      end: "07:00"
```

### 6.3 watchlist.yml 完整定义

```yaml
# ============================================
# 容器监控清单
# ============================================

containers:
  # -------- 网关层 --------
  - name: "nginx-gateway"
    description: "Nginx 反向代理"
    
    # 健康检查配置
    health_check:
      type: "http"                    # http / tcp / command
      endpoint: "http://localhost:80/health"
      expected_status: 200
      timeout_seconds: 5
      
    # 资源阈值
    thresholds:
      cpu_percent_warning: 70
      cpu_percent_critical: 90
      memory_percent_warning: 70
      memory_percent_critical: 85
      
    # 处理策略
    policy:
      auto_restart: true              # 是否允许自动重启
      restart_delay_seconds: 5        # 重启前等待时间
      priority: 1                     # 优先级（1最高）
      
  # -------- 应用层 --------
  - name: "app-backend"
    description: "Spring Boot 后端服务"
    
    health_check:
      type: "http"
      endpoint: "http://localhost:8080/actuator/health"
      expected_status: 200
      timeout_seconds: 10
      
    thresholds:
      cpu_percent_warning: 80
      cpu_percent_critical: 95
      memory_percent_warning: 75
      memory_percent_critical: 90
      
    policy:
      auto_restart: true
      restart_delay_seconds: 10
      priority: 2
      
  # -------- 缓存层 --------
  - name: "redis-cache"
    description: "Redis 缓存服务"
    
    health_check:
      type: "command"
      command: "redis-cli ping"
      expected_output: "PONG"
      timeout_seconds: 5
      
    thresholds:
      cpu_percent_warning: 50
      cpu_percent_critical: 80
      memory_percent_warning: 60
      memory_percent_critical: 80
      
    policy:
      auto_restart: true
      restart_delay_seconds: 3
      priority: 1                     # Redis 优先级高
      
  # -------- 数据库层 --------
  - name: "mysql-db"
    description: "MySQL 数据库"
    
    health_check:
      type: "tcp"
      host: "localhost"
      port: 3306
      timeout_seconds: 5
      
    thresholds:
      cpu_percent_warning: 70
      cpu_percent_critical: 90
      memory_percent_warning: 70
      memory_percent_critical: 85
      
    policy:
      auto_restart: false             # 数据库不自动重启，避免数据损坏
      priority: 1
```

---

## 7. 接口定义

### 7.1 巡检员 → Dify Webhook

**请求方式**: POST  
**Content-Type**: application/json

**请求体**:
```json
{
  "event_id": "string",
  "timestamp": "ISO8601 datetime",
  "host": "string",
  "issues": [
    {
      "container": {
        "name": "string",
        "id": "string",
        "image": "string"
      },
      "fault_type": "CONTAINER_DIED | RESOURCE_EXCEEDED | HEALTH_CHECK_FAILED",
      "severity": "warning | critical",
      "evidence": {
        "exit_code": "number | null",
        "logs_tail": "string",
        "last_stats": {
          "cpu_percent": "string",
          "memory_usage": "string",
          "memory_percent": "string"
        },
        "restart_count": "number",
        "breaker_status": "normal | warning | circuit_break"
      }
    }
  ]
}
```

### 7.2 Dify → 飞书 Webhook

**请求方式**: POST  
**Content-Type**: application/json

**请求体**: 参考 5.5.1 飞书消息卡片格式

### 7.3 Dify → 执行命令（可选）

如果 Dify 需要执行 Docker 命令，可通过以下方式：

**方案A**: 巡检员额外暴露一个本地 HTTP API
```
POST http://localhost:9999/action
{
  "action": "restart",
  "container": "app-backend"
}
```

**方案B**: Dify 通过 SSH 执行命令（需配置密钥）

**推荐方案A**，更安全可控。

---

## 8. 实施计划

### 8.1 里程碑

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| M1: 环境准备 | Day 1-2 | Docker 环境、Dify 部署、飞书机器人 |
| M2: 巡检员开发 | Day 3-5 | watchdog.py 核心功能 |
| M3: Dify 工作流 | Day 6-7 | 完整决策流程 |
| M4: 联调测试 | Day 8-9 | 端到端验证 |
| M5: 故障模拟 | Day 10 | 模拟容器验证修复能力 |
| M6: 上线观察 | Day 11-14 | 生产环境试运行 |

### 8.2 详细任务分解

#### M1: 环境准备 (Day 1-2)

- [ ] 确认 Docker 版本 >= 20.x
- [ ] 部署 Dify 容器
- [ ] 创建飞书群 + 添加自定义机器人
- [ ] 配置邮箱 SMTP（备用）
- [ ] 创建项目目录结构

#### M2: 巡检员开发 (Day 3-5)

- [ ] 实现配置加载模块
- [ ] 实现 Docker 事件监听
- [ ] 实现定时轮询检查
- [ ] 实现取证模块
- [ ] 实现熔断状态管理
- [ ] 实现 HTTP 上报模块
- [ ] 单元测试

#### M3: Dify 工作流 (Day 6-7)

- [ ] 创建 Webhook 触发节点
- [ ] 创建证据解析节点
- [ ] 创建熔断判断节点
- [ ] 创建飞书通知节点
- [ ] 创建邮件备用节点
- [ ] 流程测试

#### M4: 联调测试 (Day 8-9)

- [ ] 巡检员 → Dify 联通测试
- [ ] Dify → 飞书 通知测试
- [ ] 端到端场景测试
- [ ] 异常场景测试

#### M5: 故障模拟 (Day 10)

- [ ] 创建 CPU 爆满模拟容器
- [ ] 创建内存逼近上限模拟容器
- [ ] 创建进程崩溃模拟容器
- [ ] 验证自动检测 + 修复 + 通知流程

#### M6: 上线观察 (Day 11-14)

- [ ] 部署到生产环境
- [ ] 监控巡检员运行状态
- [ ] 收集误报/漏报情况
- [ ] 调优阈值参数

---

## 9. 风险评估

### 9.1 技术风险

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| Dify 容器本身挂掉 | 中 | 高 | 巡检员监控 Dify，Dify 挂掉直接发邮件 |
| 飞书 API 限流 | 低 | 中 | 合并通知、增加邮件备用 |
| 误触发重启 | 中 | 高 | 熔断机制 + 数据库类容器禁止自动重启 |
| 巡检员自身 OOM | 低 | 高 | 限制内存使用，监控自身进程 |

### 9.2 运营风险

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 告警疲劳 | 中 | 中 | 合理设置阈值、静默时段 |
| 夜间无人响应 | 中 | 中 | 非关键告警延迟到工作时间 |
| 配置文件错误 | 中 | 高 | 启动时校验配置、提供默认值 |

### 9.3 资源风险

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 内存超过 3G 宕机 | 中 | 极高 | 所有容器设置硬性内存限制 |
| 磁盘写满 | 低 | 高 | 日志轮转、定期清理 |

---

## 10. 验收标准

### 10.1 功能验收

| 测试用例 | 预期结果 | 通过标准 |
|----------|----------|----------|
| 手动停止一个业务容器 | 30秒内检测到，尝试重启，发送通知 | ✅ |
| 容器 OOM 崩溃 | 秒级检测，记录退出码137，尝试重启 | ✅ |
| 容器 CPU 持续 > 90% | 2分钟内检测到，发送告警（不重启） | ✅ |
| 同一容器连续崩溃3次 | 触发熔断，停止自动重启，发送严重告警 | ✅ |
| 飞书发送失败 | 自动切换邮件通知 | ✅ |

### 10.2 性能验收

| 指标 | 目标值 | 测试方法 |
|------|--------|----------|
| 巡检员内存占用 | < 50MB | `docker stats` |
| 事件响应延迟 | < 5秒 | 停止容器到收到通知的时间 |
| 轮询 CPU 开销 | < 1% | 稳态下 `top` 观察 |

### 10.3 可靠性验收

| 场景 | 预期 |
|------|------|
| 巡检员进程被 kill | systemd 自动重启 |
| Dify 容器重启 | 不影响巡检员运行，Dify 恢复后自动恢复对接 |
| 服务器重启 | 所有服务自动启动，巡检恢复工作 |

---

## 附录

### A. 常用命令速查

```bash
# 查看容器状态
docker ps -a

# 查看容器资源使用
docker stats --no-stream

# 查看容器日志
docker logs --tail 50 <container_name>

# 监听 Docker 事件
docker events --filter 'event=die' --filter 'event=oom'

# 重启容器
docker restart <container_name>

# 查看容器详情
docker inspect <container_name>
```

### B. 故障类型速查

| 退出码 | 含义 |
|--------|------|
| 0 | 正常退出 |
| 1 | 应用错误 |
| 137 | OOM Killed (128 + 9) |
| 139 | Segmentation Fault (128 + 11) |
| 143 | SIGTERM (128 + 15) |

### C. 参考资料

- [Docker 官方文档 - Events](https://docs.docker.com/engine/reference/commandline/events/)
- [Dify 官方文档 - Workflow](https://docs.dify.ai/)
- [飞书开放平台 - 自定义机器人](https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN)

---

**文档结束**

> 本文档将随项目进展持续更新。如有疑问，请联系项目负责人。

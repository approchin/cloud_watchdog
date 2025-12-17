# Cloud Watchdog 项目评估报告

> 评估时间：2024-12-03

---

## 1. 系统架构图

```mermaid
graph TB
    subgraph "Cloud Watchdog Agent"
        main[main.py<br/>程序入口]
        config[config.py<br/>配置管理]
        monitor[monitor.py<br/>监控核心]
        evidence[evidence.py<br/>证据收集]
        executor[executor.py<br/>命令执行]
        notifier[notifier.py<br/>通知发送]
        api[api.py<br/>HTTP 接口]
    end
    
    subgraph "外部系统"
        docker[(Docker Engine)]
        dify[Dify Workflow<br/>LLM 决策]
        email[邮件服务<br/>SMTP]
    end
    
    main --> config
    main --> monitor
    main --> api
    
    monitor --> evidence
    monitor --> config
    monitor -.->|POST /webhook| dify
    
    evidence --> docker
    executor --> docker
    
    api -.->|POST /action| executor
    api -.->|POST /notify| notifier
    
    dify -.->|调用| api
    notifier --> email
```

---

## 2. 核心数据流

```mermaid
sequenceDiagram
    participant D as Docker
    participant M as Monitor
    participant E as Evidence
    participant Dify as Dify Workflow
    participant API as API Server
    participant Ex as Executor
    participant N as Notifier
    
    Note over M: 双线程监控
    
    alt 轮询检测
        M->>D: docker inspect / stats
        D-->>M: 容器状态
    else 事件监听
        D->>M: docker events (die/oom)
    end
    
    M->>M: _should_report() 熔断检查
    
    alt 允许上报
        M->>E: collect_evidence()
        E->>D: docker inspect/stats/logs
        D-->>E: 原始数据
        E-->>M: evidence JSON
        M->>Dify: POST webhook_url
        
        Dify->>Dify: LLM 分析决策
        
        Dify->>API: POST /action
        API->>Ex: execute_action()
        Ex->>Ex: _execute_restart_with_retry()
        
        loop 最多 max_retries 次
            Ex->>D: docker restart
            Ex->>Ex: sleep(restart_delay_seconds)
            Ex->>D: docker inspect (验证)
            alt 恢复成功
                Ex-->>API: is_recovered=true
            else 继续重试
                Ex->>Ex: 下一轮
            end
        end
        
        alt 所有重试失败
            Ex->>D: docker stop
            Ex-->>API: is_recovered=false
        end
        
        API-->>Dify: 执行结果
        
        Dify->>API: POST /notify
        API->>N: send_notification()
        N->>N: format_alert_email()
        N-->>API: 发送结果
    else 熔断/去重
        M->>M: 跳过上报
    end
```

---

## 3. 模块依赖关系

```mermaid
graph LR
    subgraph "入口层"
        main[main.py]
    end
    
    subgraph "服务层"
        monitor[monitor.py]
        api[api.py]
    end
    
    subgraph "业务层"
        executor[executor.py]
        evidence[evidence.py]
        notifier[notifier.py]
    end
    
    subgraph "基础层"
        config[config.py]
    end
    
    main --> config
    main --> monitor
    main --> api
    
    monitor --> config
    monitor --> evidence
    
    api --> executor
    api --> notifier
    
    executor --> config
    executor --> evidence
    
    evidence --> config
    
    notifier --> config
```

---

## 4. 熔断状态机

```mermaid
stateDiagram-v2
    [*] --> 正常: 启动
    
    正常 --> 正常: 上报成功<br/>(记录时间)
    正常 --> 冷却中: 上报后<br/>(cooldown_seconds内)
    冷却中 --> 正常: 冷却期结束
    
    正常 --> 熔断: 时间窗口内<br/>达到 failure_threshold
    熔断 --> 正常: time_window_seconds 后
    
    note right of 熔断
        跳过所有上报
        防止打爆 Dify
    end note
    
    note right of 冷却中
        跳过重复上报
        防止同一问题刷屏
    end note
```

---

## 5. RESTART 重试流程

```mermaid
flowchart TD
    A[execute_action RESTART] --> B{白名单检查}
    B -->|失败| C[返回错误]
    B -->|通过| D[_execute_restart_with_retry]
    
    D --> E[attempt = 1]
    E --> F[docker restart]
    F --> G{成功?}
    G -->|否| H{attempt < max_retries?}
    H -->|是| I[attempt++]
    I --> F
    H -->|否| J[docker stop]
    J --> K[返回失败<br/>is_recovered=false]
    
    G -->|是| L[sleep restart_delay_seconds]
    L --> M[get_container_info]
    M --> N{running?}
    N -->|否| H
    N -->|是| O[health_check]
    O --> P{healthy?}
    P -->|否| H
    P -->|是| Q[返回成功<br/>is_recovered=true]
```

---

## 6. 配置层级

```mermaid
graph TD
    subgraph "config.yml 全局配置"
        system[system<br/>check_interval_seconds<br/>log_level]
        cb[circuit_breaker<br/>failure_threshold<br/>time_window_seconds<br/>cooldown_seconds]
        dify[dify<br/>webhook_url<br/>timeout_seconds]
        executor[executor<br/>host/port<br/>allowed_actions]
        thresholds[thresholds<br/>cpu_warning/critical<br/>memory_warning/critical]
        email[email<br/>smtp_server<br/>sender/recipients]
    end
    
    subgraph "watchlist.yml 容器配置"
        container1[容器1]
        container2[容器2]
        container3[容器N...]
    end
    
    container1 --> hc1[health_check<br/>type/endpoint]
    container1 --> th1[thresholds<br/>覆盖全局]
    container1 --> po1[policy<br/>auto_restart<br/>max_retries]
```

---

## 7. 项目评估

### 7.1 架构评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **模块划分** | ⭐⭐⭐⭐ | 职责清晰，单一职责原则 |
| **依赖方向** | ⭐⭐⭐⭐ | 从上到下，无循环依赖 |
| **可测试性** | ⭐⭐⭐ | 缺少单元测试，但结构支持测试 |
| **可扩展性** | ⭐⭐⭐⭐ | 易于添加新的通知渠道、健康检查类型 |
| **错误处理** | ⭐⭐⭐ | 有基本处理，但异常类型不够细化 |

### 7.2 功能完整性

| 功能 | 状态 | 说明 |
|------|------|------|
| 容器存活监控 | ✅ 完整 | 轮询 + 事件监听双模式 |
| 资源监控 | ✅ 完整 | CPU/内存阈值检测 |
| 健康检查 | ✅ 完整 | HTTP/TCP/Command 三种类型 |
| 证据收集 | ✅ 完整 | inspect/stats/logs/health |
| 重试机制 | ✅ 完整 | 可配置重试次数和延迟 |
| 熔断保护 | ✅ 完整 | 时间窗口 + 阈值 + 冷却 |
| 邮件通知 | ✅ 完整 | 4种通知类型 |
| 飞书/钉钉通知 | ❌ 未实现 | 仅预留配置 |
| API 认证 | ❌ 未实现 | 接口完全开放 |

### 7.3 代码质量

| 指标 | 评价 |
|------|------|
| **代码行数** | ~1000 行（合理） |
| **注释覆盖** | 中等（函数有 docstring，内部注释少） |
| **类型标注** | 良好（使用 typing） |
| **配置外置** | 良好（YAML 配置） |
| **日志规范** | 良好（分级日志） |

### 7.4 潜在风险

```mermaid
graph LR
    subgraph "高风险"
        R1[API 无认证<br/>可被恶意调用]
    end
    
    subgraph "中风险"
        R2[日志截断<br/>可能丢失关键信息]
        R3[单点故障<br/>Agent 挂掉则无监控]
    end
    
    subgraph "低风险"
        R4[Windows 兼容<br/>日志文件不写入]
        R5[内存泄漏<br/>report_history 无上限]
    end
```

### 7.5 改进建议

| 优先级 | 建议 | 工作量 |
|--------|------|--------|
| P0 | API 添加 IP 白名单认证 | 小 |
| P1 | 添加单元测试 | 中 |
| P1 | report_history 定期清理 | 小 |
| P2 | 飞书/钉钉通知实现 | 中 |
| P2 | 日志收集到文件 | 小 |
| P3 | 容器组 CPU 贡献度计算 | 中 |
| P3 | Web 管理界面 | 大 |

---

## 8. 部署架构

```mermaid
graph TB
    subgraph "云服务器 182.254.240.198"
        subgraph "Docker 环境"
            c1[nginx]
            c2[redis]
            c3[app]
            c4[...]
        end
        
        agent[Cloud Watchdog Agent<br/>:9999]
        
        agent -.-> c1
        agent -.-> c2
        agent -.-> c3
    end
    
    subgraph "Dify 平台"
        workflow[Workflow<br/>LLM 决策引擎]
    end
    
    agent -->|POST evidence| workflow
    workflow -->|POST /action| agent
    workflow -->|POST /notify| agent
    
    subgraph "通知"
        email[邮件]
    end
    
    agent --> email
```

---

## 9. 总结

**项目成熟度：70%**

✅ 核心功能完整
✅ 架构设计合理
✅ 可扩展性良好

⚠️ 缺少测试覆盖
⚠️ API 安全性待加强
⚠️ 部分配置功能未使用

**可直接用于生产环境（需先添加 API 认证）**

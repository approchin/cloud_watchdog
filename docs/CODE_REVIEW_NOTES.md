# Cloud Watchdog 代码审阅记录

> 审阅日期: 2025-12-02  
> 审阅状态: 进行中

---

## 待修改事项汇总

| # | 文件 | 问题描述 | 优先级 | 状态 |
|---|------|----------|--------|------|
| 1 | config.yml | `executor.host` 默认 `127.0.0.1`，Dify 容器内无法访问，需改为 `182.254.240.198` | 高 | 待修改 |
| 2 | config.py | 注释掉 `_resolve_env()` 调用，保留函数本身 | 中 | ✅ 已完成 |
| 3 | config.yml | 测试阈值过高，建议增加 `test_mode` 配置 | 中 | 待修改 |
| 4 | 新增功能 | 缺少"容器群 CPU 贡献率"指标 | 中 | 待设计 |

---

## Step 1: config.py 审阅记录

### 已确认设计
- [x] `@dataclass` 用于简化配置类定义
- [x] `field(default_factory=...)` 解决可变默认值问题
- [x] YAML 存结构化配置 + .env 存敏感信息的分离设计
- [x] 模块级全局变量实现单例模式

### 待改进建议
- [ ] 缺少配置校验（端口范围、URL 格式等）
- [x] `_resolve_env()` 暂不使用，已注释其调用

---

## Step 2: 配置文件审阅记录

### 已修复的不一致问题
| # | 问题 | 解决方案 | 状态 |
|---|------|----------|------|
| 5 | `circuit_breaker.max_restarts` 字段名不一致 | 改为 `max_restart_attempts` | ✅ |
| 6 | `containers[].auto_restart` 结构不一致 | 改为 `policy` 结构 | ✅ |
| 7 | `containers[].enabled` 代码未处理 | 添加过滤逻辑 | ✅ |
| 8 | 全局 `thresholds` 代码未加载 | 添加加载逻辑 | ✅ |
| 9 | `cooldown_seconds` 代码未使用 | 添加字段到 CircuitBreakerConfig | ✅ |
| 10 | `system.name` 无用字段 | 从配置文件删除 | ✅ |

### 配置与代码对应关系
```
config.yml                    config.py
─────────────────────────────────────────────
system:                  →    SystemConfig
circuit_breaker:         →    CircuitBreakerConfig
dify:                    →    DifyConfig
executor:                →    ExecutorConfig
notification.email:      →    EmailConfig
thresholds:              →    ThresholdConfig

watchlist.yml
─────────────────────────────────────────────
containers[]:            →    List[ContainerConfig]
  - enabled              →      过滤 enabled=false
  - policy               →      ContainerConfig.policy
```

---

## Step 3: evidence.py 审阅记录

### 已完成修改
| # | 问题 | 解决方案 | 状态 |
|---|------|----------|------|
| 11 | `get_container_info()` 缺少关键字段 | 添加 `oom_killed`, `error`, `restarting`, `ip_address`, `ports` 等 | ✅ |
| 12 | `collect_evidence()` 未暴露 OOM 和错误信息 | 添加 `oom_killed`, `error_message` 到 evidence | ✅ |

### 待改进建议
- [ ] `get_container_logs()` 日志截断固定 2000 字符，可能丢失关键信息
- [ ] `parse_percent()` 使用裸 `except`，应明确捕获 `ValueError`

---

## Step 4: executor.py 审阅记录

### 已完成修改
| # | 问题 | 解决方案 | 状态 |
|---|------|----------|------|
| 13 | 双重检查冗余 | 合并为单行检查 | ✅ |
| 14 | 缺少重试逻辑 | 新增 `_execute_restart_with_retry()` 函数 | ✅ |
| 15 | `restart_delay_seconds` 未使用 | 从 policy 读取并使用 | ✅ |
| 16 | 重试失败后无处理 | 自动 STOP 容器并返回失败 | ✅ |

### 新增函数
- `_execute_single_command()` - 执行单次命令（STOP/INSPECT）
- `_execute_restart_with_retry()` - 带重试的 RESTART 逻辑

---

## Step 5: notifier.py 审阅记录

### 待改进建议
- [ ] 只支持邮件通知，缺少飞书/钉钉/Webhook 等渠道
- [ ] `action_result` 未展示重试次数 `attempts` 信息
- [ ] 邮件中 `verification` 直接打印字典，格式粗糙

---

## Step 6: api.py 审阅记录

### 已完成修改
| # | 问题 | 解决方案 | 状态 |
|---|------|----------|------|
| 20 | `ActionResponse` 缺少重试字段 | 添加 `is_recovered`, `total_attempts`, `attempts` 等 | ✅ |
| 21 | `/action` 冗余白名单检查 | 移除，由 executor 统一处理 | ✅ |

### 待改进建议
- [ ] 无认证机制（后期用 IP 白名单解决）

### 设计模式说明
- `create_app()` 是**工厂函数**模式，用于测试、配置注入、延迟初始化

---

## Step 7: monitor.py 审阅记录

### 已完成修改
| # | 问题 | 解决方案 | 状态 |
|---|------|----------|------|
| 22 | 缺少熔断逻辑 | 新增 `_should_report()` 实现熔断 | ✅ |
| 23 | 缺少去重机制 | 使用 `cooldown_seconds` 防止短时间重复上报 | ✅ |
| 24 | `_is_monitored()` 效率低 | 使用 `set` 替代 `list` 遍历，O(n) → O(1) | ✅ |
| 25 | 未使用 `cooldown_seconds` | 在 `_should_report()` 中实现 | ✅ |

### 新增函数
- `_should_report()` - 熔断 + 去重检查
- `_record_report()` - 记录上报时间

### 关键概念
- **daemon=True**：守护线程，主线程退出时自动终止
- **GIL**：仅影响 CPU 密集型任务，I/O 密集型可真正并行
- **docker events**：实时监听容器 die/oom 事件

---

## Step 8: main.py 审阅记录

### 代码质量
✅ 结构清晰，启动流程合理

### 待改进建议
- [ ] Windows 不写日志文件（L53 判断跳过）
- [ ] `--monitor-only` 模式下用 `while True: sleep(1)` 阻塞，可改用 `Event.wait()`

---

# 审阅总结

## 已完成修改统计
| 模块 | 修改数 | 关键改动 |
|------|--------|----------|
| config.py | 4 | 添加 `cooldown_seconds`、`enabled` 字段 |
| evidence.py | 2 | 添加 OOM/错误信息字段 |
| executor.py | 4 | 重试逻辑、使用配置参数 |
| api.py | 2 | 添加响应字段、移除冗余检查 |
| monitor.py | 4 | 熔断、去重、O(1) 查询优化 |
| main.py | 0 | 无需修改 |

## 待处理事项
- [ ] API 认证（IP 白名单）
- [ ] 飞书/钉钉通知渠道
- [ ] 日志截断优化
- [ ] Windows 日志文件支持

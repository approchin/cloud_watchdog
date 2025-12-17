# Cloud Watchdog

基于 LLM 的容器故障自动诊断与修复系统

## ✨ 功能特性

- 🔍 **实时监控** - 双线程监控（轮询 + 事件监听）
- 🚨 **智能诊断** - 集成 Dify Workflow 智能决策
- 🔧 **自动修复** - RESTART 重试机制，失败后自动 STOP
- 🛡️ **熔断保护** - 防止频繁重启刷屏
- 📊 **证据收集** - docker inspect/stats/logs 完整证据包
- 📧 **告警通知** - 邮件通知（支持多种通知类型）
- 🎯 **健康检查** - HTTP/TCP/Command 多种检查方式

## 🎯 监控能力

| 监控类型 | 检测内容 | 触发条件 |
|---------|---------|---------|
| **存活检查** | 容器运行状态 | 容器停止/退出 |
| **资源监控** | CPU/内存使用率 | 超过阈值（可配置） |
| **健康检查** | HTTP/TCP/命令 | 健康检查失败 |
| **事件监听** | OOM/Die 事件 | Docker 事件触发 |

## 📦 快速开始

### 1. 环境检查

```bash
# 检查依赖和配置
./check-env.sh
```

### 2. 安装依赖

```bash
# 安装 Python 依赖
pip3 install -r requirements.txt
```

### 3. 配置文件

编辑 `config/config.yml`：

```yaml
# Dify Webhook URL（必须修改）
dify:
  webhook_url: "http://your-dify:8080/v1/workflows/webhook/YOUR_ID"

# API 服务地址（必须修改为公网 IP）
executor:
  host: "182.254.240.198"
  port: 9999

# 邮件配置（可选）
notification:
  email:
    enabled: true
    sender: "your-email@qq.com"
    password: "smtp-auth-code"
    recipients: ["admin@example.com"]
```

编辑 `config/watchlist.yml` 添加需要监控的容器。

### 4. 启动服务

```bash
# 方式一：快速启动（前台）
./start.sh

# 方式二：后台运行
nohup ./start.sh > /dev/null 2>&1 &

# 方式三：systemd 服务（推荐生产环境）
# 参考 DEPLOYMENT.md
```

### 5. 检查状态

```bash
# 查看服务状态
./status.sh

# 测试 API
curl http://localhost:9999/health
```

## 🧪 故障模拟测试

启动测试容器：

```bash
cd test-containers

# 启动所有测试容器
docker-compose up -d

# 或逐个启动
docker-compose up -d normal-app      # 正常容器
docker-compose up -d crash-loop      # 进程崩溃
docker-compose up -d cpu-stress      # CPU 压力
docker-compose up -d memory-leak     # 内存泄漏
docker-compose up -d unhealthy-app   # 健康检查失败
```

查看监控日志：

```bash
tail -f ../logs/watchdog.log
```

## 📋 API 接口

### POST /action - 执行容器操作

```bash
curl -X POST http://localhost:9999/action \
  -H "Content-Type: application/json" \
  -d '{
    "command": "RESTART",
    "container_name": "crash-loop"
  }'
```

### POST /notify - 发送通知

```bash
curl -X POST http://localhost:9999/notify \
  -H "Content-Type: application/json" \
  -d '{
    "type": "alert",
    "container_name": "crash-loop",
    "fault_type": "PROCESS_CRASH"
  }'
```

### GET /health - 健康检查

```bash
curl http://localhost:9999/health
```

## 📁 项目结构

```
cloud-watchdog/
├── watchdog/                   # 核心代码
│   ├── main.py                 # 主入口
│   ├── config.py               # 配置加载
│   ├── monitor.py              # 监控核心（双线程）
│   ├── evidence.py             # 证据收集
│   ├── executor.py             # 命令执行（重试逻辑）
│   ├── api.py                  # FastAPI 接口
│   └── notifier.py             # 邮件通知
├── config/                     # 配置文件
│   ├── config.yml              # 全局配置
│   └── watchlist.yml           # 监控容器列表
├── test-containers/            # 故障模拟容器
│   ├── docker-compose.yml
│   ├── normal-app/             # 正常容器
│   ├── crash-loop/             # 崩溃容器
│   ├── cpu-stress/             # CPU 压力
│   ├── memory-leak/            # 内存泄漏
│   └── unhealthy-app/          # 健康检查失败
├── docs/                       # 文档
│   ├── PROJECT_SPECIFICATION.md
│   ├── PROJECT_EVALUATION.md
│   └── CODE_REVIEW_NOTES.md
├── logs/                       # 日志目录
├── state/                      # 熔断器状态
├── requirements.txt            # Python 依赖
├── DEPLOYMENT.md               # 部署指南
├── check-env.sh                # 环境检查脚本
├── start.sh                    # 启动脚本
├── stop.sh                     # 停止脚本
└── status.sh                   # 状态检查脚本
```

## 🔧 核心机制

### 1. 双线程监控

- **轮询线程**: 定期检查容器状态和资源使用
- **事件线程**: 监听 Docker 事件（die/oom）

### 2. RESTART 重试逻辑

```
检测故障 → 收集证据 → Dify 诊断 → 执行 RESTART
    ↓ 失败
重试（最多3次）→ 健康检查
    ↓ 仍失败
自动 STOP → 告警通知
```

### 3. 熔断机制

```
时间窗口（5分钟）内重启次数 ≥ 阈值（3次）
    ↓
触发熔断 → 冷却期（30分钟）→ 仅监控不上报
```

### 4. 证据包格式

```json
{
  "event_id": "evt_20231203_120000",
  "timestamp": "2023-12-03T12:00:00",
  "container": {
    "name": "crash-loop",
    "status": "exited",
    "exit_code": 1,
    "oom_killed": false
  },
  "evidence": {
    "cpu_percent": "15%",
    "memory_percent": "45%",
    "logs_tail": "最近50行日志..."
  },
  "fault_type": "PROCESS_CRASH"
}
```

## 📊 故障类型

| 故障类型 | 触发条件 | 推荐动作 |
|---------|---------|---------|
| `PROCESS_CRASH` | 容器退出 | RESTART |
| `OOM_KILLED` | 内存溢出 | STOP |
| `CPU_HIGH` | CPU 超限 | RESTART/INSPECT |
| `MEMORY_HIGH` | 内存超限 | RESTART |
| `HEALTH_FAIL` | 健康检查失败 | RESTART |

## 🛠️ 脚本工具

| 脚本 | 用途 | 示例 |
|-----|------|------|
| `check-env.sh` | 环境检查 | `./check-env.sh` |
| `start.sh` | 启动服务 | `./start.sh 0.0.0.0 9999` |
| `stop.sh` | 停止服务 | `./stop.sh` |
| `status.sh` | 状态检查 | `./status.sh` |

## 📖 文档

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - 完整部署指南
- **[docs/PROJECT_SPECIFICATION.md](docs/PROJECT_SPECIFICATION.md)** - 项目规格说明
- **[docs/CODE_REVIEW_NOTES.md](docs/CODE_REVIEW_NOTES.md)** - 代码审查记录

## 🔐 安全建议

1. ✅ 限制 API 访问（防火墙白名单）
2. ✅ 使用环境变量存储敏感信息
3. ✅ 配置 API Token 认证（生产环境）
4. ✅ 定期备份配置和状态文件
5. ✅ 监控服务自身运行状态

## 📝 许可证

本项目仅供学习和研究使用。

## 🆘 技术支持

- 查看日志: `tail -f logs/watchdog.log`
- 环境检查: `./check-env.sh`
- 状态查看: `./status.sh`
- 完整文档: `DEPLOYMENT.md`

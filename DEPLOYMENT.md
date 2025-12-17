# Cloud Watchdog 部署指南

## 🚀 快速部署

### 1. 系统要求
- **操作系统**: Linux (推荐 Ubuntu 20.04+)
- **Docker**: 20.10+
- **Docker Compose**: 1.29+
- **Python**: 3.8+
- **权限**: 当前用户需要有 Docker 执行权限

### 2. 安装依赖

```bash
# 安装 Python 依赖
pip3 install -r requirements.txt

# 验证 Docker 权限
docker ps
```

### 3. 配置文件

#### 3.1 主配置文件 `config/config.yml`

**必须修改的配置项**：

```yaml
# Dify 配置
dify:
  webhook_url: "http://your-dify-server:8080/v1/workflows/webhook/YOUR_WORKFLOW_ID"
  api_key: ""  # 可选
  timeout_seconds: 30

# 执行API配置（修改为服务器公网 IP）
executor:
  host: "182.254.240.198"  # 改为你的服务器公网 IP
  port: 9999

# 邮件配置（推荐启用）
notification:
  email:
    enabled: true
    smtp_server: "smtp.qq.com"
    smtp_port: 465
    use_ssl: true
    sender: "your-email@qq.com"  # 修改为你的邮箱
    password: "your-smtp-password"  # QQ邮箱授权码
    recipients:
      - "admin@example.com"  # 接收告警的邮箱
```

#### 3.2 监控列表 `config/watchlist.yml`

已预配置了测试容器，生产环境需要根据实际容器修改：

```yaml
containers:
  - name: "your-container-name"
    enabled: true
    description: "你的应用描述"
    health_check:
      type: "http"  # 或 tcp / command
      endpoint: "http://localhost:8080/health"
      expected_status: 200
      timeout_seconds: 5
    thresholds:
      cpu_percent_critical: 85
      memory_percent_critical: 85
    policy:
      auto_restart: true
      restart_delay_seconds: 10
      max_retries: 3
```

### 4. 启动服务

#### 方式一：前台运行（测试）

```bash
# 启动监控服务
python3 -m watchdog.main --host 0.0.0.0 --port 9999 --log-level INFO
```

#### 方式二：后台运行（生产）

```bash
# 使用 nohup
nohup python3 -m watchdog.main --host 0.0.0.0 --port 9999 --log-level INFO > /dev/null 2>&1 &

# 查看进程
ps aux | grep watchdog

# 查看日志
tail -f logs/watchdog.log
```

#### 方式三：systemd 服务（推荐）

创建服务文件 `/etc/systemd/system/cloud-watchdog.service`：

```ini
[Unit]
Description=Cloud Watchdog - Container Monitoring Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=lyb
WorkingDirectory=/home/lyb
ExecStart=/usr/bin/python3 -m watchdog.main --host 0.0.0.0 --port 9999 --log-level INFO
Restart=always
RestartSec=10
StandardOutput=append:/home/lyb/logs/watchdog.log
StandardError=append:/home/lyb/logs/watchdog-error.log

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloud-watchdog
sudo systemctl start cloud-watchdog
sudo systemctl status cloud-watchdog
```

### 5. 验证服务

```bash
# 检查 API 服务
curl http://182.254.240.198:9999/health

# 预期输出
{"status":"healthy"}

# 检查日志
tail -f logs/watchdog.log
```

### 6. 防火墙配置

```bash
# 开放 API 端口（如需外网访问）
sudo ufw allow 9999/tcp

# 仅允许 Dify 服务器访问（推荐）
sudo ufw allow from YOUR_DIFY_SERVER_IP to any port 9999
```

---

## 🧪 故障模拟测试

### 测试容器说明

项目包含 5 个测试容器，用于验证监控功能：

| 容器名 | 用途 | 故障类型 |
|-------|------|---------|
| `normal-app` | 正常运行 | 无故障（对照组） |
| `cpu-stress` | CPU 压力 | 30秒后 CPU 达到 100% |
| `memory-leak` | 内存泄漏 | 30秒后内存持续增长 |
| `crash-loop` | 进程崩溃 | 每60秒崩溃一次 |
| `unhealthy-app` | 健康检查失败 | HTTP 健康检查 |

### 启动测试容器

```bash
cd test-containers

# 启动所有测试容器
docker-compose up -d

# 查看容器状态
docker ps -a

# 查看容器日志
docker logs -f crash-loop
```

### 逐个测试流程

#### 测试 1: 正常容器（应无告警）

```bash
docker-compose up -d normal-app
```

**预期**: 无告警，监控日志显示容器运行正常。

#### 测试 2: 进程崩溃（RESTART 重试）

```bash
docker-compose up -d crash-loop
```

**预期**:
1. 60秒后容器崩溃
2. 监控检测到 `PROCESS_CRASH`
3. 调用 Dify Workflow 诊断
4. Dify 返回 `RESTART` 命令
5. 执行重启（最多3次）
6. 发送邮件通知

#### 测试 3: CPU 超限（告警）

```bash
docker-compose up -d cpu-stress
```

**预期**:
1. 30秒后 CPU 达到 100%
2. 监控检测到 `CPU_HIGH`
3. 调用 Dify 诊断
4. 发送告警邮件

#### 测试 4: 内存超限（告警）

```bash
docker-compose up -d memory-leak
```

**预期**:
1. 30秒后内存持续增长
2. 监控检测到 `MEMORY_HIGH`
3. 调用 Dify 诊断
4. 可能触发 OOM Kill

#### 测试 5: 健康检查失败

```bash
docker-compose up -d unhealthy-app

# 修改环境变量触发健康检查失败
docker stop unhealthy-app
docker run -d --name unhealthy-app -p 8080:8080 -e FAIL_RATE=1.0 test-containers-unhealthy-app

# 手动测试健康检查
curl http://localhost:8080/health
```

**预期**:
1. 健康检查返回 500
2. 监控检测到 `HEALTH_FAIL`
3. 调用 Dify 诊断

#### 测试 6: 熔断机制

```bash
# 手动模拟多次重启失败
for i in {1..5}; do
  docker restart crash-loop
  sleep 10
done
```

**预期**:
1. 5分钟内重启3次
2. 触发熔断
3. 停止上报 Dify（进入冷却期30分钟）
4. 发送熔断告警邮件

### 停止测试容器

```bash
# 停止所有测试容器
docker-compose down

# 停止单个容器
docker stop cpu-stress
```

---

## 📊 监控日志查看

```bash
# 实时查看
tail -f logs/watchdog.log

# 搜索特定容器
grep "crash-loop" logs/watchdog.log

# 查看最近告警
grep "ERROR\|WARNING" logs/watchdog.log | tail -20
```

---

## 🔧 常见问题

### 1. Docker 权限错误

```bash
# 将当前用户加入 docker 组
sudo usermod -aG docker $USER

# 重新登录或执行
newgrp docker
```

### 2. 端口被占用

```bash
# 查看端口占用
sudo lsof -i :9999

# 修改端口
python3 -m watchdog.main --host 0.0.0.0 --port 8888
```

### 3. Dify Webhook 连接失败

- 检查 Dify 服务是否正常
- 检查 Webhook URL 是否正确
- 检查防火墙规则

### 4. 邮件发送失败

- QQ邮箱需使用授权码（非登录密码）
- 检查 SMTP 服务器和端口
- 确认已开启 IMAP/SMTP 服务

---

## 📦 生产环境部署建议

1. **使用 systemd 管理服务**：自动重启、日志管理
2. **配置日志轮转**：防止日志文件过大
3. **监控服务本身**：使用 cron 或监控工具
4. **定期备份配置**：config/、state/ 目录
5. **设置告警通知**：邮件、钉钉、企业微信
6. **配置 HTTPS**：如需外网访问 API
7. **限制 API 访问**：防火墙白名单、API Token

---

## 🛠️ Dify Workflow 配置

Cloud Watchdog 发送的证据包格式：

```json
{
  "evidence": {
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
      "logs_tail": "容器最近50行日志..."
    },
    "fault_type": "PROCESS_CRASH"
  }
}
```

Dify Workflow 需要返回：

```json
{
  "action": "RESTART",  // 或 STOP / INSPECT
  "container_name": "crash-loop",
  "reason": "进程崩溃，尝试重启"
}
```

然后调用 Cloud Watchdog API：

```bash
POST http://182.254.240.198:9999/action
Content-Type: application/json

{
  "command": "RESTART",
  "container_name": "crash-loop"
}
```

---

## 📝 目录结构

```
/home/lyb/
├── watchdog/           # 核心代码
├── config/             # 配置文件
├── test-containers/    # 测试容器
├── logs/               # 日志目录
├── state/              # 熔断器状态
├── docs/               # 文档
├── requirements.txt    # Python 依赖
└── README.md           # 项目说明
```

---

## 🆘 技术支持

- 项目文档：`docs/`
- 日志分析：`logs/watchdog.log`
- 代码审查：`docs/CODE_REVIEW_NOTES.md`

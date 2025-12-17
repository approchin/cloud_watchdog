# Cloud Watchdog 目录结构

```
cloud-watchdog/
├── watchdog/                   # 核心代码目录
│   ├── __init__.py            # 包初始化
│   ├── main.py                # 主入口（113行）
│   ├── config.py              # 配置加载（208行）
│   ├── monitor.py             # 监控核心（288行）✅ 已修复Bug
│   ├── evidence.py            # 证据收集（239行）
│   ├── executor.py            # 命令执行（226行）
│   ├── api.py                 # FastAPI接口（122行）
│   └── notifier.py            # 邮件通知（164行）
│
├── config/                     # 配置文件目录
│   ├── config.yml             # 全局配置（需修改）
│   └── watchlist.yml          # 监控容器列表
│
├── test-containers/           # 测试容器目录
│   ├── docker-compose.yml     # Docker编排
│   ├── normal-app/            # 正常容器
│   ├── crash-loop/            # 崩溃测试
│   ├── cpu-stress/            # CPU压力
│   ├── memory-leak/           # 内存泄漏
│   └── unhealthy-app/         # 健康检查失败
│
├── docs/                      # 文档目录
│   ├── PROJECT_SPECIFICATION.md   # 项目规格说明
│   ├── PROJECT_EVALUATION.md      # 项目评估
│   └── CODE_REVIEW_NOTES.md       # 代码审查记录
│
├── logs/                      # 日志目录（运行时生成）
│   └── watchdog.log          # 主日志文件
│
├── state/                     # 状态目录（运行时生成）
│   └── breaker_state.json    # 熔断器状态
│
├── README.md                  # 项目说明文档
├── DEPLOYMENT.md              # 部署指南
├── PROJECT_CHECKLIST.md       # 项目检查清单
├── STRUCTURE.md               # 目录结构说明（本文件）
│
├── requirements.txt           # Python依赖
├── .env.example              # 环境变量模板
├── .gitignore                # Git忽略规则
│
├── start.sh                  # 启动脚本
├── stop.sh                   # 停止脚本
├── status.sh                 # 状态检查脚本
└── check-env.sh              # 环境检查脚本
```

## 代码统计

- **核心代码**: 8个Python文件，1,363行
- **配置文件**: 2个YAML文件
- **测试容器**: 5个Docker容器
- **文档**: 6个Markdown文件
- **脚本工具**: 4个Shell脚本

## 快速开始

```bash
cd cloud-watchdog

# 环境检查
./check-env.sh

# 配置修改
vim config/config.yml

# 安装依赖
pip3 install -r requirements.txt

# 启动服务
./start.sh
```

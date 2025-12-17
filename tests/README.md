# Cloud Watchdog 测试指南

本文档说明如何使用测试工具和典型容器进行系统测试。

## 📁 测试文件结构

```
cloud-watchdog/
├── collect_typical_evidence.py     # 典型evidence收集脚本 ⭐
├── test_deepseek_complete.py       # DeepSeek完整测试 ⭐
├── test_deepseek_real.py           # DeepSeek真实容器测试
├── test_monitor.py                 # 监控系统功能测试
├── logs/                           # Evidence数据存储 ⭐
│   ├── normal_running_*.json
│   ├── cpu_*percent_*.json
│   ├── memory_*percent_*.json
│   ├── container_crash_*.json
│   ├── oom_killed_*.json
│   └── test_results_complete.json
└── test-containers/                # 测试容器配置 ⭐
    ├── docker-compose.yml          # 基础测试容器
    ├── docker-compose.extended.yml # 扩展测试场景
    ├── README_TYPICAL_SCENARIOS.md # 容器说明文档
    ├── normal-app/
    ├── cpu-stress/
    ├── memory-leak/
    ├── crash-loop/
    ├── unhealthy-app/
    └── oom-test/
```

## 🚀 快速开始

### 1. 启动测试容器

```bash
# 基础容器（5个）
cd test-containers
docker-compose up -d

# 或扩展容器（9个，包含极限场景）
docker-compose -f docker-compose.extended.yml up -d
```

### 2. 收集典型Evidence

```bash
# 自动收集8种典型场景
python3 collect_typical_evidence.py

# 收集完成后检查
ls -lh logs/*_*.json
```

### 3. 运行DeepSeek测试

```bash
# 完整测试（使用logs/中的数据）
python3 test_deepseek_complete.py

# 查看测试结果
cat logs/test_results_complete.json
```

## 📊 典型测试场景

| 场景 | 容器 | Evidence文件 | 预期决策 | 关键指标 |
|------|------|--------------|---------|---------|
| 正常运行 | normal-app | normal_running_*.json | NONE | CPU<5%, 内存<10% |
| CPU 50% | cpu-stress | cpu_50percent_*.json | NONE | CPU~50%, 未达70%阈值 |
| CPU 100% | cpu-stress | cpu_100percent_*.json | ALERT_ONLY | CPU达到limit上限 |
| 内存 80% | memory-leak | memory_80percent_*.json | ALERT_ONLY | 内存在70-90%区间 |
| 内存 95% | memory-leak | memory_95percent_*.json | RESTART | 内存接近limit |
| 容器崩溃 | crash-loop | container_crash_*.json | RESTART | exit_code=1 |
| OOM Killed | test-oom | oom_killed_*.json | RESTART | oom_killed=true |
| 频繁重启 | restart-loop | high_restart_count_*.json | STOP | restart_count>3 |

## 🔧 手动调整测试场景

### 临时增加CPU压力

```bash
# 增加到100%
docker exec cpu-stress sh -c \
  'pkill stress-ng && stress-ng --cpu 4 --timeout 0 &'

# 恢复到50%
docker exec cpu-stress sh -c \
  'pkill stress-ng && stress-ng --cpu 2 --timeout 0 &'
```

### 临时增加内存压力

```bash
# 增加到95%
docker exec memory-leak sh -c \
  'pkill stress-ng && stress-ng --vm 1 --vm-bytes 240M --timeout 0 &'

# 恢复到80%
docker exec memory-leak sh -c \
  'pkill stress-ng && stress-ng --vm 1 --vm-bytes 200M --timeout 0 &'
```

### 触发OOM Killer

```bash
# 使用专用OOM测试容器
docker run -d --name test-oom \
  --memory 64m \
  --restart no \
  cloud-watchdog-oom-test

# 等待10秒后收集evidence
sleep 10
docker inspect test-oom | jq '.[0].State.OOMKilled'
```

## 📝 Evidence数据说明

### Evidence文件格式

```json
{
  "_metadata": {
    "scenario": "cpu_100percent",
    "description": "CPU 100%使用，4个worker争抢0.5核心",
    "collected_at": "2025-12-04T14:30:00"
  },
  "event_id": "evt_...",
  "timestamp": "...",
  "container": {
    "name": "cpu-stress",
    "status": "running",
    "exit_code": 0,
    ...
  },
  "evidence": {
    "cpu_percent": "50.82%",
    "memory_percent": "6.05%",
    "memory_usage": "7.742MiB / 128MiB",
    ...
  }
}
```

### 关键字段说明

- **cpu_percent**: CPU使用率（相对于整个主机，不是容器limit）
- **memory_percent**: 内存使用率（相对于容器limit）
- **exit_code**: 退出码（0=正常，1=崩溃，137=OOM killed）
- **oom_killed**: 是否被OOM Killer杀掉
- **restart_count**: Docker记录的重启次数

## 🧪 测试工作流

### 完整测试流程

```bash
# 1. 启动容器
cd test-containers
docker-compose up -d

# 2. 等待容器稳定（stress-ng启动需要30秒）
sleep 35

# 3. 收集evidence
cd ..
python3 collect_typical_evidence.py

# 4. 运行DeepSeek测试
python3 test_deepseek_complete.py

# 5. 查看结果
cat logs/test_results_complete.json | jq '.[] | {scenario, status, decision: .decision.command}'

# 6. 清理
cd test-containers
docker-compose down
```

### 单个场景测试

```python
# 使用Python快速测试单个容器
from watchdog.evidence import collect_evidence
import json

evidence = collect_evidence('cpu-stress')
print(json.dumps(evidence, indent=2, ensure_ascii=False))
```

## 🎯 测试目标和验证点

### DeepSeek决策准确性

- [ ] 正常容器判断为NONE
- [ ] CPU 50%判断为NONE（未达阈值）
- [ ] CPU 100%判断为ALERT_ONLY（达到limit但未崩溃）
- [ ] 内存70-90%判断为ALERT_ONLY
- [ ] 内存>90%判断为RESTART
- [ ] 容器崩溃判断为RESTART
- [ ] OOM Killed判断为RESTART
- [ ] 频繁重启判断为STOP

### 数据格式正确性

- [ ] 所有evidence包含必需字段
- [ ] CPU/内存值为合法百分比
- [ ] DeepSeek返回符合JSON Schema
- [ ] fault_type在枚举范围内（含模糊匹配）

### 系统健壮性

- [ ] 处理大JSON输入（1800+字符）
- [ ] 处理DeepSeek的命名变体（如CRASH vs PROCESS_CRASH）
- [ ] API错误时有明确提示
- [ ] 容器异常时能正常收集数据

## 📚 进阶测试

### 压力测试

```bash
# 同时收集多个容器
for container in normal-app cpu-stress memory-leak; do
  python3 -c "
from watchdog.evidence import collect_evidence
import json
e = collect_evidence('$container')
print(json.dumps(e, indent=2))
" > logs/batch_${container}.json
done
```

### 性能测试

```bash
# 测试evidence收集速度
time python3 -c "
from watchdog.evidence import collect_evidence
for i in range(10):
    collect_evidence('normal-app')
"
```

### 错误注入测试

```bash
# 停止容器测试错误处理
docker stop cpu-stress
python3 -c "
from watchdog.evidence import collect_evidence
e = collect_evidence('cpu-stress')
print('Status:', e['container']['status'] if e else 'None')
"
docker start cpu-stress
```

## 🛠️ 故障排查

### 容器未启动

```bash
docker-compose ps
docker-compose logs cpu-stress
```

### stress-ng未生效

```bash
docker exec cpu-stress ps aux | grep stress
docker exec cpu-stress sh -c 'pkill stress-ng && stress-ng --cpu 2 &'
```

### Evidence收集失败

```bash
# 检查Docker权限
docker ps

# 检查容器是否存在
docker inspect cpu-stress

# 手动测试
python3 -c "from watchdog.evidence import collect_evidence; print(collect_evidence('cpu-stress'))"
```

## 📖 相关文档

- `test-containers/README_TYPICAL_SCENARIOS.md` - 容器详细说明
- `CODE_LEARNING_SESSION.md` - 代码学习指南
- `TEST_DATA_AUTHENTICITY.md` - 数据真实性说明
- `docs/HTTP_STATUS_EXPLANATION.md` - HTTP状态处理

## ⚠️ 注意事项

1. **资源消耗**: 扩展容器会占用约2GB内存，请确保主机资源充足
2. **数据保留**: logs/目录的JSON文件是宝贵测试数据，不要误删
3. **国内网络**: Dockerfile已配置阿里云镜像源，构建速度快
4. **清理习惯**: 测试完记得`docker-compose down`释放资源
5. **并发限制**: 收集evidence时避免并发，可能影响指标准确性

# 典型测试场景容器说明

本目录包含用于Cloud Watchdog测试的各种典型故障场景容器。

## 容器列表

### 1. normal-app (正常容器)
- **用途**: 基准对照，正常运行的容器
- **资源**: CPU 0.5核, 内存 128M
- **预期状态**: 运行正常，无告警
- **evidence特征**: CPU < 5%, 内存 < 10%

### 2. cpu-stress (CPU压力)
- **用途**: 测试CPU高负载场景
- **资源**: CPU 0.5核, 内存 128M
- **工具**: stress-ng
- **配置**:
  - 默认: 2 workers → CPU ~50%
  - 高压: 4 workers → CPU ~100% (打满limit)
- **预期决策**:
  - 50%: NONE (未达70%阈值)
  - 100%: ALERT_ONLY (已达limit但未崩溃)

### 3. memory-leak (内存压力)
- **用途**: 测试内存高负载和泄漏场景
- **资源**: CPU 0.5核, 内存 256M
- **工具**: stress-ng --vm
- **配置**:
  - 默认: 200M → 内存 ~80%
  - 高压: 240M → 内存 ~95%
- **预期决策**:
  - 80%: ALERT_ONLY (70-90%告警区间)
  - 95%: RESTART (接近OOM)

### 4. crash-loop (崩溃容器)
- **用途**: 测试容器崩溃和重启场景
- **资源**: CPU 0.2核, 内存 64M
- **行为**: 每60秒exit(1)
- **预期决策**: RESTART

### 5. unhealthy-app (健康检查失败)
- **用途**: 测试健康检查失败场景
- **资源**: CPU 0.2核, 内存 64M
- **服务**: Flask HTTP服务器
- **配置**: FAIL_RATE环境变量控制失败率
- **预期决策**: RESTART或ALERT_ONLY

## 资源限制设计原则

### CPU限制
- 使用 `cpus: 0.5` 而非绝对值，更灵活
- CPU百分比是相对于**整个主机**，不是容器limit
- 示例: 4核主机上，0.5核 = 12.5%主机CPU

### 内存限制
- 使用合理的limit值便于触发OOM
- 测试容器使用小内存 (64M-256M) 方便快速测试
- 内存百分比是相对于**容器limit**

## 典型Evidence值

### 正常运行
```json
{
  "cpu_percent": "0.00%",
  "memory_percent": "1.20%",
  "exit_code": 0,
  "oom_killed": false,
  "status": "running"
}
```

### CPU高负载 (50%)
```json
{
  "cpu_percent": "50.34%",
  "memory_percent": "6.05%",
  "exit_code": 0,
  "status": "running"
}
```

### 内存高负载 (80%)
```json
{
  "cpu_percent": "50.52%",
  "memory_percent": "79.99%",
  "memory_usage": "204.8MiB / 256MiB",
  "exit_code": 0,
  "status": "running"
}
```

### 容器崩溃
```json
{
  "cpu_percent": "0.00%",
  "memory_percent": "0.00%",
  "exit_code": 1,
  "status": "exited",
  "error": "..."
}
```

### OOM Killed
```json
{
  "exit_code": 137,
  "oom_killed": true,
  "status": "exited",
  "error": "OOMKilled"
}
```

## 使用方法

### 1. 启动所有测试容器
```bash
docker-compose up -d
```

### 2. 收集典型evidence
```bash
python3 ../collect_typical_evidence.py
```

### 3. 运行DeepSeek测试
```bash
python3 ../test_deepseek_complete.py
```

### 4. 临时调整压力
```bash
# 增加CPU压力到100%
docker exec cpu-stress sh -c 'pkill stress-ng && stress-ng --cpu 4 --timeout 0 &'

# 增加内存到95%
docker exec memory-leak sh -c 'pkill stress-ng && stress-ng --vm 1 --vm-bytes 240M --timeout 0 &'

# 恢复默认配置
docker-compose restart cpu-stress memory-leak
```

## 注意事项

1. **国内镜像源**: cpu-stress和memory-leak的Dockerfile已配置阿里云源加速
2. **压力工具**: 使用stress-ng而非自写脚本，更安全可控
3. **资源清理**: 测试后记得清理临时容器
4. **数据保留**: logs/目录的evidence文件是宝贵的测试数据，不要误删

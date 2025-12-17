# LangGraph Agent 快速开始

**5分钟启动 Cloud Watchdog（基于 LangGraph）**

---

## 📦 前置要求

- Python 3.8+
- Docker
- DeepSeek API Key（[获取地址](https://platform.deepseek.com/)）

---

## ⚡ 快速启动（3步）

### 1. 安装依赖

```bash
cd /home/lyb/cloud-watchdog
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
export DEEPSEEK_API_KEY="sk-your-api-key-here"
```

### 3. 运行测试

```bash
# 快速验证（离线测试，不需要 API Key）
python tests/test_agent.py --offline

# 完整验证（在线测试，需要 API Key）
python tests/test_agent.py --online
```

---

## 🚀 启动监控

```bash
python main.py
```

或后台运行：

```bash
nohup python main.py > logs/monitor.out 2>&1 &
```

---

## 📊 验证运行

### 查看日志
```bash
tail -f logs/watchdog.log
```

### 触发测试告警
```bash
cd test-containers
docker-compose up -d cpu-stress
```

### 检查诊断结果
```bash
ls -lh logs/test_agent_*.json
cat logs/watchdog.log | grep "诊断"
```

---

## 🔧 常见问题

### Q: 如何检查配置？

```bash
python -c "
from watchdog.config import get_config
config = get_config()
print(f'LLM Provider: {config.llm.provider}')
print(f'LLM Model: {config.llm.model}')
print(f'API Key 已配置: {bool(config.llm.api_key)}')
"
```

### Q: 如何测试 API 连接？

```bash
python -c "
from watchdog.agent import analyze_with_llm
from watchdog.config import init_config

init_config()

evidence = {
    'container': {'name': 'test'},
    'evidence': {'cpu_percent': '5%'},
    'fault_type': 'UNKNOWN',
    'thresholds': {}
}

decision = analyze_with_llm(evidence)
print(f\"✅ API 连接正常，决策: {decision['command']}\")
"
```

### Q: 如何停止监控？

```bash
# 查找进程
ps aux | grep "python main.py"

# 停止进程
kill <PID>
```

---

## 📚 下一步

- [完整迁移指南](docs/MIGRATION_TO_LANGGRAPH.md)
- [测试指南](TESTING_GUIDE.md)
- [架构文档](TEST_INFRASTRUCTURE.md)

---

## 💡 提示

1. **API Key 安全**：使用环境变量而非硬编码
2. **测试优先**：先运行测试再启动生产监控
3. **日志监控**：定期检查 `logs/watchdog.log`
4. **资源限制**：注意测试容器的资源消耗

---

**遇到问题？** 查看 [故障排查](docs/MIGRATION_TO_LANGGRAPH.md#故障排查)

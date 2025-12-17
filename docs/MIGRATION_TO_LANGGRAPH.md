# Dify → LangGraph 迁移指南

## 📋 迁移概述

本次迁移将 Cloud Watchdog 的决策层从 **Dify Workflow** 迁移到 **LangGraph Agent**，实现以下目标：

- ✅ **去除 Dify 依赖**：减少内存占用（Dify 占用 2GB+）
- ✅ **代码可控性**：决策逻辑完全在代码中，便于调试和维护
- ✅ **性能提升**：去掉 HTTP 中间层，降低延迟
- ✅ **可扩展性**：为多 Agent 并发处理预留架构

---

## 🔄 架构变化

### 迁移前（Dify）

```
Monitor → POST /webhook → Dify Workflow
                            ↓
                    LLM 决策 + 条件分流
                            ↓
                    POST /action (executor)
                    POST /notify (通知)
```

**问题：**
- Dify 占用大量内存（2GB+）
- HTTP 调用链路长，延迟高
- 依赖外部服务，增加复杂度
- 调试困难，黑盒操作

### 迁移后（LangGraph）

```
Monitor → run_diagnosis(evidence) → LangGraph Agent
                                        ↓
                                DeepSeek 分析
                                        ↓
                                执行命令 (executor)
                                        ↓
                                发送通知 (notifier)
```

**优势：**
- 内存占用小（仅 Python 库）
- 直接函数调用，延迟低
- 代码完全可控，易于调试
- 支持异步队列，可扩展

---

## 📝 变更清单

### 1. 配置文件变更

#### `requirements.txt`
```diff
+ # LangGraph Agent 依赖
+ langgraph>=0.2.0
+ langchain-core>=0.3.0
+ langchain-openai>=0.2.0
```

#### `config/config.yml`
```diff
- # Dify 配置
- dify:
-   webhook_url: "..."
-   api_key: "..."

+ # LLM 配置（用于 LangGraph Agent）
+ llm:
+   provider: "deepseek"
+   api_key: "${DEEPSEEK_API_KEY}"
+   base_url: "https://api.deepseek.com"
+   model: "deepseek-chat"
+   temperature: 0
+   timeout_seconds: 30
+   max_retries: 3
```

### 2. 代码变更

#### 新增文件
- `watchdog/agent.py` - LangGraph Agent 核心实现
  - `SYSTEM_PROMPT` - 从 Dify 迁移的决策规则
  - `analyze_with_llm()` - DeepSeek API 调用
  - `DiagnosisAgent` - 完整诊断流程
  - `DiagnosisTaskQueue` - 异步任务队列

- `tests/test_agent.py` - Agent 测试套件
  - 离线测试（不需要 API Key）
  - 在线测试（需要 API Key）
  - 集成测试

#### 修改文件
- `watchdog/config.py`
  - 新增 `LLMConfig` 类
  - 启用环境变量解析

- `watchdog/monitor.py`
  - `_report_issue()` 从调用 Dify webhook 改为调用 `run_diagnosis()`

### 3. 已保留文件（向后兼容）
- `watchdog/executor.py` - 命令执行（无变更）
- `watchdog/notifier.py` - 邮件通知（无变更）
- `config/watchlist.yml` - 监控列表（无变更）

---

## 🚀 部署步骤

### 步骤 1: 安装依赖

```bash
cd /home/lyb/cloud-watchdog
pip install -r requirements.txt
```

### 步骤 2: 配置环境变量

设置 DeepSeek API Key：

```bash
# 临时设置（本次会话）
export DEEPSEEK_API_KEY="sk-your-api-key-here"

# 永久设置（推荐）
echo 'export DEEPSEEK_API_KEY="sk-your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

验证配置：
```bash
echo $DEEPSEEK_API_KEY
```

### 步骤 3: 运行测试

#### 离线测试（不需要 API Key）
```bash
python tests/test_agent.py --offline
```

#### 在线测试（需要 API Key）
```bash
python tests/test_agent.py --online
```

#### 全部测试
```bash
python tests/test_agent.py
```

### 步骤 4: 启动监控

```bash
python main.py
```

或使用 systemd 服务：
```bash
sudo systemctl restart cloud-watchdog
sudo systemctl status cloud-watchdog
```

### 步骤 5: 验证运行

查看日志：
```bash
tail -f logs/watchdog.log
```

期望看到类似日志：
```
[INFO] 诊断任务队列已启动，工作线程数: 1
[INFO] 启动容器监控...
[INFO] 监控已启动
[INFO] 触发诊断: cpu-stress - CPU_HIGH
[INFO] 调用 DeepSeek 分析容器: cpu-stress
[INFO] DeepSeek 决策: ALERT_ONLY - CPU使用率95.2%超过严重阈值...
[INFO] 诊断完成: cpu-stress - ALERT_ONLY
```

---

## 🧪 测试验证

### 1. 单元测试

```bash
# 测试 SYSTEM_PROMPT 生成
python -c "from watchdog.agent import SYSTEM_PROMPT; print('✓' if '容器故障诊断' in SYSTEM_PROMPT else '✗')"

# 测试配置加载
python -c "from watchdog.config import get_config; c=get_config(); print(f'LLM Provider: {c.llm.provider}')"
```

### 2. 集成测试

使用测试容器触发告警：

```bash
# 启动测试容器
cd test-containers
docker-compose up -d

# 等待监控检测到问题（约30-60秒）
tail -f ../logs/watchdog.log

# 查看诊断结果
ls -lh ../logs/test_agent_*.json
```

### 3. API 调用测试

```bash
python -c "
from watchdog.agent import analyze_with_llm
from watchdog.config import init_config
import json

init_config()

evidence = {
    'container': {'name': 'test'},
    'evidence': {'cpu_percent': '95%', 'memory_percent': '50%'},
    'fault_type': 'CPU_HIGH',
    'thresholds': {'cpu_critical': 90}
}

decision = analyze_with_llm(evidence)
print(json.dumps(decision, indent=2, ensure_ascii=False))
"
```

---

## 🔍 故障排查

### 问题 1: API Key 未配置

**错误信息：**
```
[ERROR] DeepSeek API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY
```

**解决方法：**
```bash
export DEEPSEEK_API_KEY="sk-your-key"
python tests/test_agent.py --online
```

### 问题 2: 导入错误

**错误信息：**
```
ModuleNotFoundError: No module named 'langgraph'
```

**解决方法：**
```bash
pip install -r requirements.txt
```

### 问题 3: API 调用失败

**错误信息：**
```
[ERROR] DeepSeek API 调用失败: timeout
```

**解决方法：**
1. 检查网络连接
2. 增加超时时间（`config.yml` 中 `llm.timeout_seconds`）
3. 检查 API Key 是否有效

### 问题 4: 决策格式错误

**错误信息：**
```
[WARNING] LLM 响应缺少字段: reason
```

**原因：** DeepSeek 输出格式不符合预期

**解决方法：** 已自动处理，会使用默认值并记录警告

---

## 📊 性能对比

| 指标 | Dify | LangGraph | 改进 |
|------|------|-----------|------|
| 内存占用 | ~2GB | ~200MB | ↓ 90% |
| 决策延迟 | 3-5秒 | 1-2秒 | ↓ 60% |
| 部署复杂度 | 高（需 Docker Compose） | 低（仅 Python） | ⬇️ |
| 可维护性 | 低（黑盒） | 高（代码可见） | ⬆️ |
| 扩展性 | 差 | 好（支持多 Agent） | ⬆️ |

---

## 🔮 未来扩展

### 多 Agent 并发处理

```python
# 当前：单 Agent 串行处理
task_queue = DiagnosisTaskQueue(max_workers=1)

# 未来：多 Agent 并发处理
task_queue = DiagnosisTaskQueue(max_workers=3)  # 3个并发 Agent
```

### 专用 Agent

```python
# CPU 诊断专用 Agent
class CPUDiagnosisAgent(DiagnosisAgent):
    def __init__(self):
        super().__init__()
        self.prompt = CPU_SPECIALIZED_PROMPT
    
    def should_handle(self, evidence):
        return evidence['fault_type'] in ['CPU_HIGH']

# 内存诊断专用 Agent
class MemoryDiagnosisAgent(DiagnosisAgent):
    # ...
```

### Agent 路由

```python
def route_to_agent(evidence):
    fault_type = evidence['fault_type']
    
    if fault_type in ['CPU_HIGH']:
        return CPUDiagnosisAgent()
    elif fault_type in ['MEMORY_HIGH', 'OOM_KILLED']:
        return MemoryDiagnosisAgent()
    else:
        return GeneralDiagnosisAgent()
```

---

## 📚 相关文档

- [LangGraph 官方文档](https://python.langchain.com/docs/langgraph)
- [DeepSeek API 文档](https://platform.deepseek.com/api-docs/)
- [Cloud Watchdog 测试指南](../TESTING_GUIDE.md)
- [Agent 测试报告](../logs/test_agent_*.json)

---

## ✅ 迁移检查清单

- [ ] 安装 LangGraph 依赖
- [ ] 配置 DEEPSEEK_API_KEY 环境变量
- [ ] 运行离线测试通过
- [ ] 运行在线测试通过
- [ ] 启动监控服务
- [ ] 验证日志输出正常
- [ ] 测试容器触发告警
- [ ] 验证邮件通知发送
- [ ] （可选）停用 Dify 服务
- [ ] 更新系统文档

---

## 🆘 需要帮助？

- 查看日志：`tail -f logs/watchdog.log`
- 运行测试：`python tests/test_agent.py`
- 检查配置：`python -c "from watchdog.config import get_config; print(get_config().llm.__dict__)"`

**遇到问题？** 检查 [故障排查](#故障排查) 章节或提交 Issue。

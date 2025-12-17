# 测试基础设施总览

本文档列出Cloud Watchdog项目中所有重要的测试脚本和容器配置。

## 🎯 核心测试文件（必读必用）

| 文件 | 类型 | 用途 | 优先级 |
|------|------|------|--------|
| `collect_typical_evidence.py` | Python脚本 | 收集8种典型故障场景的evidence数据 | ⭐⭐⭐ |
| `test_deepseek_complete.py` | Python脚本 | 使用完整prompt测试DeepSeek决策准确性 | ⭐⭐⭐ |
| `test-containers/docker-compose.yml` | Docker配置 | 基础测试容器（5个） | ⭐⭐⭐ |
| `TESTING_GUIDE.md` | 文档 | 测试工作流和命令速查 | ⭐⭐⭐ |

## 📦 测试容器配置

### 基础容器（docker-compose.yml）
```
normal-app      - 正常运行容器（对照组）
cpu-stress      - CPU压力测试（可调50%-100%）
memory-leak     - 内存压力测试（可调80%-95%）
crash-loop      - 容器崩溃测试
unhealthy-app   - 健康检查失败测试
```

### 扩展容器（docker-compose.extended.yml）
```
oom-test        - OOM Killer测试（新增）
cpu-extreme     - CPU极限压力100%（新增）
memory-extreme  - 内存极限压力97%（新增）
restart-loop    - 频繁重启测试（新增）
```

### 容器Dockerfile位置
```
test-containers/
├── normal-app/Dockerfile
├── cpu-stress/Dockerfile       ← 已优化：国内镜像源
├── memory-leak/Dockerfile      ← 已优化：国内镜像源
├── crash-loop/Dockerfile
├── unhealthy-app/Dockerfile
└── oom-test/Dockerfile         ← 新增：专门OOM测试
```

## 📊 Evidence数据存储

### 数据目录结构
```
logs/
├── normal_running_*.json          - 正常运行
├── cpu_50percent_*.json           - CPU 50%
├── cpu_100percent_*.json          - CPU 100%（新）
├── memory_80percent_*.json        - 内存 80%
├── memory_95percent_*.json        - 内存 95%（新）
├── container_crash_*.json         - 容器崩溃
├── oom_killed_*.json              - OOM被杀（新）
├── high_restart_count_*.json      - 频繁重启（新）
└── test_results_complete.json     - DeepSeek测试结果
```

### 数据特征
- **真实性**: 100%来自Docker API
- **完整性**: 1800+字符完整JSON
- **典型性**: 覆盖8种典型故障场景
- **可复现**: 脚本化收集，随时可重新生成

## 🔧 测试脚本详解

### collect_typical_evidence.py
**功能**:
- 自动收集8种典型故障场景
- 临时调整容器压力参数
- 保存带元数据的evidence JSON
- 收集后自动恢复容器状态

**使用**:
```bash
python3 collect_typical_evidence.py
```

**输出示例**:
```
【场景1】正常运行容器
  📁 保存: normal_running_20251204_143000.json
  📊 CPU: 0.00%, 内存: 1.20%, 状态: running, 退出码: 0

【场景2】CPU 50% - 未达警告阈值
  📁 保存: cpu_50percent_20251204_143010.json
  📊 CPU: 50.34%, 内存: 6.05%, 状态: running, 退出码: 0

...共8个场景
```

### test_deepseek_complete.py
**功能**:
- 读取logs/中的evidence文件
- 使用**完整系统提示词**（含few-shot）
- 发送**完整evidence JSON**
- 验证决策准确性和格式正确性

**使用**:
```bash
python3 test_deepseek_complete.py
```

**验证点**:
- ✅ fault_type枚举（模糊匹配）
- ✅ command枚举
- ✅ JSON Schema完整性
- ✅ 决策逻辑准确性

## 🎨 设计原则

### 1. 可复现性
所有测试场景都可通过脚本重现，不依赖手动操作。

### 2. 数据真实性
Evidence 100%来自真实Docker容器，不用mock数据。

### 3. 场景典型性
覆盖生产环境常见的8种故障场景：
- 正常运行
- CPU压力（低/高）
- 内存压力（低/高）
- 容器崩溃
- OOM Killed
- 频繁重启

### 4. 易于维护
- 脚本有详细注释
- 配置集中管理
- 容器可独立测试
- 文档完整清晰

## 🚀 快速测试流程

### 首次测试（完整流程）
```bash
# 1. 启动容器
cd test-containers
docker-compose up -d
sleep 35  # 等待stress-ng启动

# 2. 收集evidence
cd ..
python3 collect_typical_evidence.py

# 3. 测试DeepSeek
python3 test_deepseek_complete.py

# 4. 查看结果
ls -lh logs/
cat logs/test_results_complete.json | jq
```

### 日常测试（使用现有数据）
```bash
# 直接测试，不重新收集
python3 test_deepseek_complete.py
```

### 更新数据（场景变化时）
```bash
# 重新收集所有场景
python3 collect_typical_evidence.py

# 或手动收集单个场景
python3 -c "
from watchdog.evidence import collect_evidence
import json
from pathlib import Path

e = collect_evidence('cpu-stress')
Path('logs/cpu_manual.json').write_text(
    json.dumps(e, ensure_ascii=False, indent=2)
)
"
```

## 📖 相关文档索引

| 文档 | 内容 |
|------|------|
| `TESTING_GUIDE.md` | 测试命令速查和工作流 |
| `test-containers/README_TYPICAL_SCENARIOS.md` | 容器详细说明 |
| `TEST_DATA_AUTHENTICITY.md` | 数据真实性说明 |
| `CODE_LEARNING_SESSION.md` | 代码学习路径 |

## 🔍 故障排查速查

### 容器未启动
```bash
docker-compose ps
docker-compose logs -f cpu-stress
```

### Evidence收集失败
```bash
# 检查容器
docker ps -a | grep cpu-stress

# 手动测试
python3 -c "from watchdog.evidence import collect_evidence; print(collect_evidence('cpu-stress'))"
```

### DeepSeek测试失败
```bash
# 检查API key
env | grep DEEPSEEK

# 检查网络
curl -I https://api.deepseek.com

# 查看详细错误
python3 test_deepseek_complete.py 2>&1 | tee test_debug.log
```

## ✅ 测试清单

完成测试前确认：
- [ ] 测试容器已启动（docker-compose ps）
- [ ] stress-ng已启动（等待35秒或检查进程）
- [ ] logs/目录下有至少5个evidence文件
- [ ] DeepSeek API key已配置
- [ ] 网络连接正常

## 💡 最佳实践

1. **定期重新收集**: 代码或配置变化后重新收集evidence
2. **保留历史数据**: 用时间戳区分不同批次的数据
3. **版本控制**: evidence文件建议加入.gitignore，避免仓库膨胀
4. **文档更新**: 添加新场景时更新本文档
5. **清理资源**: 测试完成后`docker-compose down`

## 📝 未来改进方向

- [ ] 添加GPU压力测试容器
- [ ] 添加网络I/O压力测试
- [ ] 支持批量测试和报告生成
- [ ] 集成CI/CD自动化测试
- [ ] 添加性能基准测试

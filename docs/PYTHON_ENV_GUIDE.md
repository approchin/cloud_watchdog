# Python 环境管理：Poetry vs uv

## 🔍 当前环境状态

- **系统 Python**: 3.10.12 (`/usr/bin/python3`)
- **Poetry**: 已安装 (v1.1.12)
- **uv**: 未安装

---

## 📊 Poetry vs uv 对比

### Poetry（传统方案）

**特点**：
- 成熟稳定，社区广泛使用
- 功能完整：依赖管理、打包、发布
- 配置文件：`pyproject.toml` + `poetry.lock`
- 速度：较慢（依赖解析用纯 Python）

**虚拟环境位置**：
```bash
# Poetry 默认虚拟环境路径
~/.cache/pypoetry/virtualenvs/cloud-watchdog-xxxxx-py3.10/

# 或配置为项目内（推荐）
poetry config virtualenvs.in-project true
# 则在项目根目录创建 .venv/
```

**Python 可执行文件**：
```bash
~/.cache/pypoetry/virtualenvs/cloud-watchdog-xxxxx-py3.10/bin/python
# 或
项目目录/.venv/bin/python
```

---

### uv（现代方案，推荐）⚡

**特点**：
- **超快速度**：用 Rust 编写，比 pip/poetry 快 10-100 倍
- **兼容性好**：完全兼容 pip 生态，可读取 `requirements.txt`
- **内置虚拟环境管理**：自动创建和管理
- **无需额外配置**：开箱即用
- **占用空间小**：智能缓存，节省磁盘

**虚拟环境位置**：
```bash
# uv 默认在项目目录创建
项目目录/.venv/

# 全局缓存（包缓存）
~/.cache/uv/
```

**Python 可执行文件**：
```bash
项目目录/.venv/bin/python
```

---

## 🎯 推荐方案：使用 uv

### 为什么选择 uv？

1. **速度快**：依赖解析和安装速度提升 10-100 倍
2. **简单**：命令更简洁，学习成本低
3. **兼容**：可以无缝迁移现有项目
4. **环境隔离**：每个项目独立 `.venv/` 目录
5. **现代化**：2023 年发布，采用最新技术栈

---

## 📦 安装 uv

```bash
# 方式一：官方推荐（最快）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 方式二：使用 pip
pip install uv

# 方式三：使用 pipx（推荐，全局工具）
pipx install uv
```

安装后需要重新加载 shell：
```bash
source ~/.bashrc
# 或
source ~/.zshrc
```

---

## 🚀 Cloud Watchdog 项目配置

### 使用 uv 创建虚拟环境

```bash
cd /home/lyb/cloud-watchdog

# 1. 创建虚拟环境（基于 Python 3.10）
uv venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖（从 requirements.txt）
uv pip install -r requirements.txt

# 4. 验证安装
python --version
which python
# 应该显示：/home/lyb/cloud-watchdog/.venv/bin/python
```

---

## 🔄 如果使用 Poetry（备选方案）

```bash
cd /home/lyb/cloud-watchdog

# 1. 配置 Poetry 在项目内创建虚拟环境
poetry config virtualenvs.in-project true

# 2. 初始化项目（会创建 pyproject.toml）
poetry init --no-interaction

# 3. 从 requirements.txt 添加依赖
cat requirements.txt | grep -v "^#" | xargs poetry add

# 4. 激活虚拟环境
poetry shell

# 5. 验证
which python
# 应该显示：/home/lyb/cloud-watchdog/.venv/bin/python
```

---

## 📋 常用命令对比

| 操作 | Poetry | uv |
|-----|--------|-----|
| **创建虚拟环境** | `poetry install` | `uv venv` |
| **激活环境** | `poetry shell` | `source .venv/bin/activate` |
| **安装依赖** | `poetry add requests` | `uv pip install requests` |
| **从文件安装** | `poetry add $(cat requirements.txt)` | `uv pip install -r requirements.txt` |
| **运行脚本** | `poetry run python main.py` | `python main.py`（激活后） |
| **查看依赖** | `poetry show` | `uv pip list` |
| **卸载依赖** | `poetry remove requests` | `uv pip uninstall requests` |
| **导出依赖** | `poetry export -f requirements.txt` | `uv pip freeze > requirements.txt` |

---

## 🎯 环境隔离最佳实践

### 1. 项目目录结构
```
cloud-watchdog/
├── .venv/                  # 虚拟环境（uv 或 poetry 创建）
│   ├── bin/
│   │   └── python         # 隔离的 Python 可执行文件
│   ├── lib/
│   │   └── python3.10/    # 隔离的依赖包
│   └── pyvenv.cfg
├── watchdog/              # 项目代码
├── requirements.txt       # 依赖列表
└── .gitignore            # 忽略 .venv/
```

### 2. .gitignore 配置
```
.venv/
__pycache__/
*.pyc
```

### 3. IDE 配置
在 VSCode/Windsurf 中设置 Python 解释器：
```
/home/lyb/cloud-watchdog/.venv/bin/python
```

### 4. 运行项目
```bash
# 激活环境
cd /home/lyb/cloud-watchdog
source .venv/bin/activate

# 运行
python -m watchdog.main --host 0.0.0.0 --port 9999

# 退出环境
deactivate
```

---

## 🔍 检查环境隔离

```bash
# 激活虚拟环境后
which python
# 输出：/home/lyb/cloud-watchdog/.venv/bin/python

pip list
# 只显示项目依赖，不包含系统包

echo $VIRTUAL_ENV
# 输出：/home/lyb/cloud-watchdog/.venv
```

---

## 💡 推荐工作流程

### 使用 uv（推荐）
```bash
# 一次性设置
cd /home/lyb/cloud-watchdog
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 日常开发
cd /home/lyb/cloud-watchdog
source .venv/bin/activate  # 激活环境
python -m watchdog.main    # 运行项目
deactivate                 # 结束后退出
```

### 使用 Poetry
```bash
# 一次性设置
cd /home/lyb/cloud-watchdog
poetry config virtualenvs.in-project true
poetry init
cat requirements.txt | grep -v "^#" | xargs poetry add

# 日常开发
cd /home/lyb/cloud-watchdog
poetry shell              # 激活环境
python -m watchdog.main   # 运行项目
exit                      # 结束后退出
```

---

## 🎓 学习建议

1. **初学者**：推荐 uv
   - 命令简单，接近原生 pip
   - 速度快，体验好
   - 文档清晰

2. **专业项目**：uv 或 Poetry 都可以
   - uv：速度优先
   - Poetry：功能全面，打包发布更方便

3. **团队协作**：看团队习惯
   - 已有 `pyproject.toml` → Poetry
   - 只有 `requirements.txt` → uv

---

## 📚 参考资源

- **uv 官网**: https://github.com/astral-sh/uv
- **Poetry 官网**: https://python-poetry.org/
- **虚拟环境文档**: https://docs.python.org/3/library/venv.html

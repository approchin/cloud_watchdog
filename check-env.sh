#!/bin/bash
# Cloud Watchdog 环境检查脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}Cloud Watchdog 环境检查${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# 检查计数
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}!${NC} $1"
    ((WARN_COUNT++))
}

# 1. 检查 Python
echo -e "${YELLOW}[1] 检查 Python 环境${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    check_pass "Python 已安装: ${PYTHON_VERSION}"
else
    check_fail "Python3 未安装"
fi

# 检查 pip
if command -v pip3 &> /dev/null; then
    check_pass "pip3 已安装"
else
    check_fail "pip3 未安装"
fi
echo ""

# 2. 检查 Python 依赖
echo -e "${YELLOW}[2] 检查 Python 依赖${NC}"
REQUIRED_PACKAGES=("requests" "yaml" "fastapi" "uvicorn" "pydantic")
for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $pkg" &> /dev/null; then
        check_pass "$pkg 已安装"
    else
        check_fail "$pkg 未安装"
    fi
done
echo ""

# 3. 检查 Docker
echo -e "${YELLOW}[3] 检查 Docker 环境${NC}"
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    check_pass "Docker 已安装: ${DOCKER_VERSION}"
    
    # 检查 Docker 权限
    if docker ps &> /dev/null; then
        check_pass "Docker 权限正常"
    else
        check_fail "Docker 权限不足（提示: sudo usermod -aG docker \$USER）"
    fi
    
    # 检查 Docker Compose
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f3 | tr -d ',')
        check_pass "Docker Compose 已安装: ${COMPOSE_VERSION}"
    else
        check_warn "Docker Compose 未安装（测试容器需要）"
    fi
else
    check_fail "Docker 未安装"
fi
echo ""

# 4. 检查配置文件
echo -e "${YELLOW}[4] 检查配置文件${NC}"
if [ -f "config/config.yml" ]; then
    check_pass "config/config.yml 存在"
    
    # 检查关键配置
    if grep -q "webhook_url.*localhost" config/config.yml; then
        check_warn "Dify webhook_url 使用默认值，需要修改"
    else
        check_pass "Dify webhook_url 已配置"
    fi
    
    if grep -q "host.*127.0.0.1" config/config.yml; then
        check_warn "executor.host 为 127.0.0.1，仅本地访问"
    else
        check_pass "executor.host 已配置"
    fi
    
    if grep -q 'sender: ""' config/config.yml; then
        check_warn "邮件 sender 未配置"
    else
        check_pass "邮件 sender 已配置"
    fi
else
    check_fail "config/config.yml 不存在"
fi

if [ -f "config/watchlist.yml" ]; then
    CONTAINER_COUNT=$(grep -c "name:" config/watchlist.yml || echo 0)
    check_pass "config/watchlist.yml 存在 (${CONTAINER_COUNT} 个容器)"
else
    check_fail "config/watchlist.yml 不存在"
fi
echo ""

# 5. 检查目录结构
echo -e "${YELLOW}[5] 检查目录结构${NC}"
REQUIRED_DIRS=("watchdog" "config" "logs" "state")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_pass "$dir/ 目录存在"
    else
        check_fail "$dir/ 目录不存在"
    fi
done
echo ""

# 6. 检查核心模块
echo -e "${YELLOW}[6] 检查核心模块${NC}"
REQUIRED_FILES=(
    "watchdog/__init__.py"
    "watchdog/main.py"
    "watchdog/config.py"
    "watchdog/monitor.py"
    "watchdog/evidence.py"
    "watchdog/executor.py"
    "watchdog/api.py"
    "watchdog/notifier.py"
)
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "$file 存在"
    else
        check_fail "$file 不存在"
    fi
done
echo ""

# 7. 检查端口占用
echo -e "${YELLOW}[7] 检查端口占用${NC}"
PORT=9999
if command -v netstat &> /dev/null; then
    if netstat -tuln | grep ":${PORT}" &> /dev/null; then
        check_warn "端口 ${PORT} 已被占用"
    else
        check_pass "端口 ${PORT} 可用"
    fi
else
    check_warn "netstat 未安装，跳过端口检查"
fi
echo ""

# 汇总
echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}检查结果汇总${NC}"
echo -e "${BLUE}=================================${NC}"
echo -e "${GREEN}通过: ${PASS_COUNT}${NC}"
echo -e "${YELLOW}警告: ${WARN_COUNT}${NC}"
echo -e "${RED}失败: ${FAIL_COUNT}${NC}"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}❌ 环境检查失败，请先解决上述问题${NC}"
    exit 1
elif [ $WARN_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠️  环境检查通过，但有警告项需要关注${NC}"
    exit 0
else
    echo -e "${GREEN}✅ 环境检查全部通过，可以启动服务${NC}"
    exit 0
fi

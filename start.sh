#!/bin/bash
# Cloud Watchdog 快速启动脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}Cloud Watchdog 启动脚本${NC}"
echo -e "${GREEN}=================================${NC}"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未找到 docker${NC}"
    exit 1
fi

# 检查 Docker 权限
if ! docker ps &> /dev/null; then
    echo -e "${RED}错误: 无法执行 docker 命令，请检查权限${NC}"
    echo -e "${YELLOW}提示: sudo usermod -aG docker \$USER${NC}"
    exit 1
fi

# 检查依赖
echo -e "${YELLOW}检查 Python 依赖...${NC}"
if ! python3 -c "import requests, yaml, fastapi, uvicorn" &> /dev/null; then
    echo -e "${YELLOW}正在安装依赖...${NC}"
    pip3 install -r requirements.txt
fi

# 创建必要目录
mkdir -p logs state

# 检查配置文件
if [ ! -f "config/config.yml" ]; then
    echo -e "${RED}错误: config/config.yml 不存在${NC}"
    exit 1
fi

if [ ! -f "config/watchlist.yml" ]; then
    echo -e "${RED}错误: config/watchlist.yml 不存在${NC}"
    exit 1
fi

# 获取启动参数
HOST=${1:-0.0.0.0}
PORT=${2:-9999}
LOG_LEVEL=${3:-INFO}

echo ""
echo -e "${GREEN}启动参数:${NC}"
echo -e "  监听地址: ${HOST}"
echo -e "  监听端口: ${PORT}"
echo -e "  日志级别: ${LOG_LEVEL}"
echo ""

# 启动服务
echo -e "${GREEN}正在启动 Cloud Watchdog...${NC}"
python3 -m watchdog.main --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}"

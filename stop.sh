#!/bin/bash
# Cloud Watchdog 停止脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}正在停止 Cloud Watchdog...${NC}"

# 查找进程
PID=$(ps aux | grep "[p]ython3 -m watchdog.main" | awk '{print $2}')

if [ -z "$PID" ]; then
    echo -e "${YELLOW}未找到运行中的 Cloud Watchdog 进程${NC}"
    exit 0
fi

# 停止进程
echo -e "${YELLOW}找到进程 PID: ${PID}${NC}"
kill -TERM $PID

# 等待进程退出
sleep 2

# 检查是否已退出
if ps -p $PID > /dev/null 2>&1; then
    echo -e "${RED}进程未退出，强制终止...${NC}"
    kill -9 $PID
fi

echo -e "${GREEN}Cloud Watchdog 已停止${NC}"

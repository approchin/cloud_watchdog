#!/bin/bash
# Cloud Watchdog 状态检查脚本

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}Cloud Watchdog 状态检查${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# 1. 检查进程
echo -e "${YELLOW}[1] 进程状态${NC}"
PID=$(ps aux | grep "[p]ython3 -m watchdog.main" | awk '{print $2}')
if [ -z "$PID" ]; then
    echo -e "  状态: ${RED}未运行${NC}"
else
    echo -e "  状态: ${GREEN}运行中${NC}"
    echo -e "  PID: ${PID}"
    
    # CPU 和内存使用
    CPU=$(ps -p $PID -o %cpu= | xargs)
    MEM=$(ps -p $PID -o %mem= | xargs)
    echo -e "  CPU: ${CPU}%"
    echo -e "  内存: ${MEM}%"
fi
echo ""

# 2. 检查 API 服务
echo -e "${YELLOW}[2] API 服务${NC}"
if [ ! -z "$PID" ]; then
    PORT=$(netstat -tlnp 2>/dev/null | grep "$PID" | awk '{print $4}' | awk -F: '{print $NF}' | head -1)
    if [ -z "$PORT" ]; then
        echo -e "  端口: ${RED}未监听${NC}"
    else
        echo -e "  端口: ${GREEN}${PORT}${NC}"
        
        # 测试健康检查
        HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:${PORT}/health 2>/dev/null)
        if [ "$HEALTH" == "200" ]; then
            echo -e "  健康检查: ${GREEN}通过${NC}"
        else
            echo -e "  健康检查: ${RED}失败 (HTTP ${HEALTH})${NC}"
        fi
    fi
else
    echo -e "  端口: ${RED}服务未运行${NC}"
fi
echo ""

# 3. 检查 Docker
echo -e "${YELLOW}[3] Docker 状态${NC}"
if docker ps &> /dev/null; then
    CONTAINER_COUNT=$(docker ps | grep -E "normal-app|cpu-stress|memory-leak|crash-loop|unhealthy-app" | wc -l)
    echo -e "  Docker: ${GREEN}可用${NC}"
    echo -e "  监控容器数: ${CONTAINER_COUNT}"
else
    echo -e "  Docker: ${RED}不可用${NC}"
fi
echo ""

# 4. 检查日志
echo -e "${YELLOW}[4] 最新日志${NC}"
if [ -f "logs/watchdog.log" ]; then
    echo -e "  日志文件: ${GREEN}存在${NC}"
    LOG_SIZE=$(du -h logs/watchdog.log | cut -f1)
    echo -e "  日志大小: ${LOG_SIZE}"
    echo -e "  最新3行:"
    tail -3 logs/watchdog.log | sed 's/^/    /'
else
    echo -e "  日志文件: ${YELLOW}不存在${NC}"
fi
echo ""

# 5. 检查配置
echo -e "${YELLOW}[5] 配置文件${NC}"
if [ -f "config/config.yml" ]; then
    echo -e "  config.yml: ${GREEN}存在${NC}"
else
    echo -e "  config.yml: ${RED}缺失${NC}"
fi

if [ -f "config/watchlist.yml" ]; then
    WATCH_COUNT=$(grep -c "name:" config/watchlist.yml || echo 0)
    echo -e "  watchlist.yml: ${GREEN}存在 (${WATCH_COUNT} 个容器)${NC}"
else
    echo -e "  watchlist.yml: ${RED}缺失${NC}"
fi
echo ""

echo -e "${BLUE}=================================${NC}"

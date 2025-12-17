#!/bin/bash
# 内存压力容器

MEMORY_LIMIT=${MEMORY_LIMIT:-200}

echo "Memory stress container started"

# 等待一段时间后开始压力测试
sleep 30

echo "Starting high memory stress (${MEMORY_LIMIT}M)..."
stress-ng --vm 1 --vm-bytes ${MEMORY_LIMIT}M --timeout 0

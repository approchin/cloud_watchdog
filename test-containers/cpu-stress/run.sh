#!/bin/bash
# CPU 压力容器

echo "CPU stress container started"

# 等待一段时间后开始压力测试
sleep 30

echo "Starting high CPU stress..."
stress-ng --cpu 2 --timeout 0

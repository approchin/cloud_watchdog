#!/bin/bash
# OOM测试脚本 - 故意分配超过limit的内存

echo "========================================="
echo "OOM 测试容器启动"
echo "========================================="
echo "内存限制: 检查docker run --memory参数"
echo "计划分配: ${ALLOC_MEMORY}MB"
echo "========================================="

# 等待5秒让容器信息被监控系统收集
echo "等待5秒..."
sleep 5

# 开始分配内存，故意触发OOM
echo "开始分配内存 ${ALLOC_MEMORY}MB (将触发OOM)..."

# 使用stress-ng分配内存
# --vm-hang 0 确保内存一直被占用
stress-ng --vm 1 --vm-bytes ${ALLOC_MEMORY}M --vm-hang 0 --timeout 60s

# 如果stress-ng退出（被OOM killed），脚本会以137退出码结束
exit_code=$?
echo "stress-ng退出，退出码: $exit_code"

if [ $exit_code -eq 137 ]; then
    echo "容器被OOM Killer杀掉"
else
    echo "内存分配完成，未触发OOM"
fi

exit $exit_code

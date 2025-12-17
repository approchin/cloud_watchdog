#!/bin/bash
# 随机崩溃容器

CRASH_INTERVAL=${CRASH_INTERVAL:-60}

echo "Crash container started, will crash every ${CRASH_INTERVAL}s"

counter=0
while true; do
    counter=$((counter + 1))
    echo "[$(date)] Running... count=$counter"
    
    # 随机崩溃
    if [ $counter -ge $CRASH_INTERVAL ]; then
        echo "[$(date)] Simulating crash!"
        exit 1
    fi
    
    sleep 1
done

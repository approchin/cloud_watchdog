FROM python:3.9-slim

WORKDIR /app

# 换源：使用阿里云镜像加速 apt
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# 复制模拟脚本
COPY simulate_attack.py .

# 安装必要的工具 (netstat 用于网络连接模拟)
RUN apt-get update && apt-get install -y net-tools procps && rm -rf /var/lib/apt/lists/*

# 启动脚本
CMD ["python", "simulate_attack.py"]

# OOM测试容器 - 用于模拟内存超限被杀的场景
FROM alpine:3.18

# 使用阿里云镜像源加速
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    apk add --no-cache bash stress-ng

COPY oom-test.sh /app/oom-test.sh
RUN chmod +x /app/oom-test.sh

# 环境变量：分配多少内存（单位MB）
ENV ALLOC_MEMORY=100

CMD ["/app/oom-test.sh"]

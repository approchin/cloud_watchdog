# 随机崩溃容器
FROM alpine:3.18

RUN apk add --no-cache bash

COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]

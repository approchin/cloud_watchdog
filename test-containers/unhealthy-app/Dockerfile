# HTTP 服务容器（可模拟不健康状态）
FROM python:3.11-alpine

RUN pip install --no-cache-dir flask

COPY server.py /app/server.py

WORKDIR /app
EXPOSE 8080

CMD ["python", "server.py"]

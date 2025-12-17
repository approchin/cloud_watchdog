"""
简单的 HTTP 服务器，用于健康检查测试
"""
from flask import Flask, jsonify
import random
import os

app = Flask(__name__)

# 模拟间歇性故障
fail_rate = float(os.environ.get('FAIL_RATE', 0))

@app.route('/')
def index():
    return jsonify({"status": "ok", "service": "test-http"})

@app.route('/health')
def health():
    # 根据配置的失败率随机返回错误
    if random.random() < fail_rate:
        return jsonify({"status": "unhealthy"}), 500
    return jsonify({"status": "healthy"}), 200

@app.route('/crash')
def crash():
    """触发崩溃"""
    os._exit(1)

if __name__ == '__main__':
    print("HTTP server starting on port 8080...")
    app.run(host='0.0.0.0', port=8080)

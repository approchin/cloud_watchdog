import time
import sys
import os
import random
import threading
import socket

def log_injection_simulation():
    """模拟日志注入攻击"""
    patterns = [
        "ERROR: SQL syntax error near 'UNION SELECT * FROM users'",
        "WARNING: Invalid input detected: <script>alert(1)</script>",
        "INFO: User admin login failed. Password: ' OR '1'='1",
        "CRITICAL: Command execution attempt: ; cat /etc/passwd",
        "ERROR: ORA-00933: SQL command not properly ended"
    ]
    
    while True:
        # 随机选择一条攻击日志打印
        pattern = random.choice(patterns)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {pattern}", flush=True)
        time.sleep(random.randint(5, 15))

def process_masquerading():
    """模拟恶意进程 (修改进程名)"""
    # 注意：在 Python 中直接修改进程名比较复杂，通常需要 setproctitle 库
    # 这里我们用一种更简单的方法：创建一个名为 xmrig 的子进程（实际上是 sleep）
    
    # 创建一个名为 xmrig 的脚本
    with open("xmrig", "w") as f:
        f.write("#!/bin/bash\nwhile true; do sleep 1; done")
    os.chmod("xmrig", 0o755)
    
    # 运行它
    os.system("./xmrig &")

def network_connection_simulation():
    """模拟异常网络连接"""
    # 尝试连接一些随机 IP (不会真的连通，但会产生 SYN_SENT 状态，或者如果连通会有 ESTABLISHED)
    # 为了安全，我们只监听本地端口，模拟被连接
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9999))
    server.listen(5)
    
    while True:
        time.sleep(10)

if __name__ == "__main__":
    print("Starting Security Simulation Container...")
    
    # 1. 启动恶意进程模拟
    process_masquerading()
    
    # 2. 启动日志注入模拟 (线程)
    t1 = threading.Thread(target=log_injection_simulation, daemon=True)
    t1.start()
    
    # 3. 启动网络模拟
    t2 = threading.Thread(target=network_connection_simulation, daemon=True)
    t2.start()
    
    # 主线程保持运行
    while True:
        time.sleep(1)

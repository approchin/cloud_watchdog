# HTTP Status 处理详解

## `response.raise_for_status()` 是什么？

### 简单解释
这是 Python `requests` 库的一个方法，用于**检查 HTTP 响应状态码，如果是错误状态则抛出异常**。

### 代码示例

```python
import requests

# 调用 API
response = requests.get('https://api.example.com/data')

# 检查状态码
response.raise_for_status()  # 如果状态码是 4xx 或 5xx，抛出异常
```

### HTTP 状态码范围

| 状态码范围 | 含义 | `raise_for_status()` 行为 |
|-----------|------|-------------------------|
| 2xx (200-299) | 成功 | ✅ 不抛异常，继续执行 |
| 3xx (300-399) | 重定向 | ✅ 通常不抛异常 |
| 4xx (400-499) | 客户端错误 | ❌ 抛出 `HTTPError` 异常 |
| 5xx (500-599) | 服务器错误 | ❌ 抛出 `HTTPError` 异常 |

### 常见状态码

```python
200 OK              - 请求成功
201 Created         - 资源已创建
400 Bad Request     - 请求格式错误 ← raise_for_status() 抛异常
401 Unauthorized    - 未授权 ← raise_for_status() 抛异常
403 Forbidden       - 禁止访问 ← raise_for_status() 抛异常
404 Not Found       - 资源不存在 ← raise_for_status() 抛异常
429 Too Many Requests - 请求过多 ← raise_for_status() 抛异常
500 Internal Server Error - 服务器错误 ← raise_for_status() 抛异常
503 Service Unavailable - 服务不可用 ← raise_for_status() 抛异常
```

### 在我们项目中的使用

```python
# test_deepseek_real.py Line 185-195
response = requests.post(url, headers=headers, json=payload, timeout=30)

# 打印错误详情
if response.status_code != 200:
    print(f"   ❌ API 错误 {response.status_code}:")
    print(f"   {response.text}")

response.raise_for_status()  # 如果不是 2xx，抛出异常并终止程序
```

### 为什么需要它？

#### ❌ 不使用 raise_for_status()
```python
response = requests.get('https://api.example.com/data')
data = response.json()  # ← 如果状态码是 404，这里会静默失败或返回错误数据
print(data)  # 可能打印错误信息而不是数据
```

#### ✅ 使用 raise_for_status()
```python
try:
    response = requests.get('https://api.example.com/data')
    response.raise_for_status()  # 检查状态码
    data = response.json()  # 只有成功时才执行
    print(data)
except requests.exceptions.HTTPError as e:
    print(f"HTTP 错误: {e}")  # 明确知道出错了
```

### 实际案例

#### DeepSeek API 调用
```python
# 之前的 400 错误
response = requests.post(url, headers=headers, json=payload)
# Status: 400 Bad Request
# response.text: {"error": "Invalid request: response_format not supported"}

response.raise_for_status()  
# ↑ 抛出异常: HTTPError: 400 Client Error: Bad Request for url: ...
```

#### 好处
1. **快速失败**: 立即知道请求失败，而不是继续处理错误数据
2. **明确错误**: 异常信息清楚地说明了问题
3. **防止静默失败**: 避免错误数据污染后续逻辑

### 等价代码

```python
# raise_for_status() 等价于：
if 400 <= response.status_code < 600:
    raise requests.exceptions.HTTPError(
        f"{response.status_code} Error: {response.reason}"
    )
```

### 最佳实践

```python
import requests

try:
    response = requests.post(api_url, json=data, timeout=10)
    
    # 方式1: 简洁写法
    response.raise_for_status()
    result = response.json()
    
except requests.exceptions.HTTPError as e:
    # 处理 HTTP 错误 (4xx, 5xx)
    print(f"HTTP 错误: {e}")
    print(f"响应内容: {e.response.text}")
    
except requests.exceptions.Timeout:
    # 处理超时
    print("请求超时")
    
except requests.exceptions.RequestException as e:
    # 处理其他网络错误
    print(f"网络错误: {e}")
```

---

## 总结

| 方法 | 用途 | 何时使用 |
|-----|------|---------|
| `response.raise_for_status()` | 检查并抛出 HTTP 错误 | **总是使用**（除非你想自己处理错误状态） |
| `response.status_code` | 获取状态码 | 需要根据不同状态码执行不同逻辑 |
| `response.json()` | 解析 JSON | 确认状态码正确后 |
| `response.text` | 获取原始文本 | 调试或处理非 JSON 响应 |

**记住**: `raise_for_status()` 是 requests 库的安全护栏，防止你在不知道请求失败的情况下继续处理数据。

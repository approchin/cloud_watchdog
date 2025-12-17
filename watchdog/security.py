"""
安全检查模块
"""
from typing import Dict, Any, List
import os
import yaml
from .utils import run_command

def _load_security_rules() -> Dict[str, Any]:
    """加载安全规则配置"""
    # 使用相对于模块的路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rule_file = os.path.join(base_dir, "config", "security_rules.yml")
    if not os.path.exists(rule_file):
        return {}
        
    try:
        with open(rule_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def check_logs_for_injection(logs: str) -> List[str]:
    """
    检查日志中是否存在注入攻击特征 (基于知识库)
    """
    rules = _load_security_rules()
    
    suspicious_patterns = []
    
    # 从配置加载模式，如果失败则使用默认值
    log_patterns = rules.get("log_patterns", {})
    if not log_patterns:
        # 默认兜底规则
        suspicious_patterns = [
            "UNION SELECT", "syntax error", "ORA-", "MySQL Error",
            "/etc/passwd", "cat /flag", "whoami",
            "<script>", "alert(1)"
        ]
    else:
        # 展平所有分类的模式
        for category, patterns in log_patterns.items():
            suspicious_patterns.extend(patterns)
    
    found_patterns = []
    for pattern in suspicious_patterns:
        if pattern in logs:
            found_patterns.append(pattern)
            
    return found_patterns

def check_processes(container_name: str) -> List[str]:
    """
    检查容器内是否存在恶意进程 (基于知识库)
    """
    code, stdout, stderr = run_command([
        'docker', 'top', container_name
    ])
    
    malicious_processes = []
    if code == 0:
        rules = _load_security_rules()
        blacklist = rules.get("process_blacklist", [])
        
        # 默认兜底
        if not blacklist:
            blacklist = ["xmrig", "minerd", "nmap", "sqlmap", "hydra", "nc -e", "bash -i"]
        
        for line in stdout.split('\n'):
            for bad_proc in blacklist:
                if bad_proc in line:
                    malicious_processes.append(bad_proc)
                    
    return malicious_processes

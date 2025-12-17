"""
配置加载模块
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class CircuitBreakerConfig:
    max_restart_attempts: int = 3
    window_seconds: int = 300
    cooldown_seconds: int = 1800  # 熔断后冷却时间，期间持续监控并上报
    on_exceed: str = "stop_and_notify"
    state_file: str = "/opt/watchdog/state/breaker_state.json"


@dataclass
class LLMConfig:
    """LLM 配置（用于 LangGraph Agent）"""
    provider: str = "deepseek"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    temperature: float = 0
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass
class DifyConfig:
    """[已弃用] Dify 配置 - 保留以便向后兼容"""
    webhook_url: str = ""
    api_key: str = ""
    timeout_seconds: int = 30


@dataclass
class EmailConfig:
    enabled: bool = True
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 465
    use_ssl: bool = True
    sender: str = ""
    password: str = ""
    recipients: List[str] = field(default_factory=list)


@dataclass
class ExecutorConfig:
    host: str = "127.0.0.1"
    port: int = 9999
    allowed_actions: List[str] = field(default_factory=lambda: ["RESTART", "STOP", "INSPECT"])

@dataclass
class SystemConfig:
    check_interval_seconds: int = 30
    resource_check_interval_seconds: int = 120
    evidence_log_lines: int = 50
    log_level: str = "INFO"
    log_file: str = "/opt/watchdog/logs/watchdog.log"


@dataclass 
class ThresholdConfig:
    cpu_warning: int = 70
    cpu_critical: int = 90
    memory_warning: int = 70
    memory_critical: int = 85


@dataclass
class ContainerConfig:
    name: str
    enabled: bool = True  # 是否启用对该容器的监控
    description: str = ""
    health_check: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, int] = field(default_factory=dict)
    policy: Dict[str, Any] = field(default_factory=dict)


class Config:
    """全局配置类"""
    
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # 默认配置目录
            config_dir = Path(__file__).parent.parent / "config"
        
        self.config_dir = Path(config_dir)
        self.system = SystemConfig()
        self.circuit_breaker = CircuitBreakerConfig()
        self.llm = LLMConfig()
        self.dify = DifyConfig()  # 保留以便向后兼容
        self.email = EmailConfig()
        self.executor = ExecutorConfig()
        self.thresholds = ThresholdConfig()
        self.containers: List[ContainerConfig] = []
        
        self._load_config()
        self._load_watchlist()
    
    def _load_config(self):
        """加载主配置文件"""
        config_file = self.config_dir / "config.yml"
        if not config_file.exists():
            print(f"警告: 配置文件不存在 {config_file}")
            return
        
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        
        # 系统配置
        sys_cfg = data.get('system', {})
        self.system.check_interval_seconds = sys_cfg.get('check_interval_seconds', 30)
        self.system.resource_check_interval_seconds = sys_cfg.get('resource_check_interval_seconds', 120)
        self.system.evidence_log_lines = sys_cfg.get('evidence_log_lines', 50)
        self.system.log_level = sys_cfg.get('log_level', 'INFO')
        self.system.log_file = sys_cfg.get('log_file', '/opt/watchdog/logs/watchdog.log')
        
        # 熔断配置
        cb_cfg = data.get('circuit_breaker', {})
        self.circuit_breaker.max_restart_attempts = cb_cfg.get('max_restart_attempts', 3)
        self.circuit_breaker.window_seconds = cb_cfg.get('window_seconds', 300)
        self.circuit_breaker.cooldown_seconds = cb_cfg.get('cooldown_seconds', 1800)
        self.circuit_breaker.on_exceed = cb_cfg.get('on_exceed', 'stop_and_notify')
        self.circuit_breaker.state_file = cb_cfg.get('state_file', '/opt/watchdog/state/breaker_state.json')
        
        # LLM 配置
        llm_cfg = data.get('llm', {})
        self.llm.provider = llm_cfg.get('provider', 'deepseek')
        self.llm.api_key = self._resolve_env(llm_cfg.get('api_key', ''))
        self.llm.base_url = llm_cfg.get('base_url', 'https://api.deepseek.com')
        self.llm.model = llm_cfg.get('model', 'deepseek-chat')
        self.llm.temperature = llm_cfg.get('temperature', 0)
        self.llm.timeout_seconds = llm_cfg.get('timeout_seconds', 30)
        self.llm.max_retries = llm_cfg.get('max_retries', 3)
        
        # Dify 配置（保留以便向后兼容）
        dify_cfg = data.get('dify', {})
        self.dify.webhook_url = self._resolve_env(dify_cfg.get('webhook_url', ''))
        self.dify.api_key = self._resolve_env(dify_cfg.get('api_key', ''))
        self.dify.timeout_seconds = dify_cfg.get('timeout_seconds', 30)
        
        # 邮件配置
        notif_cfg = data.get('notification', {})
        email_cfg = notif_cfg.get('email', {})
        self.email.enabled = email_cfg.get('enabled', True)
        self.email.smtp_server = email_cfg.get('smtp_server', 'smtp.qq.com')
        self.email.smtp_port = email_cfg.get('smtp_port', 465)
        self.email.use_ssl = email_cfg.get('use_ssl', True)
        self.email.sender = email_cfg.get('sender', '')
        # 注: _resolve_env 暂不使用
        self.email.password = email_cfg.get('password', '')
        self.email.recipients = email_cfg.get('recipients', [])
        
        # 执行器配置
        exec_cfg = data.get('executor', {})
        self.executor.host = exec_cfg.get('host', '127.0.0.1')
        self.executor.port = exec_cfg.get('port', 9999)
        self.executor.allowed_actions = exec_cfg.get('allowed_actions', ['RESTART', 'STOP', 'INSPECT'])
        
        # 全局阈值配置
        thresh_cfg = data.get('thresholds', {})
        self.thresholds.cpu_warning = thresh_cfg.get('cpu_warning', 70)
        self.thresholds.cpu_critical = thresh_cfg.get('cpu_critical', 90)
        self.thresholds.memory_warning = thresh_cfg.get('memory_warning', 70)
        self.thresholds.memory_critical = thresh_cfg.get('memory_critical', 85)
    
    def _load_watchlist(self):
        """加载监控容器列表"""
        watchlist_file = self.config_dir / "watchlist.yml"
        if not watchlist_file.exists():
            print(f"警告: 监控列表不存在 {watchlist_file}")
            return
        
        with open(watchlist_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        
        for container in data.get('containers', []):
            # 过滤未启用的容器
            if not container.get('enabled', True):
                continue
            self.containers.append(ContainerConfig(
                name=container.get('name', ''),
                enabled=container.get('enabled', True),
                description=container.get('description', ''),
                health_check=container.get('health_check', {}),
                thresholds=container.get('thresholds', {}),
                policy=container.get('policy', {})
            ))
    
    def _resolve_env(self, value: str) -> str:
        """解析环境变量 ${VAR_NAME}"""
        if not value or not isinstance(value, str):
            return value
        
        if value.startswith('${') and value.endswith('}'):
            env_name = value[2:-1]
            return os.environ.get(env_name, '')
        
        return value
    
    def get_container(self, name: str) -> ContainerConfig:
        """获取容器配置"""
        for container in self.containers:
            if container.name == name:
                return container
        return None


# 全局配置实例
_config: Config = None


def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(config_dir: str = None):
    """初始化配置"""
    global _config
    _config = Config(config_dir)
    return _config

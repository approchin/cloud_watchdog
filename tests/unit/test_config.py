#!/usr/bin/env python3
"""
单元1: 配置模块测试 (LLMConfig 加载)

测试内容：
- 配置文件加载
- LLMConfig 解析
- 环境变量解析
- 容器配置加载
"""
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.config import (
    Config, 
    init_config, 
    get_config,
    LLMConfig,
    EmailConfig,
    ThresholdConfig,
    ContainerConfig
)


class TestLLMConfig:
    """LLMConfig 加载测试"""
    
    def test_llm_config_defaults(self):
        """测试 LLMConfig 默认值"""
        llm = LLMConfig()
        assert llm.provider == "deepseek"
        assert llm.model == "deepseek-chat"
        assert llm.temperature == 0
        assert llm.timeout_seconds == 30
        assert llm.max_retries == 3
        assert llm.base_url == "https://api.deepseek.com"
    
    def test_llm_config_from_yaml(self):
        """测试从 YAML 加载 LLMConfig"""
        config = init_config()
        assert config.llm.provider == "deepseek"
        assert config.llm.model == "deepseek-chat"
        assert config.llm.base_url == "https://api.deepseek.com"


class TestEnvVariableResolution:
    """环境变量解析测试"""
    
    def test_resolve_env_with_value(self):
        """测试环境变量解析 - 有值"""
        os.environ['TEST_API_KEY'] = 'test-key-123'
        config = Config()
        result = config._resolve_env('${TEST_API_KEY}')
        assert result == 'test-key-123'
        del os.environ['TEST_API_KEY']
    
    def test_resolve_env_without_value(self):
        """测试环境变量解析 - 无值"""
        os.environ.pop('NONEXISTENT_KEY', None)
        config = Config()
        result = config._resolve_env('${NONEXISTENT_KEY}')
        assert result == ''
    
    def test_resolve_env_plain_string(self):
        """测试环境变量解析 - 普通字符串"""
        config = Config()
        result = config._resolve_env('plain-string')
        assert result == 'plain-string'
    
    def test_deepseek_api_key_from_env(self):
        """测试 DEEPSEEK_API_KEY 从环境变量加载"""
        # 验证 _resolve_env 正确处理 ${VAR} 格式
        config = Config()
        
        # 设置测试环境变量
        os.environ['TEST_LLM_KEY'] = 'sk-test-key-12345'
        result = config._resolve_env('${TEST_LLM_KEY}')
        assert result == 'sk-test-key-12345'
        
        # 清理
        del os.environ['TEST_LLM_KEY']


class TestContainerConfig:
    """容器配置测试"""
    
    def test_container_list_loaded(self):
        """测试容器列表加载"""
        config = init_config()
        assert len(config.containers) > 0
    
    def test_container_names(self):
        """测试容器名称"""
        config = init_config()
        names = [c.name for c in config.containers]
        expected = ['normal-app', 'cpu-stress', 'memory-leak', 'crash-loop', 'unhealthy-app']
        for name in expected:
            assert name in names, f"缺少容器配置: {name}"
    
    def test_get_container(self):
        """测试获取单个容器配置"""
        config = init_config()
        container = config.get_container('cpu-stress')
        assert container is not None
        assert container.name == 'cpu-stress'
        assert container.enabled == True
    
    def test_get_nonexistent_container(self):
        """测试获取不存在的容器"""
        config = init_config()
        container = config.get_container('nonexistent-container')
        assert container is None
    
    def test_container_thresholds(self):
        """测试容器阈值配置"""
        config = init_config()
        container = config.get_container('cpu-stress')
        assert container.thresholds is not None
        assert 'cpu_percent_critical' in container.thresholds


class TestThresholdConfig:
    """全局阈值配置测试"""
    
    def test_threshold_defaults(self):
        """测试阈值默认值"""
        thresh = ThresholdConfig()
        assert thresh.cpu_warning == 70
        assert thresh.cpu_critical == 90
        assert thresh.memory_warning == 70
        assert thresh.memory_critical == 85
    
    def test_threshold_from_yaml(self):
        """测试从 YAML 加载阈值"""
        config = init_config()
        assert config.thresholds.cpu_warning == 70
        assert config.thresholds.cpu_critical == 90


class TestEmailConfig:
    """邮件配置测试"""
    
    def test_email_config_loaded(self):
        """测试邮件配置加载"""
        config = init_config()
        assert config.email.enabled == True
        assert config.email.smtp_server == "smtp.qq.com"
        assert config.email.smtp_port == 465


class TestConfigSingleton:
    """配置单例测试"""
    
    def test_get_config_returns_same_instance(self):
        """测试 get_config 返回相同实例"""
        init_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
    
    def test_init_config_creates_new_instance(self):
        """测试 init_config 创建新实例"""
        config1 = init_config()
        config2 = init_config()
        # init_config 会创建新实例并替换全局实例
        assert get_config() is config2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

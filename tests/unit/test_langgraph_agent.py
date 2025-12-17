#!/usr/bin/env python3
"""
LangGraph Agent 单元测试

验证真正的 LangGraph 实现：
- StateGraph 构建
- 节点函数
- 条件路由
- 完整工作流
"""
import os
import sys
import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.config import init_config


class TestLangGraphImports:
    """验证 LangGraph 正确导入"""
    
    def test_langgraph_imported(self):
        """验证导入了 langgraph"""
        import watchdog.agent as agent_module
        import inspect
        source = inspect.getsource(agent_module)
        assert 'from langgraph' in source, "未导入 langgraph"
    
    def test_stategraph_used(self):
        """验证使用了 StateGraph"""
        import watchdog.agent as agent_module
        import inspect
        source = inspect.getsource(agent_module)
        assert 'StateGraph' in source, "未使用 StateGraph"
    
    def test_conditional_edges_used(self):
        """验证使用了条件边"""
        import watchdog.agent as agent_module
        import inspect
        source = inspect.getsource(agent_module)
        assert 'add_conditional_edges' in source, "未使用条件边路由"


class TestGraphConstruction:
    """Graph 构建测试"""
    
    def setup_method(self):
        init_config()
    
    def test_build_graph(self):
        """测试构建 Graph"""
        from watchdog.agent import build_diagnosis_graph
        graph = build_diagnosis_graph()
        assert graph is not None
        assert 'CompiledStateGraph' in type(graph).__name__
    
    def test_graph_singleton(self):
        """测试 Graph 单例"""
        from watchdog.agent import get_diagnosis_graph
        graph1 = get_diagnosis_graph()
        graph2 = get_diagnosis_graph()
        assert graph1 is graph2


class TestNodeFunctions:
    """节点函数测试"""
    
    def setup_method(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
        init_config()
    
    @patch('watchdog.agent.get_config')
    def test_analyze_evidence_without_api_key(self, mock_get_config):
        """测试无 API Key 时的 analyze_evidence"""
        from watchdog.agent import analyze_evidence, DiagnosisState
        
        # 模拟配置返回空的 API Key
        mock_config = MagicMock()
        mock_config.llm.api_key = ""
        mock_config.llm.model = "deepseek-chat"
        mock_config.llm.base_url = "https://api.deepseek.com"
        mock_config.llm.temperature = 0
        mock_config.llm.timeout_seconds = 30
        mock_config.llm.max_retries = 3
        mock_get_config.return_value = mock_config
        
        state: DiagnosisState = {
            "evidence": {"container": {"name": "test"}},
            "container_name": "test",
            "fault_type": "CPU_HIGH",
            "decision": {},
            "command": "",
            "reason": "",
            "action_result": None,
            "notification_result": None,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
        
        result = analyze_evidence(state)
        
        # 无 API Key 时应该返回安全的默认命令和错误信息
        assert result["command"] == "ALERT_ONLY"
        assert result["error"] is not None
        assert "API Key" in result["error"] or "DEEPSEEK" in result["error"]
    
    def test_no_action_node(self):
        """测试 no_action 节点"""
        from watchdog.agent import no_action_node, DiagnosisState
        
        state: DiagnosisState = {
            "evidence": {},
            "container_name": "healthy-container",
            "fault_type": "UNKNOWN",
            "decision": {},
            "command": "NONE",
            "reason": "容器正常",
            "action_result": None,
            "notification_result": None,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
        
        result = no_action_node(state)
        
        # no_action 应该原样返回 state
        assert result["container_name"] == "healthy-container"
    
    def test_error_handler_node(self):
        """测试 error_handler 节点"""
        from watchdog.agent import error_handler_node, DiagnosisState
        
        state: DiagnosisState = {
            "evidence": {},
            "container_name": "error-container",
            "fault_type": "UNKNOWN",
            "decision": {},
            "command": "",
            "reason": "",
            "action_result": None,
            "notification_result": None,
            "timestamp": datetime.now().isoformat(),
            "error": "Test error"
        }
        
        result = error_handler_node(state)
        
        assert result["error"] == "Test error"


class TestConditionalRouting:
    """条件路由测试"""
    
    def setup_method(self):
        init_config()
    
    def test_route_restart(self):
        """测试 RESTART 路由"""
        from watchdog.agent import route_by_command
        
        state = {"command": "RESTART", "error": None}
        assert route_by_command(state) == "execute_action"
    
    def test_route_stop(self):
        """测试 STOP 路由"""
        from watchdog.agent import route_by_command
        
        state = {"command": "STOP", "error": None}
        assert route_by_command(state) == "execute_action"
    
    def test_route_alert_only(self):
        """测试 ALERT_ONLY 路由"""
        from watchdog.agent import route_by_command
        
        state = {"command": "ALERT_ONLY", "error": None}
        assert route_by_command(state) == "send_alert"
    
    def test_route_none(self):
        """测试 NONE 路由"""
        from watchdog.agent import route_by_command
        
        state = {"command": "NONE", "error": None}
        assert route_by_command(state) == "no_action"
    
    def test_route_error(self):
        """测试错误路由"""
        from watchdog.agent import route_by_command
        
        state = {"command": "ALERT_ONLY", "error": "Some error"}
        assert route_by_command(state) == "error_handler"
    
    def test_route_error_with_restart(self):
        """测试有错误但命令是 RESTART 时仍执行"""
        from watchdog.agent import route_by_command
        
        state = {"command": "RESTART", "error": "Some error"}
        # 即使有错误，RESTART/STOP 命令仍然执行
        assert route_by_command(state) == "execute_action"


class TestDiagnosisAgent:
    """DiagnosisAgent 测试"""
    
    def setup_method(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
        init_config()
    
    def test_agent_initialization(self):
        """测试 Agent 初始化"""
        from watchdog.agent import DiagnosisAgent
        
        agent = DiagnosisAgent()
        assert agent.graph is not None
        assert agent.config is not None
    
    def test_diagnose_returns_result(self):
        """测试 diagnose 返回结果结构"""
        from watchdog.agent import DiagnosisAgent
        
        agent = DiagnosisAgent()
        evidence = {
            "container": {"name": "test-container"},
            "evidence": {"cpu_percent": "50%"},
            "fault_type": "CPU_HIGH"
        }
        
        result = agent.diagnose(evidence)
        
        assert "decision" in result
        assert "command" in result
        assert "reason" in result
        assert "timestamp" in result


class TestMockedLLMCall:
    """模拟 LLM 调用测试"""
    
    def setup_method(self):
        os.environ['DEEPSEEK_API_KEY'] = 'sk-test-key'
        init_config()
    
    def teardown_method(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
    
    @patch('watchdog.agent.ChatOpenAI')
    def test_successful_graph_execution(self, mock_chat):
        """测试成功的 Graph 执行"""
        from watchdog.agent import DiagnosisAgent
        
        # 模拟 LLM 响应
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "fault_type": "CPU_HIGH",
            "command": "ALERT_ONLY",
            "params": {
                "container_name": "test-container",
                "current_cpu": "85%",
                "current_memory": "50%"
            },
            "reason": "CPU 使用率较高，建议观察"
        })
        mock_chat.return_value.invoke.return_value = mock_response
        
        agent = DiagnosisAgent()
        evidence = {
            "container": {"name": "test-container"},
            "evidence": {"cpu_percent": "85%"},
            "fault_type": "CPU_HIGH"
        }
        
        result = agent.diagnose(evidence)
        
        assert result["command"] == "ALERT_ONLY"
        assert "CPU" in result["reason"]
    
    @patch('watchdog.agent.ChatOpenAI')
    @patch('watchdog.agent.execute_action')
    @patch('watchdog.agent.send_notification')
    def test_restart_flow(self, mock_notify, mock_execute, mock_chat):
        """测试 RESTART 完整流程"""
        from watchdog.agent import DiagnosisAgent
        
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "fault_type": "PROCESS_CRASH",
            "command": "RESTART",
            "params": {"container_name": "crash-container"},
            "reason": "容器崩溃，需要重启"
        })
        mock_chat.return_value.invoke.return_value = mock_response
        mock_execute.return_value = {"success": True}
        mock_notify.return_value = {"success": True}
        
        agent = DiagnosisAgent()
        evidence = {
            "container": {"name": "crash-container"},
            "evidence": {"exit_code": 1},
            "fault_type": "PROCESS_CRASH"
        }
        
        result = agent.diagnose(evidence)
        
        assert result["command"] == "RESTART"
        mock_execute.assert_called_once()


class TestRunDiagnosis:
    """run_diagnosis 便捷函数测试"""
    
    def setup_method(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
        init_config()
    
    def test_sync_mode(self):
        """测试同步模式"""
        from watchdog.agent import run_diagnosis
        
        evidence = {"container": {"name": "test"}}
        result = run_diagnosis(evidence, async_mode=False)
        
        assert result is not None
        # 结果结构可能是直接的 dict 或包含在 result 字段中
        if "result" in result:
            assert "command" in result["result"]
        else:
            assert "command" in result
    
    @patch('watchdog.agent.get_task_queue')
    def test_async_mode(self, mock_get_queue):
        """测试异步模式"""
        from watchdog.agent import run_diagnosis
        
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue
        
        evidence = {"container": {"name": "test"}}
        result = run_diagnosis(evidence, async_mode=True)
        
        # 异步模式现在返回提交状态
        assert result is not None
        assert result.get("status") == "submitted"
        mock_queue.submit.assert_called_once()


class TestBackwardCompatibility:
    """向后兼容测试"""
    
    def setup_method(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
        init_config()
    
    def test_analyze_with_llm_exists(self):
        """测试 analyze_with_llm 兼容函数存在"""
        from watchdog.agent import analyze_with_llm
        assert callable(analyze_with_llm)
    
    def test_analyze_with_llm_returns_dict(self):
        """测试 analyze_with_llm 返回字典"""
        from watchdog.agent import analyze_with_llm
        
        evidence = {"container": {"name": "test"}}
        result = analyze_with_llm(evidence)
        
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

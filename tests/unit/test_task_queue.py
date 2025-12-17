#!/usr/bin/env python3
"""
单元5: 任务队列测试 (DiagnosisTaskQueue)

测试内容：
- 队列初始化
- 任务提交
- 工作线程启动/停止
- 回调执行
"""
import os
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from queue import Empty

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from watchdog.agent import DiagnosisTaskQueue, get_task_queue
from watchdog.config import init_config


class TestTaskQueueInit:
    """任务队列初始化测试"""
    
    def test_queue_initialization(self):
        """测试队列初始化"""
        queue = DiagnosisTaskQueue(max_workers=1)
        assert queue.max_workers == 1
        assert queue.running == False
        assert queue.queue.empty()
    
    def test_queue_multiple_workers(self):
        """测试多工作线程配置"""
        queue = DiagnosisTaskQueue(max_workers=3)
        assert queue.max_workers == 3


class TestTaskQueueLifecycle:
    """任务队列生命周期测试"""
    
    def test_start_queue(self):
        """测试启动队列"""
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        
        assert queue.running == True
        assert len(queue.workers) == 1
        
        queue.stop()
    
    def test_stop_queue(self):
        """测试停止队列"""
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        queue.stop()
        
        assert queue.running == False
    
    def test_double_start(self):
        """测试重复启动"""
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        queue.start()  # 第二次启动应该被忽略
        
        assert len(queue.workers) == 1
        
        queue.stop()


class TestTaskSubmission:
    """任务提交测试"""
    
    def setup_method(self):
        init_config()
    
    def test_submit_task(self):
        """测试提交任务"""
        queue = DiagnosisTaskQueue(max_workers=1)
        
        evidence = {"container": {"name": "test"}}
        queue.submit(evidence)
        
        assert queue.queue.qsize() == 1
    
    def test_submit_with_callback(self):
        """测试带回调的任务提交"""
        queue = DiagnosisTaskQueue(max_workers=1)
        callback = MagicMock()
        
        evidence = {"container": {"name": "test"}}
        queue.submit(evidence, callback=callback)
        
        task = queue.queue.get_nowait()
        assert task['evidence'] == evidence
        assert task['callback'] == callback
    
    def test_submit_records_timestamp(self):
        """测试任务提交记录时间戳"""
        queue = DiagnosisTaskQueue(max_workers=1)
        
        evidence = {"container": {"name": "test"}}
        queue.submit(evidence)
        
        task = queue.queue.get_nowait()
        assert 'submitted_at' in task


class TestTaskProcessing:
    """任务处理测试"""
    
    def setup_method(self):
        os.environ['DEEPSEEK_API_KEY'] = 'sk-test-key'
        init_config()
    
    def teardown_method(self):
        os.environ.pop('DEEPSEEK_API_KEY', None)
    
    @patch('watchdog.agent.DiagnosisAgent.diagnose')
    def test_task_execution(self, mock_diagnose):
        """测试任务执行"""
        mock_diagnose.return_value = {"decision": {"command": "NONE"}}
        
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        
        evidence = {"container": {"name": "test"}}
        queue.submit(evidence)
        
        # 等待任务处理
        time.sleep(0.5)
        
        mock_diagnose.assert_called_once()
        
        queue.stop()
    
    @patch('watchdog.agent.DiagnosisAgent.diagnose')
    def test_callback_execution(self, mock_diagnose):
        """测试回调执行"""
        mock_diagnose.return_value = {"decision": {"command": "NONE"}}
        callback = MagicMock()
        
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        
        evidence = {"container": {"name": "test"}}
        queue.submit(evidence, callback=callback)
        
        # 等待任务处理
        time.sleep(0.5)
        
        callback.assert_called_once()
        
        queue.stop()
    
    @patch('watchdog.agent.DiagnosisAgent.diagnose')
    def test_multiple_tasks(self, mock_diagnose):
        """测试多任务处理"""
        mock_diagnose.return_value = {"decision": {"command": "NONE"}}
        
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        
        for i in range(3):
            evidence = {"container": {"name": f"test-{i}"}}
            queue.submit(evidence)
        
        # 等待所有任务处理
        time.sleep(1.5)
        
        assert mock_diagnose.call_count == 3
        
        queue.stop()


class TestGlobalTaskQueue:
    """全局任务队列测试"""
    
    def test_get_task_queue_singleton(self):
        """测试全局队列单例"""
        queue1 = get_task_queue()
        queue2 = get_task_queue()
        
        assert queue1 is queue2
    
    def test_get_task_queue_auto_starts(self):
        """测试全局队列自动启动"""
        # 重置全局队列
        import watchdog.agent as agent_module
        agent_module._task_queue = None
        
        queue = get_task_queue()
        
        assert queue.running == True


class TestErrorHandling:
    """错误处理测试"""
    
    def setup_method(self):
        init_config()
    
    @patch('watchdog.agent.DiagnosisAgent.diagnose')
    def test_task_exception_handling(self, mock_diagnose):
        """测试任务异常处理"""
        mock_diagnose.side_effect = Exception("诊断失败")
        
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        
        evidence = {"container": {"name": "test"}}
        queue.submit(evidence)
        
        # 等待任务处理
        time.sleep(0.5)
        
        # 队列应该继续运行，不会因为异常而崩溃
        assert queue.running == True
        
        queue.stop()
    
    def test_queue_empty_timeout(self):
        """测试队列空时的超时处理"""
        queue = DiagnosisTaskQueue(max_workers=1)
        queue.start()
        
        # 等待一个超时周期
        time.sleep(1.5)
        
        # 队列应该继续运行
        assert queue.running == True
        
        queue.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

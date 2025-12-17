#!/usr/bin/env python3
"""
单元测试运行脚本

使用方式：
    # 运行所有单元测试
    python tests/unit/run_tests.py
    
    # 运行指定模块
    python tests/unit/run_tests.py --module config
    
    # 详细输出
    python tests/unit/run_tests.py -v
    
    # 生成覆盖率报告
    python tests/unit/run_tests.py --coverage
"""
import sys
import argparse
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    parser = argparse.ArgumentParser(description='运行单元测试')
    parser.add_argument('--module', '-m', type=str, 
                        choices=['config', 'prompt', 'llm', 'agent', 'queue', 'monitor', 'all'],
                        default='all', help='要测试的模块')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--coverage', '-c', action='store_true', help='生成覆盖率报告')
    parser.add_argument('--fast', '-f', action='store_true', help='快速模式（跳过慢测试）')
    
    args = parser.parse_args()
    
    import pytest
    
    test_dir = Path(__file__).parent
    pytest_args = [str(test_dir)]
    
    # 模块映射
    module_map = {
        'config': 'test_config.py',
        'prompt': 'test_agent_prompt.py',
        'llm': 'test_llm_call.py',
        'agent': 'test_diagnosis_agent.py',
        'queue': 'test_task_queue.py',
        'monitor': 'test_monitor_integration.py',
    }
    
    if args.module != 'all':
        pytest_args = [str(test_dir / module_map[args.module])]
    
    if args.verbose:
        pytest_args.append('-v')
    
    if args.fast:
        pytest_args.extend(['-m', 'not slow'])
    
    if args.coverage:
        pytest_args.extend(['--cov=watchdog', '--cov-report=term-missing'])
    
    # 添加输出格式
    pytest_args.extend([
        '--tb=short',
        '-q' if not args.verbose else '',
    ])
    
    print("=" * 60)
    print("Cloud Watchdog 单元测试")
    print("=" * 60)
    print(f"测试模块: {args.module}")
    print(f"测试路径: {pytest_args[0]}")
    print("=" * 60)
    
    exit_code = pytest.main([arg for arg in pytest_args if arg])
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

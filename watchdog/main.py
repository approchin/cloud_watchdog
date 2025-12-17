"""
Cloud Watchdog - 主入口
同时启动监控服务和 API 服务
"""
import sys
import signal
import logging
import argparse
from pathlib import Path

import uvicorn

from .config import init_config, get_config
from .monitor import ContainerMonitor
from .api import create_app
from .executor import check_docker_permission


def setup_logging(log_level: str = "INFO", log_file: str = None):
    """配置日志"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description='Cloud Watchdog - 容器故障自动诊断与修复系统')
    parser.add_argument('--config-dir', type=str, help='配置文件目录')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='API 服务监听地址')
    parser.add_argument('--port', type=int, default=9999, help='API 服务监听端口')
    parser.add_argument('--log-level', type=str, default='INFO', help='日志级别')
    parser.add_argument('--api-only', action='store_true', help='仅启动 API 服务')
    parser.add_argument('--monitor-only', action='store_true', help='仅启动监控')
    
    args = parser.parse_args()
    
    config = init_config(args.config_dir)
    
    setup_logging(
        log_level=args.log_level or config.system.log_level,
        log_file=config.system.log_file if not sys.platform.startswith('win') else None
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Cloud Watchdog 启动中...")
    logger.info("=" * 50)
    
    if not check_docker_permission():
        logger.error("无法连接 Docker，请检查权限")
        sys.exit(1)
    
    logger.info("Docker 连接正常")
    logger.info(f"监控容器数量: {len(config.containers)}")
    for container in config.containers:
        logger.info(f"  - {container.name}")
    logger.info(f"API 服务: http://{args.host}:{args.port}")
    
    monitor = None
    if not args.api_only:
        monitor = ContainerMonitor()
    
    def signal_handler(signum, frame):
        logger.info("收到退出信号，正在关闭...")
        if monitor:
            monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if monitor:
        monitor.start()
    
    if not args.monitor_only:
        app = create_app()
        config.executor.host = args.host
        config.executor.port = args.port
        
        logger.info(f"API 服务启动: http://{args.host}:{args.port}")
        
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower()
        )
    else:
        logger.info("仅监控模式，按 Ctrl+C 退出")
        try:
            while True:
                signal.pause()
        except AttributeError:
            import time
            while True:
                time.sleep(1)


if __name__ == "__main__":
    main()

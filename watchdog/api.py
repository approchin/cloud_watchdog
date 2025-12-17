"""
FastAPI 接口模块 - 提供 /action 和 /notify 接口供 Dify 调用
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from .executor import execute_action
from .notifier import send_notification

app = FastAPI(
    title="Cloud Watchdog API",
    description="容器故障诊断与修复系统 - 执行接口",
    version="1.0.0"
)

logger = logging.getLogger(__name__)


class ActionRequest(BaseModel):
    """执行命令请求"""
    command: str
    container_name: str


class ActionResponse(BaseModel):
    """执行命令响应"""
    success: bool
    action: str
    container: str
    message: Optional[str] = None
    error: Optional[str] = None
    verification: Optional[Dict[str, Any]] = None
    # RESTART 重试相关字段
    is_recovered: Optional[bool] = None
    total_attempts: Optional[int] = None
    attempts: Optional[list] = None
    final_action: Optional[str] = None
    reason: Optional[str] = None
    timestamp: str


class NotifyRequest(BaseModel):
    """通知请求"""
    type: str
    container_name: str
    fault_type: Optional[str] = None
    current_cpu: Optional[str] = None
    current_memory: Optional[str] = None
    reason: Optional[str] = None
    command: Optional[str] = None
    action_response: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class NotifyResponse(BaseModel):
    """通知响应"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


@app.get("/")
def root():
    """健康检查"""
    return {"status": "ok", "service": "Cloud Watchdog API"}


@app.get("/health")
def health_check():
    """健康检查接口"""
    return {"status": "healthy"}


@app.post("/action", response_model=ActionResponse)
def action_endpoint(request: ActionRequest):
    """执行容器操作"""
    logger.info(f"收到执行请求: {request.command} -> {request.container_name}")
    
    # 白名单检查由 executor.execute_action() 处理
    result = execute_action(request.command, request.container_name)
    
    logger.info(f"执行结果: {result.get('success')}")
    
    return ActionResponse(
        success=result.get("success", False),
        action=result.get("action", request.command),
        container=result.get("container", request.container_name),
        message=result.get("stdout", ""),
        error=result.get("error") or result.get("stderr"),
        verification=result.get("verification"),
        is_recovered=result.get("is_recovered"),
        total_attempts=result.get("total_attempts"),
        attempts=result.get("attempts"),
        final_action=result.get("final_action"),
        reason=result.get("reason"),
        timestamp=result.get("timestamp", "")
    )


@app.post("/notify", response_model=NotifyResponse)
def notify_endpoint(request: NotifyRequest):
    """发送通知"""
    logger.info(f"收到通知请求: {request.type} -> {request.container_name}")
    
    data = request.model_dump()
    result = send_notification(data)
    
    logger.info(f"通知结果: {result.get('success')}")
    
    return NotifyResponse(
        success=result.get("success", False),
        message=result.get("message"),
        error=result.get("error")
    )


def create_app():
    """创建并返回 FastAPI 应用"""
    return app

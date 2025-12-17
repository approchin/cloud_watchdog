"""
通知模块 - 发送邮件通知
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, List
from .config import get_config


def send_email(subject: str, body: str, recipients: List[str] = None) -> Dict[str, Any]:
    """发送邮件通知"""
    config = get_config()
    
    if not config.email.enabled:
        return {"success": False, "error": "邮件通知未启用"}
    
    if not recipients:
        recipients = config.email.recipients
    
    if not recipients:
        return {"success": False, "error": "未配置收件人"}
    
    try:
        msg = MIMEMultipart()
        msg['From'] = config.email.sender
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        if config.email.use_ssl:
            server = smtplib.SMTP_SSL(config.email.smtp_server, config.email.smtp_port)
        else:
            server = smtplib.SMTP(config.email.smtp_server, config.email.smtp_port)
            server.starttls()
        
        server.login(config.email.sender, config.email.password)
        server.sendmail(config.email.sender, recipients, msg.as_string())
        server.quit()
        
        return {
            "success": True,
            "message": f"邮件已发送至 {', '.join(recipients)}",
            "timestamp": datetime.now().isoformat()
        }
        
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP 认证失败"}
    except smtplib.SMTPException as e:
        return {"success": False, "error": f"SMTP 错误: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_alert_email(data: Dict[str, Any]) -> tuple:
    """格式化告警邮件"""
    notify_type = data.get("type", "alert")
    container_name = data.get("container_name", "unknown")
    fault_type = data.get("fault_type", "")
    reason = data.get("reason", "")
    current_cpu = data.get("current_cpu", "")
    current_memory = data.get("current_memory", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if notify_type == "alert":
        subject = f"⚠️ 容器告警 - {container_name}"
        body = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #f39c12;">⚠️ 容器资源告警</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>容器名称</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{container_name}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>故障类型</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{fault_type}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>当前 CPU</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{current_cpu}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>当前内存</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{current_memory}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>诊断原因</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>告警时间</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td></tr>
            </table>
        </body></html>
        """
    
    elif notify_type == "action_result":
        command = data.get("command", "")
        action_response = data.get("action_response", {})
        success = action_response.get("success", False) if isinstance(action_response, dict) else False
        verification = action_response.get("verification", {}) if isinstance(action_response, dict) else {}
        
        status_color = "#27ae60" if success else "#e74c3c"
        status_text = "✅ 执行成功" if success else "❌ 执行失败"
        
        subject = f"{status_text} - {container_name} {command}"
        body = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: {status_color};">{status_text}</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>容器名称</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{container_name}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>执行命令</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{command}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>故障类型</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{fault_type}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>执行时间</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td></tr>
            </table>
            <h3>验证结果</h3>
            <pre style="background: #f5f5f5; padding: 10px;">{verification}</pre>
        </body></html>
        """
    
    elif notify_type == "recovery":
        subject = f"✅ 容器正常 - {container_name}"
        message = data.get("message", "容器运行正常")
        body = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #27ae60;">✅ 容器状态正常</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>容器名称</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{container_name}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>状态信息</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{message}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>检查时间</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td></tr>
            </table>
        </body></html>
        """
    
    elif notify_type == "circuit_break":
        subject = f"🔥 熔断告警 - {container_name} 需要人工介入"
        body = f"""
        <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #e74c3c;">🔥 熔断告警 - 需要人工介入</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>容器名称</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{container_name}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>故障类型</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{fault_type}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>诊断原因</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
            </table>
            <div style="background: #fdecea; padding: 15px; margin-top: 20px;">
                <strong>⚠️ 警告：</strong> 该容器已多次重启仍无法恢复，请立即人工介入！
            </div>
        </body></html>
        """
    
    else:
        subject = f"📋 容器通知 - {container_name}"
        body = f"<html><body><pre>{data}</pre></body></html>"
    
    return subject, body


def send_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    """发送通知（统一入口）"""
    subject, body = format_alert_email(data)
    return send_email(subject, body)

"""
LangGraph Agent - 容器故障诊断决策引擎 (真正的 LangGraph 实现)

使用 LangGraph StateGraph 实现容器故障的智能诊断和处理。

工作流架构：
    START 
      ↓
    analyze_evidence (LLM 分析)
      ↓
    route_by_command (条件路由)
      ↓
    ┌─────────────┬──────────────┬─────────────┐
    ↓             ↓              ↓             ↓
execute_action  send_alert   no_action     error_handler
    ↓             ↓              ↓             ↓
    └─────────────┴──────────────┴─────────────┘
                      ↓
                     END
"""
import json
import logging
import os
from typing import Dict, Any, Optional, TypedDict, Literal, Annotated
from datetime import datetime, timedelta
from queue import Queue
from threading import Thread, Lock
import operator

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .config import get_config
from .executor import execute_action
from .notifier import send_notification

logger = logging.getLogger(__name__)



# ============================================
# State 定义
# ============================================

class DiagnosisState(TypedDict):
    """诊断工作流状态"""
    # 输入
    evidence: Dict[str, Any]
    container_name: str
    fault_type: str
    
    # LLM 决策
    decision: Dict[str, Any]
    command: str
    reason: str
    
    # 执行结果
    action_result: Optional[Dict[str, Any]]
    notification_result: Optional[Dict[str, Any]]
    
    # 元数据
    timestamp: str
    error: Optional[str]


# ============================================
# SYSTEM PROMPT
# ============================================

SYSTEM_PROMPT = """你是一个容器故障诊断专家。分析以下容器故障证据，判断故障类型，并输出处理指令。

【阈值标准】
- CPU 警告阈值：70%，严重阈值：90%
- 内存警告阈值：70%，严重阈值：85%

【安全响应分级规则 (Security Tiering)】
Level 1 (攻击尝试/扫描):
- 特征: 仅日志中发现攻击特征 (如 UNION SELECT)，但无恶意进程，无异常外连。
- 动作: command: ALERT_ONLY (严禁 COMMIT/STOP，防止防御过当导致 Self-DoS)。

Level 2 (攻击成功/失陷):
- 特征: 发现恶意进程 (如 xmrig, nmap) OR 反弹 Shell (bash -i) OR 明确的命令执行痕迹。
- 动作: command: COMMIT (取证) + STOP (止损)。

【通用决策规则】
1. 容器崩溃 (exit_code 非 0 或 running=false) → command: RESTART
2. OOM Killed → command: STOP (内存溢出，重启无意义)
3. 资源使用 70%-90% → command: ALERT_ONLY
4. 资源使用 >90% 且容器健康 → command: ALERT_ONLY
5. 资源使用 >90% 且容器不健康 → command: RESTART
6. 内存泄漏疑似 (MEMORY_LEAK_SUSPECTED) → command: RESTART (预防性重启)
7. 安全事件 Level 1 (仅日志特征) → command: ALERT_ONLY (标记为 ATTACK_ATTEMPT)
8. 安全事件 Level 2 (恶意进程/实锤) → command: COMMIT (标记为 SECURITY_INCIDENT)
9. 已重启 3 次以上仍异常 → command: STOP
10. 一切正常 → command: NONE

【输出格式】必须是纯 JSON，无其他内容：
{
  "fault_type": "CPU_HIGH|MEMORY_HIGH|PROCESS_CRASH|OOM_KILLED|HEALTH_FAIL|MEMORY_LEAK_SUSPECTED|ATTACK_ATTEMPT|SECURITY_INCIDENT|NO_ERROR",
  "command": "RESTART|STOP|COMMIT|ALERT_ONLY|NONE",
  "params": {
    "container_name": "容器名",
    "current_cpu": "CPU使用率",
    "current_memory": "内存使用率",
    "retry_count": 0
  },
  "reason": "简短说明决策原因"
}"""


# ============================================
# Graph Nodes (节点函数)
# ============================================

def analyze_evidence(state: DiagnosisState) -> DiagnosisState:
    """
    节点1: 使用 LLM 分析证据并生成决策
    """
    config = get_config()
    evidence = state["evidence"]
    container_name = state["container_name"]
    
    logger.info(f"[LangGraph] analyze_evidence: {container_name}")
    
    # --- 规则引擎预检 (Rule-Based Pre-check) ---
    # 优先处理明确的安全威胁，无需消耗 LLM Token，且响应更快
    ev_data = evidence.get("evidence", {})
    security_issues = ev_data.get("security_issues", [])
    
    for issue in security_issues:
        if "发现恶意进程" in issue:
            logger.warning(f"规则引擎命中: 恶意进程 -> COMMIT+STOP")
            return {
                **state,
                "decision": {"fault_type": "SECURITY_INCIDENT", "reason": issue},
                "command": "COMMIT", # Executor 会处理 COMMIT 后的 STOP
                "reason": f"规则引擎检测到高危安全事件: {issue}",
                "error": None
            }
            
    # 检查重启次数 (Crash Loop)
    restart_count = ev_data.get("restart_count_24h", 0)
    if restart_count > 5: # 阈值可配置，这里硬编码为 5 以匹配 Prompt 规则
        logger.warning(f"规则引擎命中: 重启循环 ({restart_count}次) -> STOP")
        return {
            **state,
            "decision": {"fault_type": "PROCESS_CRASH", "reason": "Restart Loop Detected"},
            "command": "STOP",
            "reason": f"容器频繁重启 ({restart_count}次)，触发熔断保护",
            "error": None
        }

    # 检查 API Key
    if not config.llm.api_key:
        logger.error("DeepSeek API Key 未配置")
        return {
            **state,
            "decision": {},
            "command": "ALERT_ONLY",
            "reason": "API Key 未配置，仅告警",
            "error": "DEEPSEEK_API_KEY 未设置"
        }
    
    try:
        # 初始化 LLM
        llm = ChatOpenAI(
            model=config.llm.model,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            temperature=config.llm.temperature,
            timeout=config.llm.timeout_seconds,
            max_retries=config.llm.max_retries
        )
        
        # 构建用户消息
        evidence_str = json.dumps(evidence, ensure_ascii=False, indent=2)
        user_message = f"请分析以下容器故障证据：\n\n{evidence_str}"
        
        # 调用 LLM
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # 解析 JSON
        # 处理可能的 markdown 代码块
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        decision = json.loads(content)
        
        # 验证必需字段
        command = decision.get("command", "ALERT_ONLY")
        reason = decision.get("reason", "LLM 未提供原因")
        
        # 确保 params 中有 container_name
        if "params" not in decision:
            decision["params"] = {}
        decision["params"]["container_name"] = container_name
        
        logger.info(f"[LangGraph] LLM 决策: {command} - {reason[:50]}...")
        
        return {
            **state,
            "decision": decision,
            "command": command,
            "reason": reason,
            "error": None
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[LangGraph] JSON 解析失败: {e}")
        return {
            **state,
            "decision": {},
            "command": "ALERT_ONLY",
            "reason": f"LLM 输出解析失败: {str(e)}",
            "error": f"JSON_PARSE_ERROR: {str(e)}"
        }
    except Exception as e:
        logger.error(f"[LangGraph] LLM 调用失败: {e}")
        return {
            **state,
            "decision": {},
            "command": "ALERT_ONLY",
            "reason": f"LLM 调用异常: {str(e)}",
            "error": f"LLM_ERROR: {str(e)}"
        }


def execute_action_node(state: DiagnosisState) -> DiagnosisState:
    """
    节点2a: 执行容器操作 (RESTART/STOP)
    """
    container_name = state["container_name"]
    command = state["command"]
    reason = state["reason"]
    
    logger.info(f"[LangGraph] execute_action: {command} for {container_name}")
    
    try:
        # 执行操作
        result = execute_action(command, container_name)
        
        # 发送执行结果通知
        notification_data = {
            "type": "action_result",
            "command": command,
            "container_name": container_name,
            "fault_type": state.get("fault_type", "UNKNOWN"),
            "reason": reason,
            "action_response": result
        }
        notification_result = send_notification(notification_data)
        
        return {
            **state,
            "action_result": result,
            "notification_result": notification_result
        }
        
    except Exception as e:
        logger.error(f"[LangGraph] 执行操作失败: {e}")
        return {
            **state,
            "action_result": {"success": False, "error": str(e)},
            "error": f"EXECUTE_ERROR: {str(e)}"
        }


def send_alert_node(state: DiagnosisState) -> DiagnosisState:
    """
    节点2b: 发送告警通知 (ALERT_ONLY)
    """
    container_name = state["container_name"]
    decision = state.get("decision", {})
    params = decision.get("params", {})
    
    logger.info(f"[LangGraph] send_alert: {container_name}")
    
    try:
        notification_data = {
            "type": "alert",
            "container_name": container_name,
            "fault_type": state.get("fault_type", "UNKNOWN"),
            "current_cpu": params.get("current_cpu", ""),
            "current_memory": params.get("current_memory", ""),
            "reason": state.get("reason", "")
        }
        notification_result = send_notification(notification_data)
        
        return {
            **state,
            "notification_result": notification_result
        }
        
    except Exception as e:
        logger.error(f"[LangGraph] 发送告警失败: {e}")
        return {
            **state,
            "notification_result": {"success": False, "error": str(e)},
            "error": f"NOTIFY_ERROR: {str(e)}"
        }


def no_action_node(state: DiagnosisState) -> DiagnosisState:
    """
    节点2c: 无需操作 (NONE)
    """
    logger.info(f"[LangGraph] no_action: {state['container_name']} 运行正常")
    return state


def error_handler_node(state: DiagnosisState) -> DiagnosisState:
    """
    节点2d: 错误处理
    """
    error = state.get("error", "Unknown error")
    logger.error(f"[LangGraph] error_handler: {error}")
    
    # 发送错误告警
    try:
        notification_data = {
            "type": "alert",
            "container_name": state["container_name"],
            "fault_type": "SYSTEM_ERROR",
            "reason": f"诊断流程出错: {error}"
        }
        send_notification(notification_data)
    except:
        pass
    
    return state


# ============================================
# Conditional Edge (条件路由)
# ============================================

def route_by_command(state: DiagnosisState) -> str:
    """
    条件路由: 根据 command 决定下一个节点
    """
    command = state.get("command", "ALERT_ONLY")
    error = state.get("error")
    
    # 如果有错误，走错误处理
    if error and command not in ["RESTART", "STOP"]:
        return "error_handler"
    
    # 根据命令路由
    if command in ["RESTART", "STOP", "COMMIT"]:
        return "execute_action"
    elif command == "ALERT_ONLY":
        return "send_alert"
    elif command == "NONE":
        return "no_action"
    else:
        return "send_alert"  # 默认告警


# ============================================
# Graph 构建
# ============================================

def build_diagnosis_graph() -> StateGraph:
    """
    构建诊断工作流 Graph
    """
    # 创建 StateGraph
    workflow = StateGraph(DiagnosisState)
    
    # 添加节点
    workflow.add_node("analyze_evidence", analyze_evidence)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("send_alert", send_alert_node)
    workflow.add_node("no_action", no_action_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # 设置入口
    workflow.set_entry_point("analyze_evidence")
    
    # 添加条件边
    workflow.add_conditional_edges(
        "analyze_evidence",
        route_by_command,
        {
            "execute_action": "execute_action",
            "send_alert": "send_alert",
            "no_action": "no_action",
            "error_handler": "error_handler"
        }
    )
    
    # 所有执行节点都指向 END
    workflow.add_edge("execute_action", END)
    workflow.add_edge("send_alert", END)
    workflow.add_edge("no_action", END)
    workflow.add_edge("error_handler", END)
    
    return workflow.compile()


# 全局编译好的 Graph
_diagnosis_graph = None


def get_diagnosis_graph():
    """获取全局诊断 Graph (单例)"""
    global _diagnosis_graph
    if _diagnosis_graph is None:
        _diagnosis_graph = build_diagnosis_graph()
    return _diagnosis_graph


# ============================================
# DiagnosisAgent (封装 Graph)
# ============================================

class DiagnosisAgent:
    """
    容器故障诊断 Agent (基于 LangGraph)
    """
    
    def __init__(self):
        self.graph = get_diagnosis_graph()
        self.config = get_config()
    
    def diagnose(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行诊断工作流
        
        Args:
            evidence: 容器证据数据
            
        Returns:
            诊断结果
        """
        container_name = evidence.get("container", {}).get("name", "unknown")
        fault_type = evidence.get("fault_type", "UNKNOWN")
        
        logger.info(f"[DiagnosisAgent] 开始诊断: {container_name} - {fault_type}")
        
        # 构建初始状态
        initial_state: DiagnosisState = {
            "evidence": evidence,
            "container_name": container_name,
            "fault_type": fault_type,
            "decision": {},
            "command": "",
            "reason": "",
            "action_result": None,
            "notification_result": None,
            "timestamp": datetime.now().isoformat(),
            "error": None
        }
        
        # 执行 Graph
        try:
            final_state = self.graph.invoke(initial_state)
            
            logger.info(f"[DiagnosisAgent] 诊断完成: {container_name} - {final_state.get('command', 'N/A')}")
            
            return {
                "decision": final_state.get("decision", {}),
                "command": final_state.get("command", ""),
                "reason": final_state.get("reason", ""),
                "action_result": final_state.get("action_result"),
                "notification_result": final_state.get("notification_result"),
                "timestamp": final_state.get("timestamp", ""),
                "error": final_state.get("error")
            }
            
        except Exception as e:
            logger.error(f"[DiagnosisAgent] Graph 执行失败: {e}")
            return {
                "decision": {},
                "command": "ERROR",
                "reason": str(e),
                "action_result": None,
                "notification_result": None,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }


# ============================================
# 任务队列 (异步处理)
# ============================================

class DiagnosisTaskQueue:
    """
    诊断任务队列 - 异步处理诊断请求
    """
    
    def __init__(self, max_workers: int = 1):
        self.queue = Queue()
        self.workers = []
        self.max_workers = max_workers
        self.lock = Lock()
        self.running = False
    
    def start(self):
        """启动工作线程"""
        if self.running:
            return
        
        self.running = True
        for i in range(self.max_workers):
            worker = Thread(
                target=self._worker_loop,
                name=f"DiagnosisWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"[TaskQueue] 已启动，工作线程数: {self.max_workers}")
    
    def stop(self):
        """停止工作线程"""
        self.running = False
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                break
        logger.info("[TaskQueue] 已停止")
    
    def submit(self, evidence: Dict[str, Any], callback: Optional[callable] = None):
        """提交诊断任务"""
        task = {
            "evidence": evidence,
            "callback": callback,
            "submitted_at": datetime.now()
        }
        self.queue.put(task)
        logger.debug(f"[TaskQueue] 任务已提交，队列长度: {self.queue.qsize()}")
    
    def _worker_loop(self):
        """工作线程主循环"""
        agent = DiagnosisAgent()
        
        while self.running:
            try:
                task = self.queue.get(timeout=1)
                self._process_task(agent, task)
                self.queue.task_done()
            except Exception:
                # Queue.Empty 或其他异常，继续循环
                pass
    
    def _process_task(self, agent: DiagnosisAgent, task: Dict[str, Any]):
        """处理单个任务"""
        evidence = task["evidence"]
        callback = task.get("callback")
        
        try:
            result = agent.diagnose(evidence)
            
            # 记录到历史文件 (用于每日总结)
            self._append_to_history(result)
            
            if callback:
                callback(result)
        except Exception as e:
            logger.error(f"[TaskQueue] 任务处理失败: {e}")

    def _append_to_history(self, result: Dict[str, Any]):
        """将诊断结果追加到历史文件"""
        try:
            history_file = "data/history.jsonl"
            os.makedirs("data", exist_ok=True)
            
            # 提取关键信息，减少存储体积
            record = {
                "timestamp": datetime.now().isoformat(),
                "container": result.get("container_name"),
                "fault_type": result.get("fault_type"),
                "command": result.get("command"),
                "reason": result.get("reason"),
                "action_success": result.get("action_result", {}).get("success", False) if result.get("action_result") else None
            }
            
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                
        except Exception as e:
            logger.error(f"写入历史记录失败: {e}")


# 全局任务队列
_task_queue: Optional[DiagnosisTaskQueue] = None


def get_task_queue() -> DiagnosisTaskQueue:
    """获取全局任务队列"""
    global _task_queue
    if _task_queue is None:
        _task_queue = DiagnosisTaskQueue(max_workers=1)
        _task_queue.start()
    return _task_queue





# ============================================
# 便捷函数
# ============================================



# ============================================
# 便捷函数
# ============================================

def run_diagnosis(evidence: Dict[str, Any], async_mode: bool = False) -> Dict[str, Any]:
    """
    运行容器故障诊断
    
    Args:
        evidence: 容器证据
        async_mode: 是否异步执行
        
    Returns:
        包含状态信息的字典
    """
    if async_mode:
        task_queue = get_task_queue()
        task_queue.submit(evidence)
        return {"status": "submitted", "message": "任务已提交到队列"}
    else:
        agent = DiagnosisAgent()
        result = agent.diagnose(evidence)
        return {"status": "completed", "message": "任务已完成", "result": result}


# 保留旧的函数名以兼容
def analyze_with_llm(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    [兼容函数] 使用 LLM 分析证据
    """
    result = run_diagnosis(evidence, async_mode=False)
    return result.get("decision", {}) if result else {}

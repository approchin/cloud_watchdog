"""
报告生成模块
"""
import os
import json
import logging
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from .config import get_config

logger = logging.getLogger(__name__)

def generate_daily_summary():
    """
    生成每日总结报告 (归档)
    读取 history.jsonl -> LLM 总结 -> 保存为 Markdown -> 清空 history
    """
    history_file = "data/history.jsonl"
    if not os.path.exists(history_file):
        logger.info("没有历史记录，跳过每日总结")
        return

    try:
        # 1. 读取历史记录
        records = []
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        if not records:
            return

        # 2. 简单的统计
        total_events = len(records)
        fault_counts = {}
        for r in records:
            ft = r.get("fault_type", "UNKNOWN")
            fault_counts[ft] = fault_counts.get(ft, 0) + 1
            
        # 3. 调用 LLM 生成总结 (直接 Invoke，不走 Agent 流程)
        config = get_config()
        llm = ChatOpenAI(
            model=config.llm.model,
            temperature=0.3,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url
        )
        
        prompt = f"""请根据以下 Docker 容器故障处理记录，生成一份简要的每日运维日报。
        
        【统计数据】
        总事件数: {total_events}
        故障分布: {fault_counts}
        
        【详细记录 (最近 20 条)】
        {json.dumps(records[-20:], ensure_ascii=False, indent=2)}
        
        【要求】
        1. 总结今日系统的整体健康状况。
        2. 指出最频繁出现的故障类型和容器。
        3. 给出针对性的优化建议。
        4. 使用 Markdown 格式。
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        summary_content = response.content
        
        # 4. 保存归档
        report_dir = "reports"
        os.makedirs(report_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        report_path = os.path.join(report_dir, f"daily_report_{date_str}.md")
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# Cloud Watchdog 每日运维报告 ({date_str})\n\n")
            f.write(summary_content)
            
        logger.info(f"每日报告已生成: {report_path}")
        
        # 5. 归档/清理历史文件 (重命名备份)
        archive_path = os.path.join("data", f"history_{date_str}.jsonl")
        os.rename(history_file, archive_path)
        
    except Exception as e:
        logger.error(f"生成每日报告失败: {e}")

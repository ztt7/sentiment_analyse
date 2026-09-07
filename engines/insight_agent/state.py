from typing import TypedDict

from engines.contracts.evidence.models import EvidenceStrength
from engines.insight_agent.evidence_processor import EvidencePool, EvidenceRecord


class InsightSection(TypedDict, total=False):
    """单章节交付物：标题、目标、正文与证据强度。"""
    # 1.章节规划信息第一阶段：由PLanNode初始化时的规划信息
    title: str
    goal: list[str]
    section_key: str
    # 2.章节写作结果第二阶段：由SummarizeNode动态补充的写作结果与元数据
    body: str   # 章节摘要
    hit_count: int
    evidence_strength: EvidenceStrength


class InsightState(TypedDict, total=False):
    """LangGraph 全局状态：证据池、章节列表与游标。"""
    # 入口参数.查询信息第一阶段：由QueryNode初始化时的查询信息
    query: str
    role: str
    evidence_pool: EvidencePool
    # 执行状态（中间产物）
    sections: list[InsightSection]
    section_evidence_records: list[list[EvidenceRecord]]
    # 流程控制游标
    cursor: int
    # 最终交付物
    final_report: str
    report_title: str

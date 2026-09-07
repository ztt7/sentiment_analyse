from typing import Any

from engines.common.nodes.base_node import BaseNode, ResearchNodeContext
from engines.insight_agent.evidence_processor import (
    EvidencePool,
    EvidenceRecord,
    generate_section_records,
)
from engines.insight_agent.state import InsightSection, InsightState

"""InsightAgent章节证据调拨节点：将全局证据中的数据按章节维度路由至对应的上下文。"""

class SectionAllocationNode(BaseNode):
    """证据分配节点：按章节键为各章节配置证据。"""

    def __init__(self, context: ResearchNodeContext) -> None:
        """初始化证据分配节点上下文。"""
        super().__init__(context)

    async def __call__(self, state: InsightState) -> dict[str, Any]:
        """为每个章节筛选并截取对应证据记录。"""
        pool: EvidencePool = state["evidence_pool"]
        records = pool.records
        sections: list[InsightSection] = list(state.get("sections"))
        section_evidence_records: list[list[EvidenceRecord]] = []
        # 遍历各章节，根据section_key路由匹配的证据记录
        for section in sections:
            section_key = section["section_key"]
            # 筛选并截断符合维度的证据
            section_records = generate_section_records(section_key, records)[:20]
            # 将该章节对应的证据记录存入中间容器
            section_evidence_records.append(section_records)
        return {"sections": sections, "section_evidence_records": section_evidence_records}

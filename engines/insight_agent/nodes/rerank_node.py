from collections import defaultdict
from typing import Any, Optional

from engines.common.nodes.base_node import BaseNode, ResearchNodeContext
from engines.contracts.evidence.models import EvidenceRecord, RetrievalMeta
from engines.insight_agent.state import InsightState

_CHANNEL_WEIGHTS = {
    "semantic_recall": 0.5,
    "keyword_recall": 0.4,
    "comment_recall": 0.4,
    "hot_recall": 0.20,
}

_CHANNEL_QUOTAS = {
    "keyword_recall": 10,
    "semantic_recall": 10,
    "comment_recall": 20,
    "hot_recall": 10,
}

MAX_EVIDENCE_RECORDS = 50


class RerankNode(BaseNode):
    """重排节点：去重、加权评分与渠道配额裁剪。"""

    def __init__(self, context: ResearchNodeContext) -> None:
        """初始化重排节点上下文。"""
        super().__init__(context)

    async def __call__(self, state: InsightState) -> dict[str, Any]:
        # 1. 获取evidence_pool
        evidence_pool = state['evidence_pool']

        # 2. 获取records
        records = evidence_pool.records

        # 3. 去重、合并
        merged_records = _dedupe_and_merge(records)

        # 4. 打分、排序
        sorted_records = _score_and_sort(merged_records)

        # 5. 根据通道选择指定的证据记录对象列表【通道配额筛选】
        evidence_records = _apply_channel_quotas(sorted_records)

        # 4. 更新state的证据池中的证据记录
        evidence_pool.records = evidence_records

        # 5. 返回
        return {"evidence_pool": evidence_pool}


def _dedupe_and_merge(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """按记录 ID 去重并合并召回元数据。"""
    # 1. 判断是否有证据记录
    if not records:
        return []

    # 2. 遍历(去除重复的：MySQL三个通道的检索会不会重复？有可能：query:分词:【分词1.分词2】---分词1，分词2都获取到了同一条数据  Milvus中返回的查询记录可也可能和MySQL中查询某张表记录重复)
    # 2.1 基于ID即可

    records_by_id: dict[str, EvidenceRecord] = {}
    for record in records:

        # 1. 获取记录ID
        record_id = record.id

        # 2. 判断当前记录ID是否已经存在
        if record_id not in records_by_id:
            records_by_id[record_id] = record
            continue

        # 3. 当前记录已经存在(不是剔除掉重复的记录，而是利用重复的记录)
        # 3.1 更新当前记录的热度值(找同一条记录中最大热度值的那一个)
        # 3.2 更新当前记录的检索元数据（更新检索元数据的查询【字符串相加】、更新检索元数据的通道【字符串相加】 更新元数据的检索分数:复杂一点）

        base_record = records_by_id[record_id]
        base_record.retrieval = _merge_retrieval_meta(base_record, record)
        base_record.hotness_score = max(base_record.hotness_score,
                                        record.hotness_score)  # 两套规则计算热度值（我们的多源数据:Milvus中的数据和MySQL中一致）

    # 4. 重复记录（利用起来）
    return list(records_by_id.values())


def _merge_retrieval_meta(base_record: EvidenceRecord, new_record: EvidenceRecord) -> RetrievalMeta:
    """合并两条记录的召回渠道、查询与得分。"""
    base_record.retrieval.retrieval_scores.update(new_record.retrieval.retrieval_scores)
    return RetrievalMeta(
        matched_queries=sorted(
            set(base_record.retrieval.matched_queries + new_record.retrieval.matched_queries)
        ),
        retrieval_channels=sorted(
            set(
                (base_record.retrieval.retrieval_channels + new_record.retrieval.retrieval_channels)
            )
        ),
        retrieval_scores=base_record.retrieval.retrieval_scores,
    )


def _retrival_score(merged_record: EvidenceRecord) -> float:
    """按渠道权重加权召回得分并截断至 1。"""
    meta = merged_record.retrieval
    score = 0.0
    for ch in meta.retrieval_channels:
        w = _CHANNEL_WEIGHTS.get(ch)
        s = meta.retrieval_scores.get(ch)
        if w is None or s is None:
            continue
        score += s * w
    return min(score, 1.0)


def _score_and_sort(merged_records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """融合召回分与热度分排序证据记录。"""
    # EvidenceRecord对象的检索元数据的通道就有可能是多个["keyword_recall","sematic_recall"]
    max_hot_score = max([merged_record.hotness_score for merged_record in merged_records]) or 1.0
    for merged_record in merged_records:
        # 总得分（二因子）检索相关得分*0.6+热度值*0.4
        final_score = (_retrival_score(merged_record) * 0.6 + ((merged_record.hotness_score / max_hot_score) * 0.4))
        merged_record.final_score = final_score

    return sorted(merged_records, key=lambda record: record.final_score, reverse=True)


def _apply_channel_quotas(sorted_records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """按渠道配额裁剪证据并补足至上限。"""
    selected_records = []
    channel_count: dict[str, int] = defaultdict(int)
    for record in sorted_records:
        channel = _select_quota_channel(record)
        if channel is not None and channel_count[channel] < _CHANNEL_QUOTAS[channel]:
            selected_records.append(record)
            channel_count[channel] += 1
    if len(selected_records) < MAX_EVIDENCE_RECORDS:
        selected_ids = [r.id for r in selected_records]
        remainders = [r for r in sorted_records if r.id not in selected_ids]
        selected_records.extend(remainders[: (MAX_EVIDENCE_RECORDS - len(selected_ids))])
    return sorted(selected_records, key=lambda record: record.final_score, reverse=True)


def _select_quota_channel(record: EvidenceRecord) -> Optional[str]:
    """选取记录命中的首个配额渠道。"""
    for channel in _CHANNEL_QUOTAS:
        if channel == "other":
            continue
        if channel in record.retrieval.retrieval_channels:
            return channel
    return None

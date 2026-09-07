from dataclasses import dataclass, field
from typing import Literal, Optional

EvidenceStrength = Literal["missing", "weak", "medium", "strong"]

# 第一组：元数据
@dataclass(slots=True)
class Engagement:
    """证据互动数据(点赞/评论/转发等)"""

    likes: float = 0.0
    comments: float = 0.0
    shares: float = 0.0
    collects: float = 0.0
    replies: float = 0.0


@dataclass(slots=True)
class RetrievalMeta:
    """召回过程元数据(查询词/通道/分数)"""
    # 召回来源
    matched_queries: list[str] = field(default_factory=list)
    retrieval_channels: list[str] = field(default_factory=list)
    # 召回质量
    retrieval_scores: dict[str, float] = field(default_factory=dict)

# 第二组：核心业务实体
@dataclass(slots=True)
class EvidenceRecord:
    """统一证据记录(DB/Milvus召回的统一数据载体)"""
    # 溯源身份标识
    id: str
    platform: str
    source_table: str
    source_keyword: Optional[str]
    # 核心业务内容
    content: str
    published_at: str
    # 打分状态
    hotness_score: float = 0.0
    final_score: float = 0.0
    # 拓扑对象
    cluster_id: str = ""
    engagement: Engagement = field(default_factory=Engagement)
    retrieval: RetrievalMeta = field(default_factory=RetrievalMeta)
    # media网页证据专属字段(insight DB/向量证据留空即可，不参与其排序/聚类逻辑)
    url: str = ""

"""数据库查询返回的列的定义。"""
from typing import Mapping, cast

from sqlalchemy import DECIMAL, cast as sa_cast, column, func, literal, literal_column
from sqlalchemy.sql.elements import ColumnElement

from engines.insight_agent.tools.hotness import ENGAGEMENT_METRICS, HotScoreWeights
from engines.insight_agent.tools.platform_mappings import (
    CommentTableMapping,
    ContentTableMapping,
    PlatformSearchMapping,
)

# 封装基础字段的投影
def content_search_columns(platform_mapping: PlatformSearchMapping) -> list[ColumnElement]:
    """生成内容表检索所需的标准列定义列表。"""
    content_mapping = platform_mapping.content_mapping
    return [
        literal(platform_mapping.platform_name).label("platform"),
        literal(content_mapping.table_name).label("source_table"),
        column("id").label("mysql_pk"),
        column(content_mapping.text_col).label("title"),
        column(content_mapping.published_at_col).label("published_at"),
        column(content_mapping.source_keyword_col).label("source_keyword"),
    ]

# 封装基础字段的投影
def comment_search_columns(platform_mapping: PlatformSearchMapping) -> list[ColumnElement]:
    """生成评论表检索所需的标准列定义列表。"""
    comment_mapping = platform_mapping.comment_mapping
    return [
        literal(platform_mapping.platform_name).label("platform"),
        literal(comment_mapping.table_name).label("source_table"),
        column("id").label("mysql_pk"),
        column(comment_mapping.text_col).label("title"),
        column(comment_mapping.published_at_col).label("published_at"),
        literal_column("NULL").label("source_keyword"),
    ]

# 内容表以及评论表的互动字段
def engagement_metric_columns(engagement_column_map: Mapping[str, str]) -> list[ColumnElement]:
    """根据互动指标映射构建带统一前缀的互动数据列列表。"""
    result_columns = []
    # 遍历所有的参与度指标
    for engagement_metric in ENGAGEMENT_METRICS:
        # 判断当前指标是否在映射字典中   engagement_column_map 是具体的某个平台参与度指标
        if engagement_metric in engagement_column_map:
            mapped_column = engagement_column_map[engagement_metric]
            base_column = safe_number_column(mapped_column)
        else:
            # 如果映射中没有当前指标，使用默认值 0
            base_column = literal_column("0")
        # 统一给该列加上 as 别名
        labeled_column = base_column.label(f"eng_{engagement_metric}")
        result_columns.append(labeled_column)
    # 返回最终的列表
    return result_columns


def hot_score_metric_column(
    table_mapping: ContentTableMapping | CommentTableMapping,
) -> ColumnElement:
    """基于平台各互动指标及对应权重，动态生成热度计算的SQL表达式。"""
    hotness_expression = None
    metric_weights = HotScoreWeights()
    # 遍历当前平台配置的互动指标字典
    # metric_key:标准化指标名
    # db_column_name:该平台数据库中的真实列名
    for metric_key, db_column_name in table_mapping.engagement_cols.items():
        # 1.动态获取该指标对应的权重值
        current_weight = getattr(metric_weights, metric_key)
        # 2.组装单个指标的加权sql片段
        weighted_metric_term = safe_number_column(db_column_name) * current_weight
        # 3.将当前片段累加到总表达式中
        if hotness_expression is None:
            hotness_expression = weighted_metric_term
        else:
            hotness_expression = hotness_expression + weighted_metric_term
    # 将最终的算式强制转换为列元素
    return cast(ColumnElement, hotness_expression).label("hotness_score")


def safe_number_column(col_name: str) -> ColumnElement:
    """将列转换为数字类型并处理 NULL 值，确保数值计算安全。"""
    return func.coalesce(sa_cast(column(col_name), DECIMAL), 0.0)

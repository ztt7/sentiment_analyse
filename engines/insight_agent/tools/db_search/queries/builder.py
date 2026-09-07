"""数据库查询构建器。构建数据库查询语句。"""
from sqlalchemy import bindparam, column, desc, or_, select, table, union_all
from sqlalchemy.sql import Select

from engines.insight_agent.tools.db_search.queries.columns import (
    comment_search_columns,
    content_search_columns,
    engagement_metric_columns,
    hot_score_metric_column,
)
from engines.insight_agent.tools.hotness import HotRecallPeriod, hot_recall_start_time
from engines.insight_agent.tools.platform_mappings import PlatformSearchMapping


def build_hotness_query(
        platform_mapping: PlatformSearchMapping,
        time_period: HotRecallPeriod,
        limit: int,
) -> Select:
    """构建热度召回查询，合并内容表与评论表符合时间范围的热度数据。"""
    start_time = hot_recall_start_time(time_period)
    platform_hot_queries = []
    # 2.统一遍历并处理该平台的内容表和评论表
    for table_mapping, search_columns in [
        (platform_mapping.content_mapping, content_search_columns),
        (platform_mapping.comment_mapping, comment_search_columns),
    ]:
        # 3.构造时间过滤条件（参数命名携带表名后缀，防止多表UION冲突）
        recent_record_condition = column(table_mapping.published_at_col) >= bindparam(
            f"time_{platform_mapping.platform_name}_{table_mapping.table_name}",
            int(start_time.timestamp()),
        )
        # 4.获取该表的热度分数计算公式列
        hot_score_expr = hot_score_metric_column(table_mapping)
        # 5.构建单表查询过滤时间、按热度降序排序并限制召回条数
        table_hot_query = (
            select(
                *search_columns(platform_mapping),
                *engagement_metric_columns(table_mapping.engagement_cols),
                hot_score_expr,
            )
            .select_from(table(table_mapping.table_name))
            .where(recent_record_condition)
            .order_by(desc(hot_score_expr))
            .limit(limit)
        )
        platform_hot_queries.append(table_hot_query)
    return union_all(*platform_hot_queries)  # type: ignore


def build_content_search_query(
        platform_mapping: PlatformSearchMapping, search_term: str, limit: int
) -> Select:
    """构建单平台内容表关键词模糊匹配查询。"""
    content_mapping = platform_mapping.content_mapping
    # 1.动态生成针对多字段的模糊查询条件
    where_clauses = [
        column(field).like(bindparam(f"term_{content_mapping.table_name}_{i}", search_term))
        for i, field in enumerate(content_mapping.search_fields)
    ]
    hot_score_expr = hot_score_metric_column(content_mapping)
    # 2.组装并返回查询应用条件匹配
    return (
        select(
            *content_search_columns(platform_mapping),
            *engagement_metric_columns(content_mapping.engagement_cols),
            hot_score_expr,
        )
        .select_from(table(content_mapping.table_name))
        .where(or_(*where_clauses))
        .order_by((column("id")))
        .limit(limit)
    )


def build_comment_search_query(
        platform_mapping: PlatformSearchMapping, search_term: str, limit: int
) -> Select:
    """构建评论检索查询，根据关键词模糊匹配评论表字段。"""
    comment_mapping = platform_mapping.comment_mapping
    where_clauses = [
        column(field).like(bindparam(f"term_{comment_mapping.table_name}_{i}", search_term))
        for i, field in enumerate(comment_mapping.search_fields)
    ]
    hot_score_expr = hot_score_metric_column(comment_mapping)
    return (
        select(
            *comment_search_columns(platform_mapping),
            *engagement_metric_columns(comment_mapping.engagement_cols),
            hot_score_expr,
        )
        .select_from(table(comment_mapping.table_name))
        .where(or_(*where_clauses))
        .order_by((column("id")))
        .limit(limit)
    )

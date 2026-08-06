"""生成促销和优惠券不可变规则版本"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Table

from ..support import (
    END_OF_TIME,
    SOURCE_SYSTEM,
    UNKNOWN_ID,
    UNKNOWN_SK,
    TableWriter,
    load_rows,
    stable_hash,
    start_of_day,
)
from ...settings import RunContext

logger = logging.getLogger(__name__)


def _rule_audit(rule: dict, ctx: RunContext) -> dict:
    return {
        "rule_hash": stable_hash(rule),
        "source_system_code": SOURCE_SYSTEM,
        "source_update_time": None,
        "load_batch_id": ctx.batch_id,
    }


def _promotion_rows(ctx: RunContext):
    activity_start = start_of_day(ctx.gen.start_date)
    activity_end = start_of_day(ctx.gen.end_date + timedelta(days=1))
    unknown = {
        "promotion_version_sk": UNKNOWN_SK,
        "promotion_id": UNKNOWN_ID,
        "rule_version_no": 1,
        "promotion_name": "未知促销",
        "promotion_type": "未知",
        "promotion_scene": "未知",
        "promotion_priority": 1,
        "activity_start_time": datetime(1900, 1, 1),
        "activity_end_time": END_OF_TIME,
        "rule_effective_start_time": datetime(1900, 1, 1),
        "rule_effective_end_time": END_OF_TIME,
        "rule_description": "未知促销规则",
        "threshold_amount": None,
        "discount_amount": None,
        "discount_rate": None,
        "max_discount_amount": None,
        "sponsor_type": "未知",
        "sponsor_business_id": None,
        "promotion_status": "已发布",
    }
    yield unknown | _rule_audit(unknown, ctx)
    types = ("满减", "折扣", "直降")
    for idx in range(ctx.gen.promotion_count):
        promotion_type = types[idx % len(types)]
        threshold = Decimal(str((idx % 5 + 1) * 100))
        discount = Decimal(str((idx % 4 + 1) * 10))
        rate = Decimal("0.900000") if promotion_type == "折扣" else None
        rule = {
            "promotion_id": 30_000_001 + idx,
            "rule_version_no": 1,
            "promotion_name": f"全场{promotion_type}活动{idx + 1:03d}",
            "promotion_type": promotion_type,
            "promotion_scene": "全场活动",
            "promotion_priority": idx % 10 + 1,
            "activity_start_time": activity_start,
            "activity_end_time": activity_end,
            "rule_effective_start_time": activity_start,
            "rule_effective_end_time": END_OF_TIME,
            "rule_description": f"满{threshold}享{discount}元优惠",
            "threshold_amount": threshold,
            "discount_amount": discount if promotion_type != "折扣" else None,
            "discount_rate": rate,
            "max_discount_amount": Decimal("100.00")
            if promotion_type == "折扣"
            else None,
            "sponsor_type": "平台",
            "sponsor_business_id": "PLATFORM",
            "promotion_status": "已发布",
        }
        yield rule | _rule_audit(rule, ctx)


def _coupon_rows(ctx: RunContext):
    use_start = start_of_day(ctx.gen.start_date)
    use_end = start_of_day(ctx.gen.end_date + timedelta(days=1))
    unknown = {
        "coupon_template_version_sk": UNKNOWN_SK,
        "coupon_template_id": UNKNOWN_ID,
        "rule_version_no": 1,
        "coupon_name": "未知优惠券",
        "coupon_type": "未知",
        "threshold_amount": None,
        "discount_amount": None,
        "discount_rate": None,
        "max_discount_amount": None,
        "issue_start_time": datetime(1900, 1, 1),
        "issue_end_time": END_OF_TIME,
        "use_start_time": datetime(1900, 1, 1),
        "use_end_time": END_OF_TIME,
        "rule_effective_start_time": datetime(1900, 1, 1),
        "rule_effective_end_time": END_OF_TIME,
        "total_issue_limit": None,
        "per_user_limit": None,
        "coupon_status": "已发布",
    }
    yield unknown | _rule_audit(unknown, ctx)
    for idx in range(ctx.gen.coupon_count):
        is_discount = idx % 3 == 2
        threshold = Decimal(str((idx % 5 + 1) * 50))
        discount = Decimal(str((idx % 4 + 1) * 5))
        rule = {
            "coupon_template_id": 40_000_001 + idx,
            "rule_version_no": 1,
            "coupon_name": f"通用{'折扣' if is_discount else '满减'}券{idx + 1:03d}",
            "coupon_type": "折扣券" if is_discount else "满减券",
            "threshold_amount": threshold,
            "discount_amount": None if is_discount else discount,
            "discount_rate": Decimal("0.950000") if is_discount else None,
            "max_discount_amount": Decimal("50.00") if is_discount else None,
            "issue_start_time": use_start,
            "issue_end_time": use_end,
            "use_start_time": use_start,
            "use_end_time": use_end,
            "rule_effective_start_time": use_start,
            "rule_effective_end_time": END_OF_TIME,
            "total_issue_limit": 1_000_000,
            "per_user_limit": 10,
            "coupon_status": "已发布",
        }
        yield rule | _rule_audit(rule, ctx)


def run(ctx: RunContext, tables: dict[str, Table]) -> None:
    with ctx.engine.connect() as conn:
        writer = TableWriter(
            ctx.loader,
            ctx.gen.batch_size,
            ctx.gen.start_date,
            ctx.as_of_time,
        )
        writer.add_many("dim_promotion_rule_version", _promotion_rows(ctx))
        writer.add_many("dim_coupon_template_version", _coupon_rows(ctx))
        writer.flush_all()
        promotions = load_rows(
            conn,
            tables["dim_promotion_rule_version"],
            where=tables["dim_promotion_rule_version"].c.promotion_id != UNKNOWN_ID,
        )
        coupons = load_rows(
            conn,
            tables["dim_coupon_template_version"],
            where=tables["dim_coupon_template_version"].c.coupon_template_id
            != UNKNOWN_ID,
        )
        for promotion in promotions:
            writer.add(
                "bridge_promotion_scope",
                {
                    "promotion_version_sk": promotion["promotion_version_sk"],
                    "promotion_id": promotion["promotion_id"],
                    "scope_type": "ALL",
                    "scope_business_id": "*",
                    "is_excluded": 0,
                    "source_system_code": SOURCE_SYSTEM,
                    "load_batch_id": ctx.batch_id,
                },
            )
        for coupon in coupons:
            writer.add(
                "bridge_coupon_scope",
                {
                    "coupon_template_version_sk": coupon["coupon_template_version_sk"],
                    "coupon_template_id": coupon["coupon_template_id"],
                    "scope_type": "ALL",
                    "scope_business_id": "*",
                    "is_excluded": 0,
                    "source_system_code": SOURCE_SYSTEM,
                    "load_batch_id": ctx.batch_id,
                },
            )
        counts = writer.flush_all()
    logger.info("营销域生成完成 %s", counts)

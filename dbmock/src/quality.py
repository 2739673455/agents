"""跨表数据质量校验"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from sqlalchemy import Table, text

from .checkpoint import CheckpointStore
from .settings import RunContext
from .support import doris_unique_key_columns, iter_jsonl_rows
from .timeline import month_periods

logger = logging.getLogger(__name__)

CHECKS: dict[str, str] = {
    "日期节假日配置": """
        SELECT
            CASE
                WHEN DATEDIFF(MAX(full_date), MIN(full_date)) >= 365
                 AND SUM(is_holiday) = 0
                THEN 1
                ELSE 0
            END
            + SUM(
                CASE
                    WHEN is_holiday = 1
                     AND (holiday_name IS NULL OR is_workday <> 0)
                    THEN 1
                    WHEN is_holiday = 0 AND holiday_name IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            )
        FROM dim_date
    """,
    "订单活动优惠分摊": """
        SELECT COUNT(*)
        FROM dwd_trade_order_detail_di d
        LEFT JOIN (
            SELECT order_detail_id, SUM(promotion_discount_amount) amount
            FROM dwd_trade_order_detail_activity_di
            GROUP BY order_detail_id
        ) a ON a.order_detail_id = d.order_detail_id
        WHERE d.activity_discount_amount <> COALESCE(a.amount, 0)
    """,
    "订单优惠券分摊": """
        SELECT COUNT(*)
        FROM dwd_trade_order_detail_di d
        LEFT JOIN (
            SELECT order_detail_id, SUM(coupon_discount_amount) amount
            FROM dwd_trade_order_detail_coupon_di
            GROUP BY order_detail_id
        ) c ON c.order_detail_id = d.order_detail_id
        WHERE d.coupon_discount_amount <> COALESCE(c.amount, 0)
    """,
    "支付金额分摊": """
        SELECT COUNT(*)
        FROM dwd_trade_pay_detail_di p
        LEFT JOIN (
            SELECT pay_detail_id, SUM(allocated_pay_amount) amount
            FROM dwd_trade_pay_order_detail_di
            GROUP BY pay_detail_id
        ) a ON a.pay_detail_id = p.pay_detail_id
        WHERE p.requested_pay_amount <> COALESCE(a.amount, 0)
    """,
    "包裹重量和运费分摊": """
        SELECT COUNT(*)
        FROM dwd_trade_delivery_di d
        LEFT JOIN (
            SELECT delivery_id,
                   SUM(allocated_weight_kg) weight,
                   SUM(allocated_freight_amount) freight
            FROM dwd_trade_delivery_item_di
            GROUP BY delivery_id
        ) i ON i.delivery_id = d.delivery_id
        WHERE d.package_weight_kg <> COALESCE(i.weight, 0)
           OR d.package_freight_amount <> COALESCE(i.freight, 0)
    """,
    "事实业务日期": """
        SELECT SUM(violations) FROM (
            SELECT COUNT(*) violations FROM dwd_trade_order_detail_di
             WHERE biz_date <> DATE(order_create_time)
                OR order_date_key <> DATE_FORMAT(order_create_time, '%Y%m%d') + 0
            UNION ALL
            SELECT COUNT(*) FROM dwd_trade_pay_detail_di
             WHERE biz_date <> DATE(pay_request_time)
                OR pay_date_key <> DATE_FORMAT(pay_request_time, '%Y%m%d') + 0
            UNION ALL
            SELECT COUNT(*) FROM dwd_inventory_change_di
             WHERE biz_date <> DATE(event_time)
                OR event_date_key <> DATE_FORMAT(event_time, '%Y%m%d') + 0
        ) q
    """,
    "业务状态时间严格递增": """
        SELECT SUM(violations) FROM (
            SELECT COUNT(*) violations FROM (
                SELECT event_time,
                       LAG(event_time) OVER (
                           PARTITION BY order_id ORDER BY event_seq_no
                       ) previous_time
                FROM dwd_trade_order_status_event_di
            ) x
            WHERE previous_time IS NOT NULL AND event_time <= previous_time
            UNION ALL
            SELECT COUNT(*) FROM (
                SELECT event_time,
                       LAG(event_time) OVER (
                           PARTITION BY pay_detail_id ORDER BY event_seq_no
                       ) previous_time
                FROM dwd_trade_pay_status_event_di
            ) x
            WHERE previous_time IS NOT NULL AND event_time <= previous_time
            UNION ALL
            SELECT COUNT(*) FROM (
                SELECT event_time,
                       LAG(event_time) OVER (
                           PARTITION BY delivery_id ORDER BY event_seq_no
                       ) previous_time
                FROM dwd_trade_delivery_status_event_di
            ) x
            WHERE previous_time IS NOT NULL AND event_time <= previous_time
            UNION ALL
            SELECT COUNT(*) FROM (
                SELECT event_time,
                       LAG(event_time) OVER (
                           PARTITION BY refund_detail_id ORDER BY event_seq_no
                       ) previous_time
                FROM dwd_trade_refund_status_event_di
            ) x
            WHERE previous_time IS NOT NULL AND event_time <= previous_time
            UNION ALL
            SELECT COUNT(*) FROM (
                SELECT event_time,
                       LAG(event_time) OVER (
                           PARTITION BY refund_pay_detail_id ORDER BY event_seq_no
                       ) previous_time
                FROM dwd_trade_refund_pay_status_event_di
            ) x
            WHERE previous_time IS NOT NULL AND event_time <= previous_time
        ) q
    """,
    "订单维度时点命中": """
        SELECT COUNT(*)
        FROM dwd_trade_order_detail_di f
        LEFT JOIN dim_user_info_zip u
          ON u.user_sk = f.user_sk
         AND u.user_id = f.user_id
         AND f.order_create_time >= u.effective_start_time
         AND f.order_create_time < u.effective_end_time
        LEFT JOIN dim_shop_info_zip sh
          ON sh.shop_sk = f.shop_sk
         AND sh.shop_id = f.shop_id
         AND f.order_create_time >= sh.effective_start_time
         AND f.order_create_time < sh.effective_end_time
        LEFT JOIN dim_sku_info_zip sk
          ON sk.sku_sk = f.sku_sk
         AND sk.sku_id = f.sku_id
         AND f.order_create_time >= sk.effective_start_time
         AND f.order_create_time < sk.effective_end_time
        LEFT JOIN dim_spu_info_zip sp
          ON sp.spu_sk = f.spu_sk
         AND sp.spu_id = f.spu_id
         AND f.order_create_time >= sp.effective_start_time
         AND f.order_create_time < sp.effective_end_time
        LEFT JOIN dim_category_info_zip c
          ON c.category_sk = f.category_sk
         AND c.category_id = f.category_id
         AND f.order_create_time >= c.effective_start_time
         AND f.order_create_time < c.effective_end_time
        WHERE u.user_sk IS NULL OR sh.shop_sk IS NULL OR sk.sku_sk IS NULL
           OR sp.spu_sk IS NULL OR c.category_sk IS NULL
    """,
    "SKU价格事件衔接": """
        SELECT COUNT(*) FROM (
            SELECT previous_list_price,
                   previous_sale_price,
                   previous_cost_price,
                   LAG(new_list_price) OVER (
                       PARTITION BY sku_id ORDER BY price_effective_time
                   ) last_list_price,
                   LAG(new_sale_price) OVER (
                       PARTITION BY sku_id ORDER BY price_effective_time
                   ) last_sale_price,
                   LAG(new_cost_price) OVER (
                       PARTITION BY sku_id ORDER BY price_effective_time
                   ) last_cost_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY sku_id ORDER BY price_effective_time
                   ) row_no
            FROM dwd_product_sku_price_change_di
        ) x
        WHERE (row_no = 1 AND (
                   previous_list_price IS NOT NULL
                OR previous_sale_price IS NOT NULL
                OR previous_cost_price IS NOT NULL
              ))
           OR (row_no > 1 AND (
                   NOT (previous_list_price <=> last_list_price)
                OR NOT (previous_sale_price <=> last_sale_price)
                OR NOT (previous_cost_price <=> last_cost_price)
              ))
    """,
    "退款不超过实付": """
        SELECT COUNT(*) FROM (
            SELECT p.order_detail_id,
                   SUM(p.allocated_pay_amount) paid_amount,
                   COALESCE(r.refund_amount, 0) refund_amount
            FROM dwd_trade_pay_order_detail_di p
            LEFT JOIN (
                SELECT rp.order_detail_id, SUM(rp.refund_amount) refund_amount
                FROM dwd_trade_refund_pay_detail_di rp
                WHERE EXISTS (
                    SELECT 1 FROM dwd_trade_refund_pay_status_event_di s
                    WHERE s.refund_pay_detail_id = rp.refund_pay_detail_id
                      AND s.after_refund_pay_status = 'SUCCESS'
                )
                GROUP BY rp.order_detail_id
            ) r ON r.order_detail_id = p.order_detail_id
            GROUP BY p.order_detail_id, r.refund_amount
        ) x
        WHERE refund_amount > paid_amount
    """,
    "库存事件首尾衔接": """
        SELECT COUNT(*) FROM (
            SELECT before_on_hand_qty,
                   before_reserved_qty,
                   LAG(after_on_hand_qty) OVER (
                       PARTITION BY warehouse_id, sku_id
                       ORDER BY event_time, inventory_change_id
                   ) previous_on_hand,
                   LAG(after_reserved_qty) OVER (
                       PARTITION BY warehouse_id, sku_id
                       ORDER BY event_time, inventory_change_id
                   ) previous_reserved
            FROM dwd_inventory_change_di
        ) x
        WHERE previous_on_hand IS NOT NULL
          AND (before_on_hand_qty <> previous_on_hand
               OR before_reserved_qty <> previous_reserved)
    """,
    "库存期末快照": """
        SELECT COUNT(*)
        FROM dwd_inventory_daily_snapshot_df s
        JOIN (
            SELECT warehouse_id, sku_id, biz_date,
                   after_on_hand_qty last_on_hand,
                   after_reserved_qty last_reserved
            FROM (
                SELECT warehouse_id, sku_id, biz_date,
                       after_on_hand_qty, after_reserved_qty,
                       ROW_NUMBER() OVER (
                           PARTITION BY warehouse_id, sku_id, biz_date
                           ORDER BY event_time DESC, inventory_change_id DESC
                       ) row_no
                FROM dwd_inventory_change_di
            ) ranked
            WHERE row_no = 1
        ) e ON e.warehouse_id = s.warehouse_id
           AND e.sku_id = s.sku_id
           AND e.biz_date = s.biz_date
        WHERE s.on_hand_qty <> e.last_on_hand
           OR s.reserved_qty <> e.last_reserved
    """,
    "库存快照覆盖范围": """
        WITH expected AS (
            SELECT d.date_key snapshot_date_key,
                   b.warehouse_sk,
                   b.sku_sk
            FROM (
                SELECT warehouse_sk,
                       sku_sk,
                       MIN(biz_date) listing_date
                FROM dwd_inventory_change_di
                WHERE change_type = 'INITIAL_STOCK'
                GROUP BY warehouse_sk, sku_sk
            ) b
            JOIN dim_date d ON d.full_date >= b.listing_date
        )
        SELECT SUM(violations) FROM (
            SELECT COUNT(*) violations
            FROM expected e
            LEFT JOIN dwd_inventory_daily_snapshot_df s
              ON s.snapshot_date_key = e.snapshot_date_key
             AND s.warehouse_sk = e.warehouse_sk
             AND s.sku_sk = e.sku_sk
            WHERE s.sku_sk IS NULL
            UNION ALL
            SELECT COUNT(*)
            FROM dwd_inventory_daily_snapshot_df s
            LEFT JOIN expected e
              ON e.snapshot_date_key = s.snapshot_date_key
             AND e.warehouse_sk = s.warehouse_sk
             AND e.sku_sk = s.sku_sk
            WHERE e.sku_sk IS NULL
        ) q
    """,
    "会话事件汇总": """
        SELECT COUNT(*)
        FROM dwd_traffic_session_di s
        LEFT JOIN (
            SELECT session_id, COUNT(*) count_value
            FROM dwd_traffic_page_view_di GROUP BY session_id
        ) p ON p.session_id = s.session_id
        LEFT JOIN (
            SELECT session_id, COUNT(*) count_value
            FROM dwd_traffic_search_di GROUP BY session_id
        ) q ON q.session_id = s.session_id
        WHERE s.page_view_count <> COALESCE(p.count_value, 0)
           OR s.search_count <> COALESCE(q.count_value, 0)
    """,
    "订单行为链路": """
        SELECT COUNT(*)
        FROM dwd_trade_order_detail_di d
        LEFT JOIN dwd_traffic_session_di s
          ON s.session_id = d.source_session_id
         AND s.user_id = d.user_id
        LEFT JOIN dwd_interaction_cart_event_di c
          ON c.session_id = d.source_session_id
         AND c.user_id = d.user_id
         AND c.sku_id = d.sku_id
         AND c.cart_event_type = '加入'
         AND c.event_time <= d.order_create_time
        WHERE s.session_id IS NULL OR c.cart_event_id IS NULL
    """,
    "订单成本完整性": """
        SELECT COUNT(*)
        FROM dwd_trade_order_detail_di
        WHERE cost_amount IS NULL OR cost_amount <= 0
    """,
    "库存数量合法性": """
        SELECT SUM(violations) FROM (
            SELECT COUNT(*) violations
            FROM dwd_inventory_change_di
            WHERE after_on_hand_qty < 0
               OR after_reserved_qty < 0
               OR after_reserved_qty > after_on_hand_qty
            UNION ALL
            SELECT COUNT(*)
            FROM dwd_inventory_daily_snapshot_df
            WHERE on_hand_qty < 0
               OR reserved_qty < 0
               OR available_qty <> on_hand_qty - reserved_qty
        ) q
    """,
}

SCD_TABLES: dict[str, tuple[str, ...]] = {
    "dim_geo_region_zip": ("region_code",),
    "dim_user_info_zip": ("user_id",),
    "dim_seller_info_zip": ("seller_id",),
    "dim_shop_info_zip": ("shop_id",),
    "dim_category_info_zip": ("category_id",),
    "dim_warehouse_info_zip": ("warehouse_id",),
    "dim_spu_info_zip": ("spu_id",),
    "dim_sku_info_zip": ("sku_id",),
    "bridge_user_tag_relation_zip": ("user_id", "user_tag_sk"),
}

UNKNOWN_MEMBER_TABLES = (
    "dim_channel_info",
    "dim_page_info",
    "dim_geo_region_zip",
    "dim_user_info_zip",
    "dim_user_tag_info",
    "dim_seller_info_zip",
    "dim_shop_info_zip",
    "dim_category_info_zip",
    "dim_brand_info",
    "dim_payment_type",
    "dim_logistics_company",
    "dim_warehouse_info_zip",
    "dim_spu_info_zip",
    "dim_sku_info_zip",
    "dim_promotion_rule_version",
    "dim_coupon_template_version",
)

OPTIONAL_EMPTY_TABLES = {
    "dwd_product_shop_score_daily_snapshot_df",
}

SMOKE_OPTIONAL_EMPTY_TABLES = {
    "dwd_service_comment_detail_di",
    "dwd_trade_refund_detail_di",
    "dwd_trade_refund_pay_detail_di",
    "dwd_trade_refund_pay_status_event_di",
    "dwd_trade_refund_status_event_di",
}

FACT_TIME_COLUMNS = {
    "dwd_interaction_cart_event_di": "event_time",
    "dwd_interaction_favor_event_di": "event_time",
    "dwd_inventory_change_di": "event_time",
    "dwd_inventory_daily_snapshot_df": "snapshot_time",
    "dwd_marketing_user_coupon_event_di": "event_time",
    "dwd_product_shop_score_daily_snapshot_df": "snapshot_time",
    "dwd_product_sku_price_change_di": "price_effective_time",
    "dwd_service_comment_detail_di": "comment_time",
    "dwd_trade_delivery_di": "delivery_create_time",
    "dwd_trade_delivery_item_di": "delivery_create_time",
    "dwd_trade_delivery_status_event_di": "event_time",
    "dwd_trade_order_detail_activity_di": "order_create_time",
    "dwd_trade_order_detail_coupon_di": "coupon_use_time",
    "dwd_trade_order_detail_di": "order_create_time",
    "dwd_trade_order_status_event_di": "event_time",
    "dwd_trade_pay_detail_di": "pay_request_time",
    "dwd_trade_pay_order_detail_di": "pay_request_time",
    "dwd_trade_pay_status_event_di": "event_time",
    "dwd_trade_refund_detail_di": "apply_time",
    "dwd_trade_refund_pay_detail_di": "refund_pay_request_time",
    "dwd_trade_refund_pay_status_event_di": "event_time",
    "dwd_trade_refund_status_event_di": "event_time",
    "dwd_traffic_page_view_di": "event_time",
    "dwd_traffic_search_click_di": "event_time",
    "dwd_traffic_search_di": "event_time",
    "dwd_traffic_session_di": "session_end_time",
}


def validate_catalog_dimensions(ctx: RunContext) -> None:
    failures: list[str] = []
    selected_spu_ids = {
        int(row["spu_id"])
        for index, row in enumerate(iter_jsonl_rows(ctx.gen.data_dir / "spus.jsonl"))
        if index < ctx.gen.spu_count
    }
    expected_skus = sum(
        1
        for row in iter_jsonl_rows(ctx.gen.data_dir / "skus.jsonl")
        if int(row["spu_id"]) in selected_spu_ids
    )
    checks = {
        "SPU数量": (
            "SELECT COUNT(*) FROM dim_spu_info_zip WHERE spu_id <> 0 AND is_current = 1",
            ctx.gen.spu_count,
        ),
        "SKU数量": (
            "SELECT COUNT(*) FROM dim_sku_info_zip WHERE sku_id <> 0 AND is_current = 1",
            expected_skus,
        ),
        "SKU库存预警阈值": (
            """
            SELECT COUNT(*)
            FROM dim_sku_info_zip
            WHERE sku_id <> 0
              AND is_current = 1
              AND warning_stock_qty <= 0
            """,
            0,
        ),
        "没有SKU的SPU数量": (
            """
            SELECT COUNT(*) FROM (
                SELECT sp.spu_id
                FROM dim_spu_info_zip sp
                LEFT JOIN dim_sku_info_zip sk
                  ON sk.spu_id = sp.spu_id
                 AND sk.sku_id <> 0
                 AND sk.is_current = 1
                WHERE sp.spu_id <> 0 AND sp.is_current = 1
                GROUP BY sp.spu_id
                HAVING COUNT(sk.sku_id) = 0
            ) x
            """,
            0,
        ),
        "SPU维度引用": (
            """
            SELECT COUNT(*)
            FROM dim_spu_info_zip sp
            LEFT JOIN dim_shop_info_zip sh
              ON sh.shop_id = sp.shop_id AND sh.is_current = 1
            LEFT JOIN dim_category_info_zip c
              ON c.category_id = sp.category_id AND c.is_current = 1
            LEFT JOIN dim_brand_info b ON b.brand_id = sp.brand_id
            WHERE sp.spu_id <> 0 AND sp.is_current = 1
              AND (sh.shop_id IS NULL OR c.category_id IS NULL OR b.brand_id IS NULL)
            """,
            0,
        ),
        "SKU维度引用": (
            """
            SELECT COUNT(*)
            FROM dim_sku_info_zip sk
            LEFT JOIN dim_spu_info_zip sp
              ON sp.spu_id = sk.spu_id AND sp.is_current = 1
            LEFT JOIN dim_shop_info_zip sh
              ON sh.shop_id = sk.shop_id AND sh.is_current = 1
            LEFT JOIN dim_category_info_zip c
              ON c.category_id = sk.category_id AND c.is_current = 1
            LEFT JOIN dim_brand_info b ON b.brand_id = sk.brand_id
            WHERE sk.sku_id <> 0 AND sk.is_current = 1
              AND (sp.spu_id IS NULL OR sh.shop_id IS NULL
                   OR c.category_id IS NULL OR b.brand_id IS NULL)
            """,
            0,
        ),
    }
    with ctx.engine.connect() as conn:
        for name, (sql, expected) in checks.items():
            actual = int(conn.execute(text(sql)).scalar_one() or 0)
            if actual != expected:
                failures.append(f"{name}: expected={expected} actual={actual}")
    if failures:
        raise ValueError("商品维度校验失败\n" + "\n".join(failures))
    logger.info(
        "商品维度校验通过 spus=%s skus=%s",
        ctx.gen.spu_count,
        expected_skus,
    )


def validate_database(ctx: RunContext, tables: Mapping[str, Table]) -> None:
    failures: list[str] = []
    counts: dict[str, int] = {}
    earliest_load_time = None
    optional_empty_tables = OPTIONAL_EMPTY_TABLES | (
        SMOKE_OPTIONAL_EMPTY_TABLES if ctx.gen.is_smoke else set()
    )
    with ctx.engine.connect() as conn:
        for table_name in sorted(tables):
            table = tables[table_name]
            count = int(
                conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar_one()
            )
            counts[table_name] = count
            if count == 0 and table_name not in optional_empty_tables:
                failures.append(f"空表: {table_name}")
            if count == 0 or "dw_load_time" not in table.c:
                continue
            load_range = conn.execute(
                text(
                    f"SELECT MIN(dw_load_time), MAX(dw_load_time), "
                    f"SUM(dw_load_time > :as_of_time) FROM `{table_name}`"
                ),
                {"as_of_time": ctx.as_of_time},
            ).one()
            table_earliest = load_range[0]
            if table_earliest is not None and (
                earliest_load_time is None or table_earliest < earliest_load_time
            ):
                earliest_load_time = table_earliest
            if int(load_range[2] or 0):
                failures.append(f"{table_name} 存在晚于任务执行时刻的入仓时间")
            if "biz_date" in table.c:
                before_business_date = int(
                    conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM `{table_name}` "
                            "WHERE DATE(dw_load_time) < biz_date"
                        )
                    ).scalar_one()
                )
                if before_business_date:
                    failures.append(
                        f"{table_name} 入仓时间早于业务日期: "
                        f"{before_business_date} 条"
                    )
                batch_month_mismatch = int(
                    conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM `{table_name}` "
                            "WHERE RIGHT(load_batch_id, 7) "
                            "<> DATE_FORMAT(biz_date, '%Y-%m')"
                        )
                    ).scalar_one()
                )
                if batch_month_mismatch:
                    failures.append(
                        f"{table_name} 业务月份与装载批次不一致: "
                        f"{batch_month_mismatch} 条"
                    )
            fact_time_column = FACT_TIME_COLUMNS.get(table_name)
            if fact_time_column is not None:
                invalid_fact_time = conn.execute(
                    text(
                        f"SELECT SUM(`{fact_time_column}` > :as_of_time), "
                        f"SUM(dw_load_time < `{fact_time_column}`) "
                        f"FROM `{table_name}`"
                    ),
                    {"as_of_time": ctx.as_of_time},
                ).one()
                if int(invalid_fact_time[0] or 0):
                    failures.append(f"{table_name} 存在晚于任务执行时刻的业务时间")
                if int(invalid_fact_time[1] or 0):
                    failures.append(f"{table_name} 存在早于业务时间的入仓时间")
            if "source_update_time" in table.c:
                invalid_source_time = int(
                    conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM `{table_name}` "
                            "WHERE source_update_time IS NULL "
                            "OR source_update_time > dw_load_time"
                        )
                    ).scalar_one()
                )
                if invalid_source_time:
                    failures.append(
                        f"{table_name} 来源更新时间异常: {invalid_source_time} 条"
                    )
        for name, sql in CHECKS.items():
            violations = int(conn.execute(text(sql)).scalar_one() or 0)
            if violations:
                failures.append(f"{name}: {violations} 条")
        expected_periods = len(month_periods(ctx.gen.start_date, ctx.gen.end_date))
        checkpoint_status = CheckpointStore(ctx).run_status()
        if checkpoint_status.completed_periods != expected_periods:
            failures.append(
                "完成月份数量异常: "
                f"expected={expected_periods} "
                f"actual={checkpoint_status.completed_periods}"
            )
        if checkpoint_status.unfinished_periods:
            failures.append(
                f"存在未完成月份: {checkpoint_status.unfinished_periods} 个"
            )
        if checkpoint_status.last_period_end != ctx.gen.end_date:
            failures.append(
                f"最后完成日期异常: expected={ctx.gen.end_date} "
                f"actual={checkpoint_status.last_period_end}"
            )
        for table_name, business_keys in SCD_TABLES.items():
            partition = ", ".join(f"`{key}`" for key in business_keys)
            overlap_sql = f"""
                SELECT COUNT(*) FROM (
                    SELECT effective_start_time,
                           LAG(effective_end_time) OVER (
                               PARTITION BY {partition}
                               ORDER BY effective_start_time
                           ) previous_end
                    FROM `{table_name}`
                ) x
                WHERE previous_end > effective_start_time
            """
            overlaps = int(conn.execute(text(overlap_sql)).scalar_one() or 0)
            if overlaps:
                failures.append(f"{table_name} 拉链区间重叠: {overlaps} 条")
            current_sql = f"""
                SELECT COUNT(*) FROM (
                    SELECT {partition}
                    FROM `{table_name}`
                    GROUP BY {partition}
                    HAVING SUM(is_current) <> 1
                ) x
            """
            invalid_current = int(conn.execute(text(current_sql)).scalar_one() or 0)
            if invalid_current:
                failures.append(f"{table_name} 当前版本数量异常: {invalid_current} 条")
        for table_name in UNKNOWN_MEMBER_TABLES:
            unique_key_columns = doris_unique_key_columns(conn, table_name)
            if not unique_key_columns:
                failures.append(f"{table_name} 未定义Doris UNIQUE KEY")
                continue
            primary_key = unique_key_columns[0]
            unknown_count = int(
                conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM `{table_name}` "
                        f"WHERE `{primary_key}` = -1"
                    )
                ).scalar_one()
            )
            if unknown_count != 1:
                failures.append(f"{table_name} 未知成员数量: {unknown_count} 条")
    if (
        earliest_load_time is not None
        and ctx.gen.start_date < ctx.gen.end_date
        and earliest_load_time.date() >= ctx.as_of_time.date()
    ):
        failures.append("历史数据入仓时间全部集中在任务执行日期")
    if failures:
        raise ValueError("数据质量校验失败\n" + "\n".join(failures))
    logger.info(
        "数据质量校验通过 tables=%s rows=%s",
        len(counts),
        sum(counts.values()),
    )

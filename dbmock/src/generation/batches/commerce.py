"""生成订单、营销、支付、履约、退款、评价和库存事件"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import Table

from ..support import (
    MONEY_ZERO,
    UNKNOWN_ID,
    UNKNOWN_SK,
    TableWriter,
    build_version_index,
    date_key,
    fact_audit,
    load_rows,
    money,
    price,
    start_of_day,
    version_at,
)
from ...settings import RunContext

logger = logging.getLogger(__name__)

WEIGHT_QUANT = Decimal("0.001")


def _event_time(ctx: RunContext, index: int, total: int) -> datetime:
    start = start_of_day(ctx.gen.start_date) + timedelta(hours=1)
    end = ctx.data_end_time - timedelta(hours=4)
    seconds = max(1, int((end - start).total_seconds()))
    return start + timedelta(seconds=seconds * index // max(total, 1))


def _later(ctx: RunContext, value: datetime, delta: timedelta) -> datetime:
    return min(value + delta, ctx.data_end_time)


def _price_at(
    price_index: dict[int, list[dict[str, Any]]],
    sku_id: int,
    event_time: datetime,
) -> dict[str, Any]:
    events = price_index[sku_id]
    selected = events[0]
    for row in events:
        if row["price_effective_time"] <= event_time:
            selected = row
        else:
            break
    return selected


def _add_order_status(
    writer: TableWriter,
    ctx: RunContext,
    event_id: int,
    order_id: int,
    seq_no: int,
    user: dict[str, Any],
    shop: dict[str, Any],
    before: str | None,
    after: str,
    event_type: str,
    event_time: datetime,
    terminal: int,
) -> None:
    writer.add(
        "dwd_trade_order_status_event_di",
        {
            "order_status_event_id": event_id,
            "order_id": order_id,
            "event_seq_no": seq_no,
            "event_date_key": date_key(event_time),
            "user_sk": user["user_sk"],
            "user_id": user["user_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "before_order_status": before,
            "after_order_status": after,
            "status_event_type": event_type,
            "status_reason_code": None,
            "status_reason_description": None,
            "cancel_stage": "待支付" if after == "CANCELLED" else None,
            "is_terminal_status": terminal,
            "operator_id": str(user["user_id"]),
            "operator_type": "USER",
            "event_time": event_time,
            "biz_date": event_time.date(),
        }
        | fact_audit(f"order-status:{order_id}:{seq_no}", ctx.batch_id),
    )


def _add_pay_status(
    writer: TableWriter,
    ctx: RunContext,
    event_id: int,
    pay_detail_id: int,
    pay_order_no: str,
    seq_no: int,
    before: str | None,
    after: str,
    event_time: datetime,
) -> None:
    writer.add(
        "dwd_trade_pay_status_event_di",
        {
            "pay_status_event_id": event_id,
            "pay_detail_id": pay_detail_id,
            "pay_order_no": pay_order_no,
            "event_seq_no": seq_no,
            "event_date_key": date_key(event_time),
            "third_party_pay_no": f"TP{pay_detail_id}" if after == "SUCCESS" else None,
            "before_pay_status": before,
            "after_pay_status": after,
            "status_reason_code": None,
            "status_reason_description": None,
            "event_time": event_time,
            "biz_date": event_time.date(),
        }
        | fact_audit(f"pay-status:{pay_detail_id}:{seq_no}", ctx.batch_id),
    )


def _add_delivery_statuses(
    writer: TableWriter,
    ctx: RunContext,
    delivery_id: int,
    first_event_id: int,
    create_time: datetime,
    region_sk: int,
    region_code: str | None,
) -> int:
    statuses = (
        (None, "CREATED", "PACKAGE_CREATED", create_time),
        (
            "CREATED",
            "SHIPPED",
            "PACKAGE_SHIPPED",
            _later(ctx, create_time, timedelta(hours=6)),
        ),
        (
            "SHIPPED",
            "SIGNED",
            "PACKAGE_SIGNED",
            _later(ctx, create_time, timedelta(days=2)),
        ),
    )
    event_id = first_event_id
    for seq_no, (before, after, code, event_time) in enumerate(statuses, start=1):
        writer.add(
            "dwd_trade_delivery_status_event_di",
            {
                "delivery_status_event_id": event_id,
                "delivery_id": delivery_id,
                "event_seq_no": seq_no,
                "event_date_key": date_key(event_time),
                "before_delivery_status": before,
                "after_delivery_status": after,
                "status_event_code": code,
                "event_region_sk": region_sk,
                "event_region_code": region_code,
                "event_location": "模拟物流节点",
                "event_remark": None,
                "event_time": event_time,
                "biz_date": event_time.date(),
            }
            | fact_audit(f"delivery-status:{delivery_id}:{seq_no}", ctx.batch_id),
        )
        event_id += 1
    return event_id


def _add_refund_statuses(
    writer: TableWriter,
    ctx: RunContext,
    refund_detail_id: int,
    refund_no: str,
    first_event_id: int,
    apply_time: datetime,
    amount: Decimal,
) -> tuple[int, datetime]:
    approved_time = _later(ctx, apply_time, timedelta(hours=6))
    rows = (
        (None, "APPLIED", None, apply_time),
        ("APPLIED", "APPROVED", amount, approved_time),
    )
    event_id = first_event_id
    for seq_no, (before, after, delta, event_time) in enumerate(rows, start=1):
        writer.add(
            "dwd_trade_refund_status_event_di",
            {
                "refund_status_event_id": event_id,
                "refund_detail_id": refund_detail_id,
                "refund_no": refund_no,
                "event_seq_no": seq_no,
                "event_date_key": date_key(event_time),
                "before_refund_status": before,
                "after_refund_status": after,
                "approved_amount_delta": delta,
                "status_reason_code": None,
                "status_reason_description": None,
                "operator_id": "SYSTEM",
                "operator_type": "SYSTEM",
                "event_time": event_time,
                "biz_date": event_time.date(),
            }
            | fact_audit(f"refund-status:{refund_detail_id}:{seq_no}", ctx.batch_id),
        )
        event_id += 1
    return event_id, approved_time


def _add_refund_pay_statuses(
    writer: TableWriter,
    ctx: RunContext,
    refund_pay_detail_id: int,
    first_event_id: int,
    request_time: datetime,
) -> tuple[int, datetime]:
    success_time = _later(ctx, request_time, timedelta(minutes=10))
    rows = (
        (None, "REQUESTED", request_time),
        ("REQUESTED", "SUCCESS", success_time),
    )
    event_id = first_event_id
    for seq_no, (before, after, event_time) in enumerate(rows, start=1):
        writer.add(
            "dwd_trade_refund_pay_status_event_di",
            {
                "refund_pay_status_event_id": event_id,
                "refund_pay_detail_id": refund_pay_detail_id,
                "event_seq_no": seq_no,
                "event_date_key": date_key(event_time),
                "third_party_refund_no": f"TR{refund_pay_detail_id}"
                if after == "SUCCESS"
                else None,
                "before_refund_pay_status": before,
                "after_refund_pay_status": after,
                "status_reason_code": None,
                "status_reason_description": None,
                "event_time": event_time,
                "biz_date": event_time.date(),
            }
            | fact_audit(
                f"refund-pay-status:{refund_pay_detail_id}:{seq_no}",
                ctx.batch_id,
            ),
        )
        event_id += 1
    return event_id, success_time


def _inventory_rows(
    ctx: RunContext,
    pending: list[dict[str, Any]],
):
    pending.sort(
        key=lambda row: (
            row["warehouse_id"],
            row["sku_id"],
            row["event_time"],
            row["priority"],
        )
    )
    state: dict[tuple[int, int], tuple[int, int]] = defaultdict(lambda: (0, 0))
    for idx, event in enumerate(pending):
        key = (event["warehouse_id"], event["sku_id"])
        before_on_hand, before_reserved = state[key]
        after_on_hand = before_on_hand + event["on_hand_delta"]
        after_reserved = before_reserved + event["reserved_delta"]
        if after_on_hand < 0 or not 0 <= after_reserved <= after_on_hand:
            raise ValueError(f"库存状态非法: {key}, event={event}")
        state[key] = (after_on_hand, after_reserved)
        total_cost_delta = price(event["unit_cost"] * event["on_hand_delta"])
        event_id = 260_000_001 + idx
        yield {
            "inventory_change_id": event_id,
            "change_no": f"IC{event_id}",
            "event_date_key": date_key(event["event_time"]),
            "warehouse_sk": event["warehouse_sk"],
            "warehouse_id": event["warehouse_id"],
            "sku_sk": event["sku_sk"],
            "sku_id": event["sku_id"],
            "spu_sk": event["spu_sk"],
            "spu_id": event["spu_id"],
            "shop_sk": event["shop_sk"],
            "shop_id": event["shop_id"],
            "change_type": event["change_type"],
            "biz_type": event["biz_type"],
            "biz_id": str(event["biz_id"]),
            "before_on_hand_qty": before_on_hand,
            "on_hand_qty_delta": event["on_hand_delta"],
            "after_on_hand_qty": after_on_hand,
            "before_reserved_qty": before_reserved,
            "reserved_qty_delta": event["reserved_delta"],
            "after_reserved_qty": after_reserved,
            "unit_cost": event["unit_cost"],
            "total_cost_delta": total_cost_delta,
            "currency_code": "CNY",
            "operator_id": "SYSTEM",
            "operator_type": "SYSTEM",
            "remark": event["change_type"],
            "event_time": event["event_time"],
            "biz_date": event["event_time"].date(),
        } | fact_audit(f"inventory-change:{event_id}", ctx.batch_id)


def run(ctx: RunContext, tables: dict[str, Table]) -> None:
    with ctx.engine.connect() as conn:
        writer = TableWriter(
            ctx.loader,
            ctx.gen.batch_size,
            ctx.gen.start_date,
            ctx.as_of_time,
        )
        users = load_rows(
            conn,
            tables["dim_user_info_zip"],
            where=tables["dim_user_info_zip"].c.user_id != UNKNOWN_ID,
        )
        user_versions = build_version_index(users, "user_id")
        current_users = [row for row in users if row["is_current"] == 1]
        shops = load_rows(
            conn,
            tables["dim_shop_info_zip"],
            where=(tables["dim_shop_info_zip"].c.is_current == 1)
            & (tables["dim_shop_info_zip"].c.shop_id != UNKNOWN_ID),
        )
        shop_by_id = {row["shop_id"]: row for row in shops}
        sellers = load_rows(
            conn,
            tables["dim_seller_info_zip"],
            where=(tables["dim_seller_info_zip"].c.is_current == 1)
            & (tables["dim_seller_info_zip"].c.seller_id != UNKNOWN_ID),
        )
        seller_by_id = {row["seller_id"]: row for row in sellers}
        skus = load_rows(
            conn,
            tables["dim_sku_info_zip"],
            where=(tables["dim_sku_info_zip"].c.is_current == 1)
            & (tables["dim_sku_info_zip"].c.sku_id != UNKNOWN_ID),
        )
        sku_by_shop: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for sku in skus:
            sku_by_shop[sku["shop_id"]].append(sku)
        product_shops = [shop_by_id[shop_id] for shop_id in sku_by_shop]
        spus = load_rows(
            conn,
            tables["dim_spu_info_zip"],
            where=(tables["dim_spu_info_zip"].c.is_current == 1)
            & (tables["dim_spu_info_zip"].c.spu_id != UNKNOWN_ID),
        )
        spu_by_id = {row["spu_id"]: row for row in spus}
        categories = load_rows(
            conn,
            tables["dim_category_info_zip"],
            where=tables["dim_category_info_zip"].c.is_current == 1,
        )
        category_by_id = {row["category_id"]: row for row in categories}
        brands = load_rows(conn, tables["dim_brand_info"])
        brand_by_id = {row["brand_id"]: row for row in brands}
        channels = load_rows(
            conn,
            tables["dim_channel_info"],
            where=tables["dim_channel_info"].c.channel_code != "UNKNOWN",
        )
        payments = load_rows(
            conn,
            tables["dim_payment_type"],
            where=tables["dim_payment_type"].c.payment_type_code != "UNKNOWN",
        )
        logistics = load_rows(
            conn,
            tables["dim_logistics_company"],
            where=tables["dim_logistics_company"].c.logistics_company_id != UNKNOWN_ID,
        )
        warehouses = load_rows(
            conn,
            tables["dim_warehouse_info_zip"],
            where=(tables["dim_warehouse_info_zip"].c.is_current == 1)
            & (tables["dim_warehouse_info_zip"].c.warehouse_id != UNKNOWN_ID),
        )
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
        regions = load_rows(
            conn,
            tables["dim_geo_region_zip"],
            where=(tables["dim_geo_region_zip"].c.is_current == 1)
            & (tables["dim_geo_region_zip"].c.region_code != "UNKNOWN"),
        )
        region_by_district = {
            row["district_code"]: row
            for row in regions
            if row.get("district_code") is not None
        }
        price_events = load_rows(
            conn,
            tables["dwd_product_sku_price_change_di"],
            order_by=(
                tables["dwd_product_sku_price_change_di"].c.sku_id,
                tables["dwd_product_sku_price_change_di"].c.price_effective_time,
            ),
        )
        price_index: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in price_events:
            price_index[row["sku_id"]].append(row)

        warehouse_for_shop = {
            shop["shop_id"]: warehouses[idx % len(warehouses)]
            for idx, shop in enumerate(product_shops)
        }
        sku_context: dict[int, dict[str, Any]] = {}
        inventory_pending: list[dict[str, Any]] = []
        inventory_start = start_of_day(ctx.gen.start_date) + timedelta(seconds=30)
        for idx, sku in enumerate(skus):
            spu = spu_by_id[sku["spu_id"]]
            shop = shop_by_id[sku["shop_id"]]
            warehouse = warehouse_for_shop[shop["shop_id"]]
            initial_price = _price_at(price_index, sku["sku_id"], inventory_start)
            context = {
                "sku": sku,
                "spu": spu,
                "shop": shop,
                "warehouse": warehouse,
                "unit_cost": initial_price["new_cost_price"] or Decimal("0.0000"),
            }
            sku_context[sku["sku_id"]] = context
            inventory_pending.append(
                {
                    "warehouse_sk": warehouse["warehouse_sk"],
                    "warehouse_id": warehouse["warehouse_id"],
                    "sku_sk": sku["sku_sk"],
                    "sku_id": sku["sku_id"],
                    "spu_sk": spu["spu_sk"],
                    "spu_id": spu["spu_id"],
                    "shop_sk": shop["shop_sk"],
                    "shop_id": shop["shop_id"],
                    "change_type": "INITIAL_STOCK",
                    "biz_type": "INITIAL",
                    "biz_id": sku["sku_id"],
                    "on_hand_delta": 100_000,
                    "reserved_delta": 0,
                    "unit_cost": context["unit_cost"],
                    "event_time": inventory_start,
                    "priority": 0,
                }
            )

        detail_id = 100_000_001
        activity_id = 110_000_001
        coupon_alloc_id = 120_000_001
        coupon_event_id = 130_000_001
        user_coupon_id = 80_000_001
        pay_detail_id = 140_000_001
        pay_alloc_id = 150_000_001
        pay_status_id = 160_000_001
        delivery_id = 170_000_001
        delivery_item_id = 180_000_001
        delivery_status_id = 190_000_001
        refund_detail_id = 200_000_001
        refund_status_id = 210_000_001
        refund_pay_id = 220_000_001
        refund_pay_status_id = 230_000_001
        comment_id = 240_000_001
        order_status_id = 250_000_001
        order_index = 0
        created_details = 0
        first_order_users: set[int] = set()

        estimated_orders = max(1, ctx.gen.order_detail_count // 2)
        while created_details < ctx.gen.order_detail_count:
            order_id = 90_000_001 + order_index
            order_time = _event_time(ctx, order_index, estimated_orders)
            shop = product_shops[order_index % len(product_shops)]
            shop_skus = sku_by_shop[shop["shop_id"]]
            user_current = current_users[(order_index * 7) % len(current_users)]
            user = version_at(user_versions, user_current["user_id"], order_time)
            seller = seller_by_id.get(shop["seller_id"])
            channel = channels[order_index % len(channels)]
            region = region_by_district.get(user.get("district_code"))
            line_count = min(
                order_index % 3 + 1,
                ctx.gen.order_detail_count - created_details,
            )
            is_first_order = int(user["user_id"] not in first_order_users)
            first_order_users.add(user["user_id"])
            use_activity = order_index % 2 == 0
            use_coupon = order_index % 3 == 0 and order_index % 20 != 0
            promotion = promotions[order_index % len(promotions)]
            coupon = coupons[order_index % len(coupons)]
            order_details: list[dict[str, Any]] = []

            for line_idx in range(line_count):
                sku = shop_skus[(order_index + line_idx) % len(shop_skus)]
                spu = spu_by_id[sku["spu_id"]]
                category = category_by_id[sku["category_id"]]
                brand = brand_by_id.get(sku.get("brand_id"))
                price_event = _price_at(price_index, sku["sku_id"], order_time)
                qty = line_idx % 3 + 1
                list_unit = price(price_event["new_list_price"])
                sale_unit = price(price_event["new_sale_price"])
                list_amount = money(list_unit * qty)
                sale_amount = money(sale_unit * qty)
                activity_discount = (
                    money(min(sale_amount * Decimal("0.05"), Decimal("10")))
                    if use_activity
                    else MONEY_ZERO
                )
                coupon_discount = (
                    money(min(sale_amount * Decimal("0.03"), Decimal("5")))
                    if use_coupon
                    else MONEY_ZERO
                )
                freight = money("3.00") if order_index % 5 == 0 else MONEY_ZERO
                tax = (
                    money(sale_amount * Decimal("0.05"))
                    if shop["is_cross_border"]
                    else MONEY_ZERO
                )
                receivable = money(
                    sale_amount - activity_discount - coupon_discount + freight + tax
                )
                cost_amount = money((price_event["new_cost_price"] or 0) * qty)
                current_detail_id = detail_id
                row = {
                    "order_detail_id": current_detail_id,
                    "order_id": order_id,
                    "parent_order_id": None,
                    "trade_no": f"T{order_id}",
                    "order_no": f"O{order_id}",
                    "order_date_key": date_key(order_time),
                    "user_sk": user["user_sk"],
                    "user_id": user["user_id"],
                    "shop_sk": shop["shop_sk"],
                    "shop_id": shop["shop_id"],
                    "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                    "seller_id": seller["seller_id"] if seller else None,
                    "sku_sk": sku["sku_sk"],
                    "sku_id": sku["sku_id"],
                    "spu_sk": spu["spu_sk"],
                    "spu_id": spu["spu_id"],
                    "category_sk": category["category_sk"],
                    "category_id": category["category_id"],
                    "brand_sk": brand["brand_sk"] if brand else UNKNOWN_SK,
                    "brand_id": brand["brand_id"] if brand else None,
                    "receiver_region_sk": region["region_sk"] if region else UNKNOWN_SK,
                    "receiver_region_code": user.get("district_code"),
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "order_source": channel["platform_type"],
                    "order_scene": "普通",
                    "is_first_order": is_first_order,
                    "is_cross_border": shop["is_cross_border"],
                    "is_presale": int(spu["is_presale"] or 0),
                    "is_gift": 0,
                    "is_risk_order": int(order_index % 97 == 0),
                    "sku_qty": qty,
                    "sku_list_unit_price": list_unit,
                    "sku_sale_unit_price": sale_unit,
                    "list_amount": list_amount,
                    "sale_amount": sale_amount,
                    "activity_discount_amount": activity_discount,
                    "coupon_discount_amount": coupon_discount,
                    "points_discount_amount": MONEY_ZERO,
                    "freight_amount": freight,
                    "tax_amount": tax,
                    "receivable_amount": receivable,
                    "cost_amount": cost_amount,
                    "currency_code": "CNY",
                    "order_create_time": order_time,
                    "biz_date": order_time.date(),
                } | fact_audit(f"order-detail:{current_detail_id}", ctx.batch_id)
                writer.add("dwd_trade_order_detail_di", row)
                detail = row | {
                    "sku": sku,
                    "spu": spu,
                    "category": category,
                    "brand": brand,
                    "price_event": price_event,
                }
                order_details.append(detail)
                if activity_discount > 0:
                    writer.add(
                        "dwd_trade_order_detail_activity_di",
                        {
                            "order_detail_activity_id": activity_id,
                            "order_detail_id": current_detail_id,
                            "order_id": order_id,
                            "promotion_version_sk": promotion["promotion_version_sk"],
                            "promotion_id": promotion["promotion_id"],
                            "promotion_discount_amount": activity_discount,
                            "rule_snapshot_json": {
                                "promotion_type": promotion["promotion_type"],
                                "rule_version_no": promotion["rule_version_no"],
                            },
                            "currency_code": "CNY",
                            "order_create_time": order_time,
                            "biz_date": order_time.date(),
                        }
                        | fact_audit(f"order-activity:{activity_id}", ctx.batch_id),
                    )
                    activity_id += 1
                detail_id += 1
                created_details += 1

            if use_coupon:
                receive_time = max(
                    start_of_day(ctx.gen.start_date), order_time - timedelta(hours=12)
                )
                writer.add(
                    "dwd_marketing_user_coupon_event_di",
                    {
                        "user_coupon_event_id": coupon_event_id,
                        "user_coupon_id": user_coupon_id,
                        "event_seq_no": 1,
                        "event_date_key": date_key(receive_time),
                        "coupon_template_version_sk": coupon[
                            "coupon_template_version_sk"
                        ],
                        "coupon_template_id": coupon["coupon_template_id"],
                        "user_sk": version_at(
                            user_versions, user["user_id"], receive_time
                        )["user_sk"],
                        "user_id": user["user_id"],
                        "before_coupon_status": None,
                        "after_coupon_status": "RECEIVED",
                        "coupon_event_type": "领取",
                        "related_order_id": None,
                        "coupon_batch_no": "MOCK-BATCH",
                        "event_time": receive_time,
                        "biz_date": receive_time.date(),
                    }
                    | fact_audit(f"coupon-event:{user_coupon_id}:1", ctx.batch_id),
                )
                coupon_event_id += 1
                writer.add(
                    "dwd_marketing_user_coupon_event_di",
                    {
                        "user_coupon_event_id": coupon_event_id,
                        "user_coupon_id": user_coupon_id,
                        "event_seq_no": 2,
                        "event_date_key": date_key(order_time),
                        "coupon_template_version_sk": coupon[
                            "coupon_template_version_sk"
                        ],
                        "coupon_template_id": coupon["coupon_template_id"],
                        "user_sk": user["user_sk"],
                        "user_id": user["user_id"],
                        "before_coupon_status": "RECEIVED",
                        "after_coupon_status": "USED",
                        "coupon_event_type": "使用",
                        "related_order_id": order_id,
                        "coupon_batch_no": "MOCK-BATCH",
                        "event_time": order_time,
                        "biz_date": order_time.date(),
                    }
                    | fact_audit(f"coupon-event:{user_coupon_id}:2", ctx.batch_id),
                )
                coupon_event_id += 1
                for detail in order_details:
                    if detail["coupon_discount_amount"] <= 0:
                        continue
                    writer.add(
                        "dwd_trade_order_detail_coupon_di",
                        {
                            "order_detail_coupon_id": coupon_alloc_id,
                            "order_detail_id": detail["order_detail_id"],
                            "order_id": order_id,
                            "coupon_template_version_sk": coupon[
                                "coupon_template_version_sk"
                            ],
                            "coupon_template_id": coupon["coupon_template_id"],
                            "user_coupon_id": user_coupon_id,
                            "user_sk": user["user_sk"],
                            "user_id": user["user_id"],
                            "coupon_discount_amount": detail["coupon_discount_amount"],
                            "coupon_batch_no": "MOCK-BATCH",
                            "coupon_receive_time": receive_time,
                            "coupon_use_time": order_time,
                            "currency_code": "CNY",
                            "order_create_time": order_time,
                            "biz_date": order_time.date(),
                        }
                        | fact_audit(f"order-coupon:{coupon_alloc_id}", ctx.batch_id),
                    )
                    coupon_alloc_id += 1
                user_coupon_id += 1

            _add_order_status(
                writer,
                ctx,
                order_status_id,
                order_id,
                1,
                user,
                shop,
                None,
                "CREATED",
                "CREATE",
                order_time,
                0,
            )
            order_status_id += 1
            is_paid = order_index % 20 != 0
            pay_time = _later(ctx, order_time, timedelta(minutes=5))
            close_time = _later(ctx, order_time, timedelta(hours=1))

            for detail in order_details:
                context = sku_context[detail["sku_id"]]
                inventory_pending.append(
                    {
                        "warehouse_sk": context["warehouse"]["warehouse_sk"],
                        "warehouse_id": context["warehouse"]["warehouse_id"],
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "spu_sk": detail["spu_sk"],
                        "spu_id": detail["spu_id"],
                        "shop_sk": detail["shop_sk"],
                        "shop_id": detail["shop_id"],
                        "change_type": "ORDER_RESERVED",
                        "biz_type": "ORDER",
                        "biz_id": order_id,
                        "on_hand_delta": 0,
                        "reserved_delta": detail["sku_qty"],
                        "unit_cost": context["unit_cost"],
                        "event_time": order_time,
                        "priority": 1,
                    }
                )

            if not is_paid:
                _add_order_status(
                    writer,
                    ctx,
                    order_status_id,
                    order_id,
                    2,
                    version_at(user_versions, user["user_id"], close_time),
                    shop,
                    "CREATED",
                    "CANCELLED",
                    "CANCEL",
                    close_time,
                    1,
                )
                order_status_id += 1
                for detail in order_details:
                    context = sku_context[detail["sku_id"]]
                    inventory_pending.append(
                        {
                            "warehouse_sk": context["warehouse"]["warehouse_sk"],
                            "warehouse_id": context["warehouse"]["warehouse_id"],
                            "sku_sk": detail["sku_sk"],
                            "sku_id": detail["sku_id"],
                            "spu_sk": detail["spu_sk"],
                            "spu_id": detail["spu_id"],
                            "shop_sk": detail["shop_sk"],
                            "shop_id": detail["shop_id"],
                            "change_type": "ORDER_RELEASED",
                            "biz_type": "CANCEL",
                            "biz_id": order_id,
                            "on_hand_delta": 0,
                            "reserved_delta": -detail["sku_qty"],
                            "unit_cost": context["unit_cost"],
                            "event_time": close_time,
                            "priority": 3,
                        }
                    )
                order_index += 1
                continue

            payment = payments[order_index % len(payments)]
            requested_amount = money(
                sum(detail["receivable_amount"] for detail in order_details)
            )
            pay_order_no = f"P{pay_detail_id}"
            fee_rate = Decimal("0.006") if payment["is_online"] else Decimal("0")
            fee = money(requested_amount * fee_rate)
            writer.add(
                "dwd_trade_pay_detail_di",
                {
                    "pay_detail_id": pay_detail_id,
                    "pay_order_no": pay_order_no,
                    "pay_attempt_no": 1,
                    "pay_date_key": date_key(pay_time),
                    "user_sk": version_at(user_versions, user["user_id"], pay_time)[
                        "user_sk"
                    ],
                    "user_id": user["user_id"],
                    "payment_type_sk": payment["payment_type_sk"],
                    "payment_type_code": payment["payment_type_code"],
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "pay_scene": "ORDER",
                    "requested_pay_amount": requested_amount,
                    "payment_fee_amount": fee,
                    "installment_count": 3 if payment["is_installment"] else None,
                    "currency_code": "CNY",
                    "pay_request_time": pay_time,
                    "biz_date": pay_time.date(),
                }
                | fact_audit(f"pay-detail:{pay_detail_id}", ctx.batch_id),
            )
            current_pay_detail_id = pay_detail_id
            for detail in order_details:
                writer.add(
                    "dwd_trade_pay_order_detail_di",
                    {
                        "pay_order_detail_id": pay_alloc_id,
                        "pay_detail_id": current_pay_detail_id,
                        "order_id": order_id,
                        "order_detail_id": detail["order_detail_id"],
                        "shop_sk": shop["shop_sk"],
                        "shop_id": shop["shop_id"],
                        "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                        "seller_id": seller["seller_id"] if seller else None,
                        "allocated_pay_amount": detail["receivable_amount"],
                        "currency_code": "CNY",
                        "pay_request_time": pay_time,
                        "biz_date": pay_time.date(),
                    }
                    | fact_audit(f"pay-allocation:{pay_alloc_id}", ctx.batch_id),
                )
                pay_alloc_id += 1
                context = sku_context[detail["sku_id"]]
                inventory_pending.append(
                    {
                        "warehouse_sk": context["warehouse"]["warehouse_sk"],
                        "warehouse_id": context["warehouse"]["warehouse_id"],
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "spu_sk": detail["spu_sk"],
                        "spu_id": detail["spu_id"],
                        "shop_sk": detail["shop_sk"],
                        "shop_id": detail["shop_id"],
                        "change_type": "ORDER_DEDUCTED",
                        "biz_type": "PAY",
                        "biz_id": current_pay_detail_id,
                        "on_hand_delta": -detail["sku_qty"],
                        "reserved_delta": -detail["sku_qty"],
                        "unit_cost": context["unit_cost"],
                        "event_time": pay_time,
                        "priority": 2,
                    }
                )
            _add_pay_status(
                writer,
                ctx,
                pay_status_id,
                current_pay_detail_id,
                pay_order_no,
                1,
                None,
                "REQUESTED",
                pay_time,
            )
            pay_status_id += 1
            pay_success_time = _later(ctx, pay_time, timedelta(minutes=1))
            _add_pay_status(
                writer,
                ctx,
                pay_status_id,
                current_pay_detail_id,
                pay_order_no,
                2,
                "REQUESTED",
                "SUCCESS",
                pay_success_time,
            )
            pay_status_id += 1
            pay_detail_id += 1

            _add_order_status(
                writer,
                ctx,
                order_status_id,
                order_id,
                2,
                version_at(user_versions, user["user_id"], pay_success_time),
                shop,
                "CREATED",
                "PAID",
                "PAY_SUCCESS",
                pay_success_time,
                0,
            )
            order_status_id += 1
            delivery_time = _later(ctx, pay_success_time, timedelta(hours=12))
            signed_time = _later(ctx, delivery_time, timedelta(days=2))
            _add_order_status(
                writer,
                ctx,
                order_status_id,
                order_id,
                3,
                version_at(user_versions, user["user_id"], delivery_time),
                shop,
                "PAID",
                "SHIPPED",
                "SHIP",
                delivery_time,
                0,
            )
            order_status_id += 1
            _add_order_status(
                writer,
                ctx,
                order_status_id,
                order_id,
                4,
                version_at(user_versions, user["user_id"], signed_time),
                shop,
                "SHIPPED",
                "SIGNED",
                "SIGN",
                signed_time,
                1,
            )
            order_status_id += 1

            warehouse = warehouse_for_shop[shop["shop_id"]]
            logistics_company = logistics[order_index % len(logistics)]
            package_weight = Decimal("0.000")
            package_freight = MONEY_ZERO
            item_weights: list[Decimal] = []
            for detail in order_details:
                weight = (
                    Decimal(detail["spu"].get("weight_kg") or 0) * detail["sku_qty"]
                ).quantize(WEIGHT_QUANT, rounding=ROUND_HALF_UP)
                item_weights.append(weight)
                package_weight += weight
                package_freight += detail["freight_amount"]
            current_delivery_id = delivery_id
            writer.add(
                "dwd_trade_delivery_di",
                {
                    "delivery_id": current_delivery_id,
                    "delivery_no": f"D{current_delivery_id}",
                    "package_no": f"PKG{current_delivery_id}",
                    "delivery_direction": "正向",
                    "delivery_date_key": date_key(delivery_time),
                    "order_id": order_id,
                    "refund_no": None,
                    "user_sk": version_at(
                        user_versions, user["user_id"], delivery_time
                    )["user_sk"],
                    "user_id": user["user_id"],
                    "shop_sk": shop["shop_sk"],
                    "shop_id": shop["shop_id"],
                    "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                    "seller_id": seller["seller_id"] if seller else None,
                    "warehouse_sk": warehouse["warehouse_sk"],
                    "warehouse_id": warehouse["warehouse_id"],
                    "logistics_company_sk": logistics_company["logistics_company_sk"],
                    "logistics_company_id": logistics_company["logistics_company_id"],
                    "receiver_region_sk": region["region_sk"] if region else UNKNOWN_SK,
                    "receiver_region_code": user.get("district_code"),
                    "tracking_no": f"TRK{current_delivery_id}",
                    "delivery_type": "快递",
                    "receiver_name": user["user_name"],
                    "receiver_phone": user["phone"],
                    "receiver_address": f"{user.get('province_code') or ''}{user.get('city_code') or ''}***",
                    "package_weight_kg": package_weight,
                    "package_freight_amount": package_freight,
                    "currency_code": "CNY",
                    "delivery_create_time": delivery_time,
                    "biz_date": delivery_time.date(),
                }
                | fact_audit(f"delivery:{current_delivery_id}", ctx.batch_id),
            )
            for detail, weight in zip(order_details, item_weights, strict=True):
                writer.add(
                    "dwd_trade_delivery_item_di",
                    {
                        "delivery_item_id": delivery_item_id,
                        "delivery_id": current_delivery_id,
                        "order_id": order_id,
                        "order_detail_id": detail["order_detail_id"],
                        "refund_detail_id": None,
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "spu_sk": detail["spu_sk"],
                        "spu_id": detail["spu_id"],
                        "category_sk": detail["category_sk"],
                        "category_id": detail["category_id"],
                        "delivery_sku_qty": detail["sku_qty"],
                        "allocated_weight_kg": weight,
                        "allocated_freight_amount": detail["freight_amount"],
                        "currency_code": "CNY",
                        "delivery_create_time": delivery_time,
                        "biz_date": delivery_time.date(),
                    }
                    | fact_audit(f"delivery-item:{delivery_item_id}", ctx.batch_id),
                )
                delivery_item_id += 1
            delivery_status_id = _add_delivery_statuses(
                writer,
                ctx,
                current_delivery_id,
                delivery_status_id,
                delivery_time,
                region["region_sk"] if region else UNKNOWN_SK,
                user.get("district_code"),
            )
            delivery_id += 1

            should_refund = order_index % 10 == 1
            if should_refund:
                detail = order_details[0]
                apply_time = _later(ctx, signed_time, timedelta(hours=8))
                goods_amount = money(
                    detail["sale_amount"]
                    - detail["activity_discount_amount"]
                    - detail["coupon_discount_amount"]
                    - detail["points_discount_amount"]
                )
                refund_amount = money(
                    goods_amount + detail["freight_amount"] + detail["tax_amount"]
                )
                refund_no = f"R{refund_detail_id}"
                current_refund_detail_id = refund_detail_id
                writer.add(
                    "dwd_trade_refund_detail_di",
                    {
                        "refund_detail_id": current_refund_detail_id,
                        "refund_no": refund_no,
                        "order_id": order_id,
                        "order_detail_id": detail["order_detail_id"],
                        "apply_date_key": date_key(apply_time),
                        "user_sk": version_at(
                            user_versions, user["user_id"], apply_time
                        )["user_sk"],
                        "user_id": user["user_id"],
                        "shop_sk": shop["shop_sk"],
                        "shop_id": shop["shop_id"],
                        "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                        "seller_id": seller["seller_id"] if seller else None,
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "refund_sku_qty": detail["sku_qty"],
                        "refund_type": "退货退款",
                        "refund_reason_code": "NO_REASON",
                        "refund_reason_description": "七天无理由",
                        "is_quality_issue": 0,
                        "need_return_goods": 1,
                        "apply_goods_amount": goods_amount,
                        "apply_freight_amount": detail["freight_amount"],
                        "apply_tax_amount": detail["tax_amount"],
                        "refund_apply_amount": refund_amount,
                        "currency_code": "CNY",
                        "apply_time": apply_time,
                        "biz_date": apply_time.date(),
                    }
                    | fact_audit(
                        f"refund-detail:{current_refund_detail_id}", ctx.batch_id
                    ),
                )
                refund_status_id, approved_time = _add_refund_statuses(
                    writer,
                    ctx,
                    current_refund_detail_id,
                    refund_no,
                    refund_status_id,
                    apply_time,
                    refund_amount,
                )
                refund_request_time = _later(ctx, approved_time, timedelta(minutes=5))
                current_refund_pay_id = refund_pay_id
                writer.add(
                    "dwd_trade_refund_pay_detail_di",
                    {
                        "refund_pay_detail_id": current_refund_pay_id,
                        "refund_no": refund_no,
                        "refund_detail_id": current_refund_detail_id,
                        "refund_pay_attempt_no": 1,
                        "original_pay_detail_id": current_pay_detail_id,
                        "order_id": order_id,
                        "order_detail_id": detail["order_detail_id"],
                        "request_date_key": date_key(refund_request_time),
                        "user_sk": version_at(
                            user_versions, user["user_id"], refund_request_time
                        )["user_sk"],
                        "user_id": user["user_id"],
                        "payment_type_sk": payment["payment_type_sk"],
                        "payment_type_code": payment["payment_type_code"],
                        "channel_sk": channel["channel_sk"],
                        "channel_code": channel["channel_code"],
                        "refund_goods_amount": goods_amount,
                        "refund_freight_amount": detail["freight_amount"],
                        "refund_tax_amount": detail["tax_amount"],
                        "refund_amount": refund_amount,
                        "refund_account_type": "原路退回",
                        "currency_code": "CNY",
                        "refund_pay_request_time": refund_request_time,
                        "biz_date": refund_request_time.date(),
                    }
                    | fact_audit(f"refund-pay:{current_refund_pay_id}", ctx.batch_id),
                )
                refund_pay_status_id, refund_success_time = _add_refund_pay_statuses(
                    writer,
                    ctx,
                    current_refund_pay_id,
                    refund_pay_status_id,
                    refund_request_time,
                )
                context = sku_context[detail["sku_id"]]
                inventory_pending.append(
                    {
                        "warehouse_sk": context["warehouse"]["warehouse_sk"],
                        "warehouse_id": context["warehouse"]["warehouse_id"],
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "spu_sk": detail["spu_sk"],
                        "spu_id": detail["spu_id"],
                        "shop_sk": detail["shop_sk"],
                        "shop_id": detail["shop_id"],
                        "change_type": "REFUND_RETURNED",
                        "biz_type": "REFUND",
                        "biz_id": current_refund_detail_id,
                        "on_hand_delta": detail["sku_qty"],
                        "reserved_delta": 0,
                        "unit_cost": context["unit_cost"],
                        "event_time": refund_success_time,
                        "priority": 4,
                    }
                )
                reverse_delivery_time = approved_time
                reverse_delivery_id = delivery_id
                reverse_weight = item_weights[0]
                warehouse_region = region_by_district.get(
                    warehouse.get("district_code")
                )
                writer.add(
                    "dwd_trade_delivery_di",
                    {
                        "delivery_id": reverse_delivery_id,
                        "delivery_no": f"D{reverse_delivery_id}",
                        "package_no": f"PKG{reverse_delivery_id}",
                        "delivery_direction": "逆向",
                        "delivery_date_key": date_key(reverse_delivery_time),
                        "order_id": order_id,
                        "refund_no": refund_no,
                        "user_sk": version_at(
                            user_versions, user["user_id"], reverse_delivery_time
                        )["user_sk"],
                        "user_id": user["user_id"],
                        "shop_sk": shop["shop_sk"],
                        "shop_id": shop["shop_id"],
                        "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                        "seller_id": seller["seller_id"] if seller else None,
                        "warehouse_sk": warehouse["warehouse_sk"],
                        "warehouse_id": warehouse["warehouse_id"],
                        "logistics_company_sk": logistics_company[
                            "logistics_company_sk"
                        ],
                        "logistics_company_id": logistics_company[
                            "logistics_company_id"
                        ],
                        "receiver_region_sk": warehouse_region["region_sk"]
                        if warehouse_region
                        else UNKNOWN_SK,
                        "receiver_region_code": warehouse.get("district_code"),
                        "tracking_no": f"TRK{reverse_delivery_id}",
                        "delivery_type": "退货快递",
                        "receiver_name": warehouse["warehouse_name"],
                        "receiver_phone": None,
                        "receiver_address": warehouse["address"],
                        "package_weight_kg": reverse_weight,
                        "package_freight_amount": MONEY_ZERO,
                        "currency_code": "CNY",
                        "delivery_create_time": reverse_delivery_time,
                        "biz_date": reverse_delivery_time.date(),
                    }
                    | fact_audit(f"delivery:{reverse_delivery_id}", ctx.batch_id),
                )
                writer.add(
                    "dwd_trade_delivery_item_di",
                    {
                        "delivery_item_id": delivery_item_id,
                        "delivery_id": reverse_delivery_id,
                        "order_id": order_id,
                        "order_detail_id": detail["order_detail_id"],
                        "refund_detail_id": current_refund_detail_id,
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "spu_sk": detail["spu_sk"],
                        "spu_id": detail["spu_id"],
                        "category_sk": detail["category_sk"],
                        "category_id": detail["category_id"],
                        "delivery_sku_qty": detail["sku_qty"],
                        "allocated_weight_kg": reverse_weight,
                        "allocated_freight_amount": MONEY_ZERO,
                        "currency_code": "CNY",
                        "delivery_create_time": reverse_delivery_time,
                        "biz_date": reverse_delivery_time.date(),
                    }
                    | fact_audit(f"delivery-item:{delivery_item_id}", ctx.batch_id),
                )
                delivery_item_id += 1
                delivery_status_id = _add_delivery_statuses(
                    writer,
                    ctx,
                    reverse_delivery_id,
                    delivery_status_id,
                    reverse_delivery_time,
                    warehouse_region["region_sk"] if warehouse_region else UNKNOWN_SK,
                    warehouse.get("district_code"),
                )
                delivery_id += 1
                refund_detail_id += 1
                refund_pay_id += 1

            if order_index % 4 == 0 and not should_refund:
                publish_time = _later(ctx, signed_time, timedelta(hours=12))
                detail = order_details[0]
                writer.add(
                    "dwd_service_comment_detail_di",
                    {
                        "comment_detail_id": comment_id,
                        "comment_id": comment_id,
                        "parent_comment_detail_id": None,
                        "comment_type": "初评",
                        "comment_date_key": date_key(publish_time),
                        "order_id": order_id,
                        "order_detail_id": detail["order_detail_id"],
                        "user_sk": version_at(
                            user_versions, user["user_id"], publish_time
                        )["user_sk"],
                        "user_id": user["user_id"],
                        "shop_sk": shop["shop_sk"],
                        "shop_id": shop["shop_id"],
                        "sku_sk": detail["sku_sk"],
                        "sku_id": detail["sku_id"],
                        "spu_sk": detail["spu_sk"],
                        "spu_id": detail["spu_id"],
                        "category_sk": detail["category_sk"],
                        "category_id": detail["category_id"],
                        "comment_level": order_index % 3 + 3,
                        "is_anonymous": int(order_index % 2 == 0),
                        "image_count": order_index % 4,
                        "video_count": int(order_index % 9 == 0),
                        "comment_content": "商品符合预期，物流体验良好",
                        "service_score": 5,
                        "logistics_score": 5,
                        "description_score": 5,
                        "sensitive_tag": None,
                        "sentiment": "正向",
                        "comment_time": publish_time,
                        "biz_date": publish_time.date(),
                    }
                    | fact_audit(f"comment:{comment_id}", ctx.batch_id),
                )
                comment_id += 1

            order_index += 1

        writer.add_many(
            "dwd_inventory_change_di",
            _inventory_rows(ctx, inventory_pending),
        )
        counts = writer.flush_all()
    logger.info("交易主链生成完成 %s", counts)

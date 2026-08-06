"""由转化会话生成订单并推进履约和库存状态"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..reference import ProductProfile, ReferenceData
from ..settings import RunContext
from ..support import (
    MONEY_ZERO,
    UNKNOWN_SK,
    TableWriter,
    date_key,
    end_of_day,
    fact_audit,
    money,
    price,
    start_of_day,
    version_at,
)
from ..timeline import (
    BusinessState,
    ConversionIntent,
    InventoryPosition,
    ScheduledFact,
)

WEIGHT_QUANT = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class OrderLinePlan:
    profile: ProductProfile
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderPlan:
    intent: ConversionIntent
    lines: tuple[OrderLinePlan, ...]


def _emit_due_facts(
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
) -> None:
    due: list[ScheduledFact] = []
    future: list[ScheduledFact] = []
    for fact in state.pending_facts:
        if fact.event_time <= cutoff:
            due.append(fact)
        else:
            future.append(fact)
    state.pending_facts = future
    for fact in sorted(
        due,
        key=lambda item: (
            item.event_time,
            item.table_name,
            item.source_record_id,
        ),
    ):
        _emit_fact(writer, batch_id, fact)


def _schedule_fact(
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    table_name: str,
    source_record_id: str,
    event_time: datetime,
    row: dict[str, Any],
) -> None:
    fact = ScheduledFact(
        table_name=table_name,
        source_record_id=source_record_id,
        event_time=event_time,
        row=row,
    )
    if event_time <= cutoff:
        _emit_fact(writer, batch_id, fact)
    else:
        state.pending_facts.append(fact)


def _emit_fact(
    writer: TableWriter,
    batch_id: str,
    fact: ScheduledFact,
) -> None:
    writer.add(
        fact.table_name,
        fact.row | fact_audit(fact.source_record_id, batch_id),
    )


def generate_day(
    ctx: RunContext,
    refs: ReferenceData,
    state: BusinessState,
    writer: TableWriter,
    day: date,
    batch_id: str,
    intents: list[ConversionIntent],
) -> None:
    rng = random.Random(f"{ctx.gen.seed}:{day}:commerce")
    cutoff = min(end_of_day(day), ctx.data_end_time)
    _emit_due_facts(state, writer, cutoff, batch_id)
    plans = _build_order_plans(refs, day, intents, rng)
    inventory_events = _inventory_opening_events(refs, state, day)
    due_events, future_events = _take_due_inventory_events(
        state.pending_inventory_events,
        cutoff,
    )
    state.pending_inventory_events = future_events
    inventory_events.extend(due_events)
    inventory_events.extend(_replenishment_events(refs, state, day, plans, due_events))
    for order_index, plan in enumerate(plans, start=1):
        order_inventory_events = _write_order(
            ctx,
            refs,
            state,
            writer,
            day,
            cutoff,
            batch_id,
            order_index,
            plan,
            rng,
        )
        for event in order_inventory_events:
            if event["event_time"] <= cutoff:
                inventory_events.append(event)
            else:
                state.pending_inventory_events.append(event)

    _apply_inventory_events(
        refs,
        state,
        writer,
        inventory_events,
        batch_id,
    )


def _build_order_plans(
    refs: ReferenceData,
    day: date,
    intents: list[ConversionIntent],
    rng: random.Random,
) -> list[OrderPlan]:
    active_by_shop: dict[int, list[ProductProfile]] = defaultdict(list)
    for profile in refs.active_profiles(day):
        active_by_shop[int(profile.shop["shop_id"])].append(profile)
    plans: list[OrderPlan] = []
    for intent in intents:
        primary = refs.profile_by_sku[int(intent.primary_sku_id)]
        shop_profiles = active_by_shop[int(primary.shop["shop_id"])]
        if len(shop_profiles) < intent.line_count:
            eligible_shops = [
                profiles
                for profiles in active_by_shop.values()
                if len(profiles) >= intent.line_count
            ]
            if not eligible_shops:
                raise ValueError(
                    f"{day} 没有可承载 {intent.line_count} 个订单行的店铺"
                )
            shop_profiles = eligible_shops[
                int(intent.user["user_id"]) % len(eligible_shops)
            ]
            primary = shop_profiles[
                int(intent.primary_sku_id) % len(shop_profiles)
            ]
        lines = [OrderLinePlan(primary, 1 + rng.randrange(2))]
        used = {int(primary.sku["sku_id"])}
        while len(lines) < intent.line_count:
            candidate = shop_profiles[rng.randrange(len(shop_profiles))]
            sku_id = int(candidate.sku["sku_id"])
            if sku_id in used and len(shop_profiles) > len(used):
                continue
            used.add(sku_id)
            lines.append(OrderLinePlan(candidate, 1 + (len(lines) % 2)))
        plans.append(OrderPlan(intent, tuple(lines)))
    return plans


def _inventory_opening_events(
    refs: ReferenceData,
    state: BusinessState,
    day: date,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for profile in refs.profiles_by_listing_date.get(day, []):
        sku_id = int(profile.sku["sku_id"])
        if sku_id in state.inventory:
            continue
        state.inventory[sku_id] = InventoryPosition(
            on_hand=0,
            reserved=0,
            in_transit=0,
            unit_cost=profile.price_on(day).cost_price,
        )
        events.append(
            _inventory_event(
                profile,
                "INITIAL_STOCK",
                "PURCHASE_RECEIPT",
                f"OPENING-{sku_id}",
                profile.initial_stock_qty,
                0,
                profile.price_on(day).cost_price,
                start_of_day(day) + timedelta(minutes=30),
                10,
            )
        )
    return events


def _take_due_inventory_events(
    pending: list[dict[str, Any]],
    cutoff: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    due: list[dict[str, Any]] = []
    future: list[dict[str, Any]] = []
    for event in pending:
        if event["event_time"] <= cutoff:
            due.append(event)
        else:
            future.append(event)
    return due, future


def _replenishment_events(
    refs: ReferenceData,
    state: BusinessState,
    day: date,
    plans: list[OrderPlan],
    due_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    demand: dict[int, int] = defaultdict(int)
    for plan in plans:
        for line in plan.lines:
            demand[int(line.profile.sku["sku_id"])] += line.quantity
    due_delta: dict[int, int] = defaultdict(int)
    for event in due_events:
        due_delta[int(event["sku_id"])] += int(event["on_hand_delta"])
    events: list[dict[str, Any]] = []
    for sku_id, required in demand.items():
        profile = refs.profile_by_sku[sku_id]
        position = state.inventory[sku_id]
        projected_available = position.available + due_delta[sku_id]
        target = required + profile.warning_stock_qty
        if projected_available >= target:
            continue
        receipt = max(
            profile.initial_stock_qty,
            target * 2 - projected_available,
        )
        events.append(
            _inventory_event(
                profile,
                "PURCHASE_RECEIPT",
                "REPLENISHMENT",
                f"PO-{date_key(day)}-{sku_id}",
                receipt,
                0,
                profile.price_on(day).cost_price,
                start_of_day(day) + timedelta(minutes=40),
                20,
            )
        )
    return events


def _write_order(
    ctx: RunContext,
    refs: ReferenceData,
    state: BusinessState,
    writer: TableWriter,
    day: date,
    cutoff: datetime,
    batch_id: str,
    order_index: int,
    plan: OrderPlan,
    rng: random.Random,
) -> list[dict[str, Any]]:
    intent = plan.intent
    order_id = date_key(day) * 1_000_000 + order_index
    user = intent.user
    primary = plan.lines[0].profile
    shop = primary.shop
    seller = refs.sellers_by_id.get(int(shop["seller_id"]))
    line_amounts = [
        money(line.profile.price_on(day).sale_price * line.quantity)
        for line in plan.lines
    ]
    sale_total = sum(line_amounts, MONEY_ZERO)
    promotion = _eligible_promotion(
        refs,
        primary,
        intent.order_time,
        sale_total,
    )
    coupon = _eligible_coupon(
        refs,
        primary,
        intent.order_time,
        sale_total,
        rng,
    )
    activity_total = _rule_discount(promotion, sale_total)
    coupon_total = min(
        _rule_discount(coupon, sale_total - activity_total),
        sale_total - activity_total,
    )
    activity_allocations = _allocate_money(activity_total, line_amounts)
    coupon_allocations = _allocate_money(coupon_total, line_amounts)
    freight_total = MONEY_ZERO if sale_total >= Decimal("99") else money("8")
    freight_allocations = _allocate_money(freight_total, line_amounts)
    paid_success = rng.random() >= 0.045
    is_first_order = int(state.user_order_counts.get(int(user["user_id"]), 0) == 0)
    details: list[dict[str, Any]] = []
    inventory_events: list[dict[str, Any]] = []

    for line_index, line in enumerate(plan.lines, start=1):
        profile = line.profile
        detail_id = order_id * 10 + line_index
        point = profile.price_on(day)
        list_amount = money(point.list_price * line.quantity)
        sale_amount = line_amounts[line_index - 1]
        activity_discount = activity_allocations[line_index - 1]
        coupon_discount = coupon_allocations[line_index - 1]
        freight = freight_allocations[line_index - 1]
        tax = (
            money(sale_amount * Decimal("0.05"))
            if int(shop["is_cross_border"])
            else MONEY_ZERO
        )
        receivable = money(
            sale_amount - activity_discount - coupon_discount + freight + tax
        )
        row = {
            "order_detail_id": detail_id,
            "order_id": order_id,
            "parent_order_id": None,
            "trade_no": f"T{order_id}",
            "order_no": f"O{order_id}",
            "source_session_id": intent.session_id,
            "order_date_key": date_key(day),
            "user_sk": user["user_sk"],
            "user_id": user["user_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
            "seller_id": seller["seller_id"] if seller else None,
            "sku_sk": profile.sku["sku_sk"],
            "sku_id": profile.sku["sku_id"],
            "spu_sk": profile.spu["spu_sk"],
            "spu_id": profile.spu["spu_id"],
            "category_sk": profile.category["category_sk"],
            "category_id": profile.category["category_id"],
            "brand_sk": profile.brand["brand_sk"]
            if profile.brand
            else UNKNOWN_SK,
            "brand_id": profile.brand["brand_id"] if profile.brand else None,
            "receiver_region_sk": intent.region["region_sk"]
            if intent.region
            else UNKNOWN_SK,
            "receiver_region_code": intent.region["region_code"]
            if intent.region
            else None,
            "channel_sk": intent.channel["channel_sk"],
            "channel_code": intent.channel["channel_code"],
            "order_source": intent.channel["platform_type"],
            "order_scene": "普通",
            "is_first_order": is_first_order,
            "is_cross_border": shop["is_cross_border"],
            "is_presale": int(profile.spu["is_presale"] or 0),
            "is_gift": 0,
            "is_risk_order": int(rng.random() < 0.008),
            "sku_qty": line.quantity,
            "sku_list_unit_price": point.list_price,
            "sku_sale_unit_price": point.sale_price,
            "list_amount": list_amount,
            "sale_amount": sale_amount,
            "activity_discount_amount": activity_discount,
            "coupon_discount_amount": coupon_discount,
            "points_discount_amount": MONEY_ZERO,
            "freight_amount": freight,
            "tax_amount": tax,
            "receivable_amount": receivable,
            "cost_amount": money(point.cost_price * line.quantity),
            "currency_code": "CNY",
            "order_create_time": intent.order_time,
            "biz_date": day,
        } | fact_audit(f"order-detail:{detail_id}", batch_id)
        writer.add("dwd_trade_order_detail_di", row)
        details.append(row | {"profile": profile, "quantity": line.quantity})
        inventory_events.append(
            _inventory_event(
                profile,
                "SALE_RESERVE",
                "ORDER",
                order_id,
                0,
                line.quantity,
                point.cost_price,
                intent.order_time,
                40,
            )
        )
        if activity_discount and promotion is not None:
            writer.add(
                "dwd_trade_order_detail_activity_di",
                {
                    "order_detail_activity_id": detail_id,
                    "order_detail_id": detail_id,
                    "order_id": order_id,
                    "promotion_version_sk": promotion["promotion_version_sk"],
                    "promotion_id": promotion["promotion_id"],
                    "promotion_discount_amount": activity_discount,
                    "rule_snapshot_json": {
                        "promotion_type": promotion["promotion_type"],
                        "rule_version_no": promotion["rule_version_no"],
                    },
                    "currency_code": "CNY",
                    "order_create_time": intent.order_time,
                    "biz_date": day,
                }
                | fact_audit(f"order-activity:{detail_id}", batch_id),
            )
        if line_index > 1 or int(profile.sku["sku_id"]) != intent.primary_sku_id:
            cart_event_id = detail_id
            cart_time = max(
                start_of_day(day),
                intent.order_time - timedelta(seconds=20 - line_index),
            )
            writer.add(
                "dwd_interaction_cart_event_di",
                {
                    "cart_event_id": cart_event_id,
                    "event_no": f"CART{cart_event_id}",
                    "event_date_key": date_key(cart_time),
                    "user_sk": user["user_sk"],
                    "user_id": user["user_id"],
                    "device_id": f"USERDEV{user['user_id']}",
                    "session_id": intent.session_id,
                    "shop_sk": profile.shop["shop_sk"],
                    "shop_id": profile.shop["shop_id"],
                    "sku_sk": profile.sku["sku_sk"],
                    "sku_id": profile.sku["sku_id"],
                    "spu_sk": profile.spu["spu_sk"],
                    "spu_id": profile.spu["spu_id"],
                    "category_sk": profile.category["category_sk"],
                    "category_id": profile.category["category_id"],
                    "channel_sk": intent.channel["channel_sk"],
                    "channel_code": intent.channel["channel_code"],
                    "cart_event_type": "加入",
                    "cart_source": "商品详情页",
                    "sku_qty_delta": line.quantity,
                    "cart_sku_qty_after": line.quantity,
                    "sku_unit_price": point.sale_price,
                    "currency_code": "CNY",
                    "event_time": cart_time,
                    "biz_date": cart_time.date(),
                }
                | fact_audit(f"cart:{cart_event_id}", batch_id),
            )

    _write_order_status(
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        1,
        user,
        shop,
        None,
        "CREATED",
        "CREATE",
        intent.order_time,
        0,
    )
    pay_time = intent.order_time + timedelta(minutes=3)
    requested_amount = sum(
        (detail["receivable_amount"] for detail in details),
        MONEY_ZERO,
    )
    payment = refs.payments[order_index % len(refs.payments)]
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_pay_detail_di",
        f"pay-detail:{order_id}",
        pay_time,
        {
            "pay_detail_id": order_id,
            "pay_order_no": f"P{order_id}",
            "pay_attempt_no": 1,
            "pay_date_key": date_key(pay_time),
            "user_sk": user["user_sk"],
            "user_id": user["user_id"],
            "payment_type_sk": payment["payment_type_sk"],
            "payment_type_code": payment["payment_type_code"],
            "channel_sk": intent.channel["channel_sk"],
            "channel_code": intent.channel["channel_code"],
            "pay_scene": "订单支付",
            "requested_pay_amount": requested_amount,
            "payment_fee_amount": MONEY_ZERO,
            "installment_count": None,
            "currency_code": "CNY",
            "pay_request_time": pay_time,
            "biz_date": pay_time.date(),
        },
    )
    for detail in details:
        detail_id = int(detail["order_detail_id"])
        _schedule_fact(
            state,
            writer,
            cutoff,
            batch_id,
            "dwd_trade_pay_order_detail_di",
            f"pay-allocation:{detail_id}",
            pay_time,
            {
                "pay_order_detail_id": detail_id,
                "pay_detail_id": order_id,
                "order_id": order_id,
                "order_detail_id": detail_id,
                "shop_sk": shop["shop_sk"],
                "shop_id": shop["shop_id"],
                "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                "seller_id": seller["seller_id"] if seller else None,
                "allocated_pay_amount": detail["receivable_amount"],
                "currency_code": "CNY",
                "pay_request_time": pay_time,
                "biz_date": pay_time.date(),
            },
        )
    _write_pay_status(
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        1,
        None,
        "REQUESTED",
        pay_time,
    )
    pay_result_time = pay_time + timedelta(seconds=8)
    _write_pay_status(
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        2,
        "REQUESTED",
        "SUCCESS" if paid_success else "FAILED",
        pay_result_time,
    )

    if coupon is not None and coupon_total:
        _write_coupon_lifecycle(
            state,
            writer,
            cutoff,
            batch_id,
            order_id,
            user,
            coupon,
            details,
            coupon_allocations,
            intent.order_time,
            paid_success,
        )

    if not paid_success:
        cancel_time = pay_result_time + timedelta(minutes=1)
        _write_order_status(
            state,
            writer,
            cutoff,
            batch_id,
            order_id,
            2,
            user,
            shop,
            "CREATED",
            "CANCELLED",
            "PAYMENT_FAILED",
            cancel_time,
            1,
        )
        for detail in details:
            profile = detail["profile"]
            inventory_events.append(
                _inventory_event(
                    profile,
                    "SALE_RELEASE",
                    "ORDER_CANCEL",
                    order_id,
                    0,
                    -int(detail["quantity"]),
                    profile.price_on(day).cost_price,
                    cancel_time,
                    50,
                )
            )
        return inventory_events

    state.user_order_counts[int(user["user_id"])] = (
        state.user_order_counts.get(int(user["user_id"]), 0) + 1
    )
    _write_order_status(
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        2,
        user,
        shop,
        "CREATED",
        "PAID",
        "PAY_SUCCESS",
        pay_result_time,
        0,
    )
    delivery_create_time = pay_result_time + timedelta(
        hours=2 + rng.randrange(10),
    )
    ship_time = delivery_create_time + timedelta(
        hours=6 + rng.randrange(24),
    )
    signed_time = ship_time + timedelta(days=1 + rng.randrange(4))
    warehouse = _warehouse_for_shop(refs, int(shop["shop_id"]))
    logistics = refs.logistics[order_index % len(refs.logistics)]
    _write_forward_delivery(
        refs,
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        user,
        shop,
        seller,
        warehouse,
        logistics,
        details,
        delivery_create_time,
        ship_time,
        signed_time,
        intent.region,
    )
    _write_order_status(
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        3,
        user,
        shop,
        "PAID",
        "SHIPPED",
        "SHIP",
        ship_time,
        0,
    )
    _write_order_status(
        state,
        writer,
        cutoff,
        batch_id,
        order_id,
        4,
        user,
        shop,
        "SHIPPED",
        "COMPLETED",
        "SIGN",
        signed_time,
        1,
    )
    for detail in details:
        profile = detail["profile"]
        inventory_events.append(
            _inventory_event(
                profile,
                "SALE_SHIPMENT",
                "DELIVERY",
                order_id,
                -int(detail["quantity"]),
                -int(detail["quantity"]),
                profile.price_on(day).cost_price,
                ship_time,
                60,
            )
        )

    should_refund = rng.random() < 0.085
    if should_refund:
        refund_detail = details[0]
        return_goods = rng.random() < 0.62
        return_event = _write_refund(
            refs,
            state,
            writer,
            cutoff,
            batch_id,
            order_id,
            user,
            shop,
            seller,
            payment,
            intent.channel,
            warehouse,
            logistics,
            refund_detail,
            signed_time,
            return_goods,
            intent.region,
            rng,
        )
        if return_event is not None:
            inventory_events.append(return_event)
    elif rng.random() < 0.31:
        _write_comment(
            refs,
            state,
            writer,
            cutoff,
            batch_id,
            order_id,
            user,
            shop,
            details[0],
            signed_time,
            rng,
        )
    return inventory_events


def _write_coupon_lifecycle(
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    order_id: int,
    user: dict[str, Any],
    coupon: dict[str, Any],
    details: list[dict[str, Any]],
    allocations: list[Decimal],
    order_time: datetime,
    paid_success: bool,
) -> None:
    receive_time = max(
        start_of_day(order_time.date()),
        order_time - timedelta(hours=2),
    )
    statuses = [
        (1, None, "RECEIVED", "领取", None, receive_time),
        (2, "RECEIVED", "LOCKED", "锁定", order_id, order_time),
        (
            3,
            "LOCKED",
            "USED" if paid_success else "RELEASED",
            "使用" if paid_success else "释放",
            order_id,
            order_time + timedelta(minutes=4),
        ),
    ]
    for seq_no, before, after, event_type, related_order_id, event_time in statuses:
        event_id = order_id * 10 + seq_no
        _schedule_fact(
            state,
            writer,
            cutoff,
            batch_id,
            "dwd_marketing_user_coupon_event_di",
            f"coupon-event:{order_id}:{seq_no}",
            event_time,
            {
                "user_coupon_event_id": event_id,
                "user_coupon_id": order_id,
                "event_seq_no": seq_no,
                "event_date_key": date_key(event_time),
                "coupon_template_version_sk": coupon["coupon_template_version_sk"],
                "coupon_template_id": coupon["coupon_template_id"],
                "user_sk": user["user_sk"],
                "user_id": user["user_id"],
                "before_coupon_status": before,
                "after_coupon_status": after,
                "coupon_event_type": event_type,
                "related_order_id": related_order_id,
                "coupon_batch_no": f"CB{date_key(order_time)}",
                "event_time": event_time,
                "biz_date": event_time.date(),
            },
        )
    for detail, amount in zip(details, allocations, strict=True):
        if not amount:
            continue
        detail_id = int(detail["order_detail_id"])
        _schedule_fact(
            state,
            writer,
            cutoff,
            batch_id,
            "dwd_trade_order_detail_coupon_di",
            f"order-coupon:{detail_id}",
            order_time,
            {
                "order_detail_coupon_id": detail_id,
                "order_detail_id": detail_id,
                "order_id": order_id,
                "coupon_template_version_sk": coupon["coupon_template_version_sk"],
                "coupon_template_id": coupon["coupon_template_id"],
                "user_coupon_id": order_id,
                "user_sk": user["user_sk"],
                "user_id": user["user_id"],
                "coupon_discount_amount": amount,
                "coupon_batch_no": f"CB{date_key(order_time)}",
                "coupon_receive_time": receive_time,
                "coupon_use_time": order_time,
                "currency_code": "CNY",
                "order_create_time": order_time,
                "biz_date": order_time.date(),
            },
        )


def _write_forward_delivery(
    refs: ReferenceData,
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    order_id: int,
    user: dict[str, Any],
    shop: dict[str, Any],
    seller: dict[str, Any] | None,
    warehouse: dict[str, Any],
    logistics: dict[str, Any],
    details: list[dict[str, Any]],
    delivery_create_time: datetime,
    ship_time: datetime,
    signed_time: datetime,
    region: dict[str, Any] | None,
) -> None:
    weights = [_line_weight(detail) for detail in details]
    freight_total = sum(
        (detail["freight_amount"] for detail in details),
        MONEY_ZERO,
    )
    freight_allocations = _allocate_money(freight_total, weights)
    package_weight = sum(weights, Decimal("0.000"))
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_delivery_di",
        f"delivery:{order_id}",
        delivery_create_time,
        {
            "delivery_id": order_id,
            "delivery_no": f"D{order_id}",
            "package_no": f"PKG{order_id}",
            "delivery_direction": "正向",
            "delivery_date_key": date_key(delivery_create_time),
            "order_id": order_id,
            "refund_no": None,
            "user_sk": version_at(
                refs.user_versions,
                int(user["user_id"]),
                delivery_create_time,
            )["user_sk"],
            "user_id": user["user_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
            "seller_id": seller["seller_id"] if seller else None,
            "warehouse_sk": warehouse["warehouse_sk"],
            "warehouse_id": warehouse["warehouse_id"],
            "logistics_company_sk": logistics["logistics_company_sk"],
            "logistics_company_id": logistics["logistics_company_id"],
            "receiver_region_sk": region["region_sk"] if region else UNKNOWN_SK,
            "receiver_region_code": region["region_code"] if region else None,
            "tracking_no": f"TRK{order_id}",
            "delivery_type": "普通快递",
            "receiver_name": str(user["user_name"]),
            "receiver_phone": user.get("phone"),
            "receiver_address": "用户脱敏收货地址",
            "package_weight_kg": package_weight,
            "package_freight_amount": freight_total,
            "currency_code": "CNY",
            "delivery_create_time": delivery_create_time,
            "biz_date": delivery_create_time.date(),
        },
    )
    for index, (detail, weight, freight) in enumerate(
        zip(details, weights, freight_allocations, strict=True),
        start=1,
    ):
        delivery_item_id = order_id * 10 + index
        _schedule_fact(
            state,
            writer,
            cutoff,
            batch_id,
            "dwd_trade_delivery_item_di",
            f"delivery-item:{delivery_item_id}",
            delivery_create_time,
            {
                "delivery_item_id": delivery_item_id,
                "delivery_id": order_id,
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
                "allocated_freight_amount": freight,
                "currency_code": "CNY",
                "delivery_create_time": delivery_create_time,
                "biz_date": delivery_create_time.date(),
            },
        )
    statuses = (
        (1, None, "CREATED", "PACKAGE_CREATED", delivery_create_time),
        (2, "CREATED", "SHIPPED", "PACKAGE_SHIPPED", ship_time),
        (3, "SHIPPED", "SIGNED", "PACKAGE_SIGNED", signed_time),
    )
    for seq_no, before, after, code, event_time in statuses:
        _write_delivery_status(
            state,
            writer,
            cutoff,
            batch_id,
            order_id,
            seq_no,
            before,
            after,
            code,
            event_time,
            region,
        )


def _write_refund(
    refs: ReferenceData,
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    order_id: int,
    user: dict[str, Any],
    shop: dict[str, Any],
    seller: dict[str, Any] | None,
    payment: dict[str, Any],
    channel: dict[str, Any],
    warehouse: dict[str, Any],
    logistics: dict[str, Any],
    detail: dict[str, Any],
    signed_time: datetime,
    return_goods: bool,
    region: dict[str, Any] | None,
    rng: random.Random,
) -> dict[str, Any] | None:
    refund_detail_id = int(detail["order_detail_id"])
    refund_no = f"R{refund_detail_id}"
    apply_time = signed_time + timedelta(days=1 + rng.randrange(6))
    refund_amount = money(detail["receivable_amount"])
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_refund_detail_di",
        f"refund-detail:{refund_detail_id}",
        apply_time,
        {
            "refund_detail_id": refund_detail_id,
            "refund_no": refund_no,
            "order_id": order_id,
            "order_detail_id": detail["order_detail_id"],
            "apply_date_key": date_key(apply_time),
            "user_sk": version_at(
                refs.user_versions,
                int(user["user_id"]),
                apply_time,
            )["user_sk"],
            "user_id": user["user_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
            "seller_id": seller["seller_id"] if seller else None,
            "sku_sk": detail["sku_sk"],
            "sku_id": detail["sku_id"],
            "refund_sku_qty": detail["sku_qty"],
            "refund_type": "退货退款" if return_goods else "仅退款",
            "refund_reason_code": "NOT_EXPECTED",
            "refund_reason_description": "商品未达到预期",
            "is_quality_issue": 0,
            "need_return_goods": int(return_goods),
            "apply_goods_amount": refund_amount,
            "apply_freight_amount": MONEY_ZERO,
            "apply_tax_amount": MONEY_ZERO,
            "refund_apply_amount": refund_amount,
            "currency_code": "CNY",
            "apply_time": apply_time,
            "biz_date": apply_time.date(),
        },
    )
    approved_time = apply_time + timedelta(hours=6)
    for seq_no, before, after, delta, event_time in (
        (1, None, "APPLIED", None, apply_time),
        (2, "APPLIED", "APPROVED", refund_amount, approved_time),
    ):
        event_id = refund_detail_id * 10 + seq_no
        _schedule_fact(
            state,
            writer,
            cutoff,
            batch_id,
            "dwd_trade_refund_status_event_di",
            f"refund-status:{refund_detail_id}:{seq_no}",
            event_time,
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
            },
        )
    refund_pay_time = approved_time + timedelta(minutes=10)
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_refund_pay_detail_di",
        f"refund-pay:{refund_detail_id}",
        refund_pay_time,
        {
            "refund_pay_detail_id": refund_detail_id,
            "refund_no": refund_no,
            "refund_detail_id": refund_detail_id,
            "refund_pay_attempt_no": 1,
            "original_pay_detail_id": order_id,
            "order_id": order_id,
            "order_detail_id": detail["order_detail_id"],
            "request_date_key": date_key(refund_pay_time),
            "user_sk": version_at(
                refs.user_versions,
                int(user["user_id"]),
                refund_pay_time,
            )["user_sk"],
            "user_id": user["user_id"],
            "payment_type_sk": payment["payment_type_sk"],
            "payment_type_code": payment["payment_type_code"],
            "channel_sk": channel["channel_sk"],
            "channel_code": channel["channel_code"],
            "refund_goods_amount": refund_amount,
            "refund_freight_amount": MONEY_ZERO,
            "refund_tax_amount": MONEY_ZERO,
            "refund_amount": refund_amount,
            "refund_account_type": "原路退回",
            "currency_code": "CNY",
            "refund_pay_request_time": refund_pay_time,
            "biz_date": refund_pay_time.date(),
        },
    )
    for seq_no, before, after, event_time in (
        (1, None, "REQUESTED", refund_pay_time),
        (
            2,
            "REQUESTED",
            "SUCCESS",
            refund_pay_time + timedelta(seconds=10),
        ),
    ):
        event_id = refund_detail_id * 10 + seq_no
        _schedule_fact(
            state,
            writer,
            cutoff,
            batch_id,
            "dwd_trade_refund_pay_status_event_di",
            f"refund-pay-status:{refund_detail_id}:{seq_no}",
            event_time,
            {
                "refund_pay_status_event_id": event_id,
                "refund_pay_detail_id": refund_detail_id,
                "event_seq_no": seq_no,
                "event_date_key": date_key(event_time),
                "third_party_refund_no": f"TR{refund_detail_id}"
                if after == "SUCCESS"
                else None,
                "before_refund_pay_status": before,
                "after_refund_pay_status": after,
                "status_reason_code": None,
                "status_reason_description": None,
                "event_time": event_time,
                "biz_date": event_time.date(),
            },
        )
    if not return_goods:
        return None
    reverse_delivery_id = order_id + 500_000
    reverse_time = approved_time + timedelta(days=2)
    weight = _line_weight(detail)
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_delivery_di",
        f"delivery:{reverse_delivery_id}",
        reverse_time,
        {
            "delivery_id": reverse_delivery_id,
            "delivery_no": f"D{reverse_delivery_id}",
            "package_no": f"PKG{reverse_delivery_id}",
            "delivery_direction": "逆向",
            "delivery_date_key": date_key(reverse_time),
            "order_id": order_id,
            "refund_no": refund_no,
            "user_sk": version_at(
                refs.user_versions,
                int(user["user_id"]),
                reverse_time,
            )["user_sk"],
            "user_id": user["user_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
            "seller_id": seller["seller_id"] if seller else None,
            "warehouse_sk": warehouse["warehouse_sk"],
            "warehouse_id": warehouse["warehouse_id"],
            "logistics_company_sk": logistics["logistics_company_sk"],
            "logistics_company_id": logistics["logistics_company_id"],
            "receiver_region_sk": UNKNOWN_SK,
            "receiver_region_code": warehouse.get("district_code"),
            "tracking_no": f"TRK{reverse_delivery_id}",
            "delivery_type": "退货快递",
            "receiver_name": warehouse["warehouse_name"],
            "receiver_phone": None,
            "receiver_address": warehouse["address"],
            "package_weight_kg": weight,
            "package_freight_amount": MONEY_ZERO,
            "currency_code": "CNY",
            "delivery_create_time": reverse_time,
            "biz_date": reverse_time.date(),
        },
    )
    reverse_item_id = reverse_delivery_id * 10 + 1
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_delivery_item_di",
        f"delivery-item:{reverse_item_id}",
        reverse_time,
        {
            "delivery_item_id": reverse_item_id,
            "delivery_id": reverse_delivery_id,
            "order_id": order_id,
            "order_detail_id": detail["order_detail_id"],
            "refund_detail_id": refund_detail_id,
            "sku_sk": detail["sku_sk"],
            "sku_id": detail["sku_id"],
            "spu_sk": detail["spu_sk"],
            "spu_id": detail["spu_id"],
            "category_sk": detail["category_sk"],
            "category_id": detail["category_id"],
            "delivery_sku_qty": detail["sku_qty"],
            "allocated_weight_kg": weight,
            "allocated_freight_amount": MONEY_ZERO,
            "currency_code": "CNY",
            "delivery_create_time": reverse_time,
            "biz_date": reverse_time.date(),
        },
    )
    _write_delivery_status(
        state,
        writer,
        cutoff,
        batch_id,
        reverse_delivery_id,
        1,
        None,
        "CREATED",
        "RETURN_CREATED",
        reverse_time,
        region,
    )
    reverse_ship_time = reverse_time + timedelta(hours=4)
    reverse_signed_time = reverse_time + timedelta(days=2)
    _write_delivery_status(
        state,
        writer,
        cutoff,
        batch_id,
        reverse_delivery_id,
        2,
        "CREATED",
        "SHIPPED",
        "RETURN_SHIPPED",
        reverse_ship_time,
        region,
    )
    _write_delivery_status(
        state,
        writer,
        cutoff,
        batch_id,
        reverse_delivery_id,
        3,
        "SHIPPED",
        "SIGNED",
        "RETURN_RECEIVED",
        reverse_signed_time,
        None,
    )
    return _inventory_event(
        detail["profile"],
        "RETURN_RECEIPT",
        "REFUND",
        refund_detail_id,
        int(detail["quantity"]),
        0,
        detail["profile"].price_on(signed_time.date()).cost_price,
        reverse_signed_time,
        70,
    )


def _write_comment(
    refs: ReferenceData,
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    order_id: int,
    user: dict[str, Any],
    shop: dict[str, Any],
    detail: dict[str, Any],
    signed_time: datetime,
    rng: random.Random,
) -> None:
    publish_time = signed_time + timedelta(hours=6 + rng.randrange(72))
    comment_id = int(detail["order_detail_id"])
    level = rng.choices([3, 4, 5], weights=[5, 22, 73], k=1)[0]
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_service_comment_detail_di",
        f"comment:{comment_id}",
        publish_time,
        {
            "comment_detail_id": comment_id,
            "comment_id": comment_id,
            "parent_comment_detail_id": None,
            "comment_type": "初评",
            "comment_date_key": date_key(publish_time),
            "order_id": order_id,
            "order_detail_id": detail["order_detail_id"],
            "user_sk": version_at(
                refs.user_versions,
                int(user["user_id"]),
                publish_time,
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
            "comment_level": level,
            "is_anonymous": int(rng.random() < 0.65),
            "image_count": rng.choices([0, 1, 2, 3], weights=[72, 18, 7, 3], k=1)[0],
            "video_count": int(rng.random() < 0.03),
            "comment_content": "商品符合预期，使用体验良好",
            "service_score": level,
            "logistics_score": min(5, level + 1),
            "description_score": level,
            "sensitive_tag": None,
            "sentiment": "正向" if level >= 4 else "中性",
            "comment_time": publish_time,
            "biz_date": publish_time.date(),
        },
    )


def _apply_inventory_events(
    refs: ReferenceData,
    state: BusinessState,
    writer: TableWriter,
    events: list[dict[str, Any]],
    batch_id: str,
) -> None:
    events.sort(
        key=lambda event: (
            event["event_time"],
            event["priority"],
            event["sku_id"],
            str(event["biz_id"]),
        )
    )
    local_by_day: dict[date, int] = defaultdict(int)
    for event in events:
        sku_id = int(event["sku_id"])
        profile = refs.profile_by_sku[sku_id]
        position = state.inventory[sku_id]
        before_on_hand = position.on_hand
        before_reserved = position.reserved
        after_on_hand = before_on_hand + int(event["on_hand_delta"])
        after_reserved = before_reserved + int(event["reserved_delta"])
        if after_on_hand < 0 or not 0 <= after_reserved <= after_on_hand:
            raise ValueError(
                f"库存状态非法 sku_id={sku_id} event={event} "
                f"before=({before_on_hand},{before_reserved})"
            )
        position.on_hand = after_on_hand
        position.reserved = after_reserved
        position.unit_cost = price(event["unit_cost"])
        event_day = event["event_time"].date()
        local_by_day[event_day] += 1
        event_id = date_key(event_day) * 1_000_000 + local_by_day[event_day]
        warehouse = _warehouse_for_shop(refs, int(profile.shop["shop_id"]))
        row = {
            "inventory_change_id": event_id,
            "change_no": f"IC{event_id}",
            "event_date_key": date_key(event_day),
            "warehouse_sk": warehouse["warehouse_sk"],
            "warehouse_id": warehouse["warehouse_id"],
            "sku_sk": profile.sku["sku_sk"],
            "sku_id": sku_id,
            "spu_sk": profile.spu["spu_sk"],
            "spu_id": profile.spu["spu_id"],
            "shop_sk": profile.shop["shop_sk"],
            "shop_id": profile.shop["shop_id"],
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
            "total_cost_delta": price(
                Decimal(event["on_hand_delta"]) * event["unit_cost"]
            ),
            "currency_code": "CNY",
            "operator_id": "SYSTEM",
            "operator_type": "SYSTEM",
            "remark": event["change_type"],
            "event_time": event["event_time"],
            "biz_date": event_day,
        } | fact_audit(f"inventory-change:{event_id}", batch_id)
        writer.add("dwd_inventory_change_di", row)


def _inventory_event(
    profile: ProductProfile,
    change_type: str,
    biz_type: str,
    biz_id: int | str,
    on_hand_delta: int,
    reserved_delta: int,
    unit_cost: Decimal,
    event_time: datetime,
    priority: int,
) -> dict[str, Any]:
    return {
        "sku_id": int(profile.sku["sku_id"]),
        "change_type": change_type,
        "biz_type": biz_type,
        "biz_id": str(biz_id),
        "on_hand_delta": on_hand_delta,
        "reserved_delta": reserved_delta,
        "unit_cost": price(unit_cost),
        "event_time": event_time,
        "priority": priority,
    }


def _write_order_status(
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
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
    event_id = order_id * 10 + seq_no
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_order_status_event_di",
        f"order-status:{order_id}:{seq_no}",
        event_time,
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
            "operator_type": "USER" if after == "CANCELLED" else "SYSTEM",
            "event_time": event_time,
            "biz_date": event_time.date(),
        },
    )


def _write_pay_status(
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    pay_detail_id: int,
    seq_no: int,
    before: str | None,
    after: str,
    event_time: datetime,
) -> None:
    event_id = pay_detail_id * 10 + seq_no
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_pay_status_event_di",
        f"pay-status:{pay_detail_id}:{seq_no}",
        event_time,
        {
            "pay_status_event_id": event_id,
            "pay_detail_id": pay_detail_id,
            "pay_order_no": f"P{pay_detail_id}",
            "event_seq_no": seq_no,
            "event_date_key": date_key(event_time),
            "third_party_pay_no": f"TP{pay_detail_id}" if after == "SUCCESS" else None,
            "before_pay_status": before,
            "after_pay_status": after,
            "status_reason_code": "CHANNEL_REJECTED" if after == "FAILED" else None,
            "status_reason_description": None,
            "event_time": event_time,
            "biz_date": event_time.date(),
        },
    )


def _write_delivery_status(
    state: BusinessState,
    writer: TableWriter,
    cutoff: datetime,
    batch_id: str,
    delivery_id: int,
    seq_no: int,
    before: str | None,
    after: str,
    code: str,
    event_time: datetime,
    region: dict[str, Any] | None,
) -> None:
    event_id = delivery_id * 10 + seq_no
    _schedule_fact(
        state,
        writer,
        cutoff,
        batch_id,
        "dwd_trade_delivery_status_event_di",
        f"delivery-status:{delivery_id}:{seq_no}",
        event_time,
        {
            "delivery_status_event_id": event_id,
            "delivery_id": delivery_id,
            "event_seq_no": seq_no,
            "event_date_key": date_key(event_time),
            "before_delivery_status": before,
            "after_delivery_status": after,
            "status_event_code": code,
            "event_region_sk": region["region_sk"] if region else UNKNOWN_SK,
            "event_region_code": region["region_code"] if region else None,
            "event_location": "区域物流节点",
            "event_remark": None,
            "event_time": event_time,
            "biz_date": event_time.date(),
        },
    )


def _eligible_promotion(
    refs: ReferenceData,
    profile: ProductProfile,
    moment: datetime,
    amount: Decimal,
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in refs.active_promotions(moment)
            if refs.promotion_applies(int(row["promotion_id"]), profile)
            and (
                row.get("threshold_amount") is None
                or amount >= row["threshold_amount"]
            )
        ),
        None,
    )


def _eligible_coupon(
    refs: ReferenceData,
    profile: ProductProfile,
    moment: datetime,
    amount: Decimal,
    rng: random.Random,
) -> dict[str, Any] | None:
    if rng.random() >= 0.28:
        return None
    return next(
        (
            row
            for row in refs.active_coupons(moment)
            if refs.coupon_applies(int(row["coupon_template_id"]), profile)
            and (
                row.get("threshold_amount") is None
                or amount >= row["threshold_amount"]
            )
        ),
        None,
    )


def _rule_discount(rule: dict[str, Any] | None, amount: Decimal) -> Decimal:
    if rule is None:
        return MONEY_ZERO
    if rule.get("discount_amount") is not None:
        return money(min(amount, rule["discount_amount"]))
    if rule.get("discount_rate") is not None:
        discount = amount * (Decimal("1") - rule["discount_rate"])
        maximum = rule.get("max_discount_amount")
        return money(min(discount, maximum) if maximum is not None else discount)
    return MONEY_ZERO


def _allocate_money(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    if not weights:
        return []
    weight_sum = sum(weights, Decimal("0"))
    if weight_sum == 0:
        result = [MONEY_ZERO] * len(weights)
        result[0] = money(total)
        return result
    allocations: list[Decimal] = []
    allocated = MONEY_ZERO
    for index, weight in enumerate(weights):
        value = (
            money(total - allocated)
            if index == len(weights) - 1
            else money(total * weight / weight_sum)
        )
        allocations.append(value)
        allocated += value
    return allocations


def _line_weight(detail: dict[str, Any]) -> Decimal:
    profile: ProductProfile = detail["profile"]
    source_weight = profile.spu.get("weight_kg")
    if source_weight is None:
        return Decimal("0.000")
    return (Decimal(str(source_weight)) * int(detail["sku_qty"])).quantize(
        WEIGHT_QUANT,
        rounding=ROUND_HALF_UP,
    )


def _warehouse_for_shop(refs: ReferenceData, shop_id: int) -> dict[str, Any]:
    return refs.warehouses[shop_id % len(refs.warehouses)]

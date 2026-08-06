"""从库存变更事件生成每日库存周期快照"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import Table

from ..support import (
    TableWriter,
    date_key,
    end_of_day,
    fact_audit,
    iter_dates,
    load_rows,
    price,
)
from ...settings import RunContext

logger = logging.getLogger(__name__)


def run(ctx: RunContext, tables: dict[str, Table]) -> None:
    with ctx.engine.connect() as conn:
        writer = TableWriter(
            ctx.loader,
            ctx.gen.batch_size,
            ctx.gen.start_date,
            ctx.as_of_time,
        )
        events = load_rows(
            conn,
            tables["dwd_inventory_change_di"],
            order_by=(
                tables["dwd_inventory_change_di"].c.warehouse_id,
                tables["dwd_inventory_change_di"].c.sku_id,
                tables["dwd_inventory_change_di"].c.event_time,
                tables["dwd_inventory_change_di"].c.inventory_change_id,
            ),
        )
        contexts: dict[tuple[int, int], dict[str, Any]] = {}
        daily_delta: dict[tuple[int, int], dict[Any, tuple[int, int, Decimal]]] = (
            defaultdict(dict)
        )
        for event in events:
            key = (event["warehouse_id"], event["sku_id"])
            contexts[key] = event
            day = event["biz_date"]
            previous = daily_delta[key].get(day, (0, 0, Decimal("0.0000")))
            daily_delta[key][day] = (
                previous[0] + event["on_hand_qty_delta"],
                previous[1] + event["reserved_qty_delta"],
                event["unit_cost"] or previous[2],
            )

        for key, context in contexts.items():
            on_hand = 0
            reserved = 0
            unit_cost = Decimal("0.0000")
            for day in iter_dates(ctx.gen.start_date, ctx.gen.end_date):
                if day in daily_delta[key]:
                    on_delta, reserved_delta, event_cost = daily_delta[key][day]
                    on_hand += on_delta
                    reserved += reserved_delta
                    unit_cost = event_cost
                available = on_hand - reserved
                writer.add(
                    "dwd_inventory_daily_snapshot_df",
                    {
                        "snapshot_date_key": date_key(day),
                        "warehouse_sk": context["warehouse_sk"],
                        "warehouse_id": context["warehouse_id"],
                        "sku_sk": context["sku_sk"],
                        "sku_id": context["sku_id"],
                        "spu_sk": context["spu_sk"],
                        "spu_id": context["spu_id"],
                        "shop_sk": context["shop_sk"],
                        "shop_id": context["shop_id"],
                        "on_hand_qty": on_hand,
                        "reserved_qty": reserved,
                        "available_qty": available,
                        "in_transit_qty": 0,
                        "unit_cost": unit_cost,
                        "inventory_cost_amount": price(unit_cost * on_hand),
                        "currency_code": "CNY",
                        "snapshot_time": min(end_of_day(day), ctx.data_end_time),
                        "biz_date": day,
                    }
                    | fact_audit(
                        f"inventory-snapshot:{context['warehouse_id']}:{context['sku_id']}:{date_key(day)}",
                        ctx.batch_id,
                    ),
                )
        counts = writer.flush_all()
    logger.info("库存快照生成完成 %s", counts)

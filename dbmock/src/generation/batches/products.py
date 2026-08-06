"""生成商品维度、价格事件和商品域每日快照"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Table
from sqlalchemy.engine import Connection

from ..support import (
    END_OF_TIME,
    UNKNOWN_ID,
    UNKNOWN_SK,
    TableWriter,
    date_key,
    dimension_audit,
    end_of_day,
    fact_audit,
    iter_jsonl_rows,
    iter_dates,
    load_json_rows,
    load_rows,
    price,
    start_of_day,
)
from ...settings import RunContext

logger = logging.getLogger(__name__)


def _scd(
    attributes: dict[str, Any],
    ctx: RunContext,
    source_system_code: str = "DBMOCK",
) -> dict[str, Any]:
    return (
        attributes
        | {
            "effective_start_time": attributes.pop(
                "effective_start_time", start_of_day(ctx.gen.start_date)
            ),
            "effective_end_time": END_OF_TIME,
            "version_no": 1,
            "is_current": 1,
            "is_deleted": attributes.get("is_deleted", 0),
        }
        | dimension_audit(attributes, ctx.batch_id, source_system_code)
    )


def _spu_rows(ctx: RunContext):
    yield _scd(
        {
            "spu_sk": UNKNOWN_SK,
            "spu_id": UNKNOWN_ID,
            "spu_name": "未知SPU",
            "spu_sub_title": None,
            "category_id": UNKNOWN_ID,
            "brand_id": UNKNOWN_ID,
            "shop_id": UNKNOWN_ID,
            "is_virtual": 0,
            "is_presale": None,
            "presale_start_time": None,
            "presale_end_time": None,
            "weight_kg": None,
            "volume_m3": None,
            "on_shelf_time": None,
            "spu_status": "在售",
            "is_deleted": 0,
            "effective_start_time": datetime(1900, 1, 1),
        },
        ctx,
    )
    count = 0
    for source in iter_jsonl_rows(ctx.gen.data_dir / "spus.jsonl"):
        if count >= ctx.gen.spu_count:
            break
        yield _scd(
            {
                "spu_id": int(source["spu_id"]),
                "spu_name": str(source["spu_name"]),
                "spu_sub_title": source.get("spu_sub_title"),
                "category_id": int(source["category_id"]),
                "brand_id": int(source["brand_id"]),
                "shop_id": int(source["shop_id"]),
                "is_virtual": int(source.get("is_virtual", 0)),
                "is_presale": source.get("is_presale"),
                "presale_start_time": None,
                "presale_end_time": None,
                "weight_kg": Decimal(str(source["weight_kg"]))
                if source.get("weight_kg") is not None
                else None,
                "volume_m3": Decimal(str(source["volume_m3"]))
                if source.get("volume_m3") is not None
                else None,
                "on_shelf_time": None,
                "spu_status": str(source.get("spu_status", "在售")),
                "is_deleted": 0,
            },
            ctx,
            str(
                source.get(
                    "source_system_code",
                    ctx.gen.catalog_product_source_system,
                )
            ),
        )
        count += 1
    if count != ctx.gen.spu_count:
        raise ValueError(
            f"真实目录SPU不足 requested={ctx.gen.spu_count} available={count}"
        )


def _sku_rows(ctx: RunContext, spus: list[dict[str, Any]]):
    yield _scd(
        {
            "sku_sk": UNKNOWN_SK,
            "sku_id": UNKNOWN_ID,
            "sku_name": "未知SKU",
            "spu_id": UNKNOWN_ID,
            "shop_id": UNKNOWN_ID,
            "category_id": UNKNOWN_ID,
            "brand_id": UNKNOWN_ID,
            "bar_code": None,
            "sku_specs_json": {"未知": "未知"},
            "unit": None,
            "sku_status": "在售",
            "is_deleted": 0,
            "effective_start_time": datetime(1900, 1, 1),
        },
        ctx,
    )
    selected_spu_ids = {int(row["spu_id"]) for row in spus}
    counts: Counter[int] = Counter()
    total = 0
    for source in iter_jsonl_rows(ctx.gen.data_dir / "skus.jsonl"):
        spu_id = int(source["spu_id"])
        if spu_id not in selected_spu_ids:
            continue
        yield _scd(
            {
                "sku_id": int(source["sku_id"]),
                "sku_name": str(source["sku_name"]),
                "spu_id": spu_id,
                "shop_id": int(source["shop_id"]),
                "category_id": int(source["category_id"]),
                "brand_id": int(source["brand_id"]),
                "bar_code": source.get("bar_code"),
                "sku_specs_json": source.get("sku_specs_json"),
                "unit": source.get("unit"),
                "sku_status": str(source.get("sku_status", "在售")),
                "is_deleted": 0,
            },
            ctx,
            str(
                source.get(
                    "source_system_code",
                    ctx.gen.catalog_product_source_system,
                )
            ),
        )
        counts[spu_id] += 1
        total += 1
    invalid_spus = [spu_id for spu_id in selected_spu_ids if counts[spu_id] == 0]
    if invalid_spus:
        raise ValueError(
            f"真实目录SKU不足 available={total} invalid_spus={invalid_spus[:10]}"
        )


def _price_rows(
    ctx: RunContext,
    skus: list[dict[str, Any]],
    spus: dict[int, dict[str, Any]],
    shops: dict[int, dict[str, Any]],
    categories: dict[int, dict[str, Any]],
    brands: dict[int, dict[str, Any]],
):
    source_prices: dict[int, dict[str, Any]] = {}
    for product_lineage in iter_jsonl_rows(ctx.gen.data_dir / "lineage.jsonl"):
        for sku_lineage in product_lineage["skus"]:
            source_prices[int(sku_lineage["sku_id"])] = sku_lineage
    start_time = start_of_day(ctx.gen.start_date) + timedelta(minutes=1)
    span_days = (ctx.gen.end_date - ctx.gen.start_date).days
    second_time = start_time + timedelta(days=max(1, span_days // 2))
    event_id = 70_000_001
    for idx, sku in enumerate(skus):
        spu = spus[sku["spu_id"]]
        shop = shops[sku["shop_id"]]
        category = categories[sku["category_id"]]
        brand = brands.get(sku["brand_id"])
        source_price = source_prices[int(sku["sku_id"])]
        sale_price = price(source_price["origin_sale_price_cny"])
        list_price = price(source_price.get("origin_list_price_cny") or sale_price)
        cost_price = None
        yield {
            "price_change_id": event_id,
            "event_date_key": date_key(start_time),
            "sku_sk": sku["sku_sk"],
            "sku_id": sku["sku_id"],
            "spu_sk": spu["spu_sk"],
            "spu_id": spu["spu_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "category_sk": category["category_sk"],
            "category_id": category["category_id"],
            "brand_sk": brand["brand_sk"] if brand else UNKNOWN_SK,
            "brand_id": brand["brand_id"] if brand else None,
            "previous_list_price": None,
            "previous_sale_price": None,
            "previous_cost_price": None,
            "new_list_price": list_price,
            "new_sale_price": sale_price,
            "new_cost_price": cost_price,
            "change_reason_code": "INITIAL",
            "change_reason_description": "以商品采集时公开价格作为初始基准价",
            "currency_code": "CNY",
            "price_effective_time": start_time,
            "change_time": start_time,
            "biz_date": start_time.date(),
        } | fact_audit(f"sku-price:{sku['sku_id']}:1", ctx.batch_id)
        event_id += 1
        if idx % 10 != 0 or second_time.date() > ctx.gen.end_date:
            continue
        new_sale_price = price(sale_price * Decimal("0.95"))
        yield {
            "price_change_id": event_id,
            "event_date_key": date_key(second_time),
            "sku_sk": sku["sku_sk"],
            "sku_id": sku["sku_id"],
            "spu_sk": spu["spu_sk"],
            "spu_id": spu["spu_id"],
            "shop_sk": shop["shop_sk"],
            "shop_id": shop["shop_id"],
            "category_sk": category["category_sk"],
            "category_id": category["category_id"],
            "brand_sk": brand["brand_sk"] if brand else UNKNOWN_SK,
            "brand_id": brand["brand_id"] if brand else None,
            "previous_list_price": list_price,
            "previous_sale_price": sale_price,
            "previous_cost_price": cost_price,
            "new_list_price": list_price,
            "new_sale_price": new_sale_price,
            "new_cost_price": None,
            "change_reason_code": "PROMOTION",
            "change_reason_description": "周期性调价",
            "currency_code": "CNY",
            "price_effective_time": second_time,
            "change_time": second_time - timedelta(minutes=5),
            "biz_date": second_time.date(),
        } | fact_audit(f"sku-price:{sku['sku_id']}:2", ctx.batch_id)
        event_id += 1


def _shop_score_rows(
    ctx: RunContext,
    shops: list[dict[str, Any]],
    sellers: dict[int, dict[str, Any]],
):
    scores = {
        int(seed["shop_id"]): seed
        for seed in load_json_rows(ctx.gen.master_data_path("shops.json"))
    }
    for day_idx, day in enumerate(iter_dates(ctx.gen.start_date, ctx.gen.end_date)):
        for idx, shop in enumerate(shops):
            seed = scores[shop["shop_id"]]
            service_score = seed.get("service_score")
            logistics_score = seed.get("logistics_score")
            description_score = seed.get("description_score")
            if all(
                value is None
                for value in (service_score, logistics_score, description_score)
            ):
                continue
            drift = Decimal((day_idx + idx) % 5 - 2) / Decimal("100")
            seller = sellers.get(shop["seller_id"])
            yield {
                "snapshot_date_key": date_key(day),
                "shop_sk": shop["shop_sk"],
                "shop_id": shop["shop_id"],
                "seller_sk": seller["seller_sk"] if seller else UNKNOWN_SK,
                "seller_id": seller["seller_id"] if seller else None,
                "service_score": min(Decimal("5.00"), Decimal(service_score) + drift)
                if service_score is not None
                else None,
                "logistics_score": min(
                    Decimal("5.00"), Decimal(logistics_score) + drift
                )
                if logistics_score is not None
                else None,
                "description_score": min(
                    Decimal("5.00"), Decimal(description_score) + drift
                )
                if description_score is not None
                else None,
                "snapshot_time": min(end_of_day(day), ctx.data_end_time),
                "biz_date": day,
            } | fact_audit(
                f"shop-score:{shop['shop_id']}:{date_key(day)}", ctx.batch_id
            )


def _sku_operation_rows(
    ctx: RunContext,
    skus: list[dict[str, Any]],
    spus: dict[int, dict[str, Any]],
    shops: dict[int, dict[str, Any]],
    categories: dict[int, dict[str, Any]],
):
    for day_idx, day in enumerate(iter_dates(ctx.gen.start_date, ctx.gen.end_date)):
        for idx, sku in enumerate(skus):
            spu = spus[sku["spu_id"]]
            shop = shops[sku["shop_id"]]
            category = categories[sku["category_id"]]
            yield {
                "snapshot_date_key": date_key(day),
                "sku_sk": sku["sku_sk"],
                "sku_id": sku["sku_id"],
                "spu_sk": spu["spu_sk"],
                "spu_id": spu["spu_id"],
                "shop_sk": shop["shop_sk"],
                "shop_id": shop["shop_id"],
                "category_sk": category["category_sk"],
                "category_id": category["category_id"],
                "warning_stock_qty": 20 + idx % 30,
                "is_hot_sale": int((idx + day_idx) % 17 == 0),
                "is_new": int(day_idx < 30),
                "snapshot_time": min(end_of_day(day), ctx.data_end_time),
                "biz_date": day,
            } | fact_audit(
                f"sku-operation:{sku['sku_id']}:{date_key(day)}", ctx.batch_id
            )


def _load_catalog_masters(
    conn: Connection,
    tables: dict[str, Table],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    shops = load_rows(
        conn,
        tables["dim_shop_info_zip"],
        where=(tables["dim_shop_info_zip"].c.is_current == 1)
        & (tables["dim_shop_info_zip"].c.shop_id != UNKNOWN_ID),
    )
    categories = load_rows(
        conn,
        tables["dim_category_info_zip"],
        where=(tables["dim_category_info_zip"].c.is_current == 1)
        & (tables["dim_category_info_zip"].c.is_leaf == 1)
        & (tables["dim_category_info_zip"].c.category_id != UNKNOWN_ID),
    )
    brands = load_rows(
        conn,
        tables["dim_brand_info"],
        where=tables["dim_brand_info"].c.brand_id != UNKNOWN_ID,
    )
    return shops, categories, brands


def _write_catalog_dimensions(
    ctx: RunContext,
    tables: dict[str, Table],
    conn: Connection,
    writer: TableWriter,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    writer.add_many("dim_spu_info_zip", _spu_rows(ctx))
    writer.flush_all()
    spus = load_rows(
        conn,
        tables["dim_spu_info_zip"],
        where=(tables["dim_spu_info_zip"].c.is_current == 1)
        & (tables["dim_spu_info_zip"].c.spu_id != UNKNOWN_ID),
    )
    writer.add_many("dim_sku_info_zip", _sku_rows(ctx, spus))
    writer.flush_all()
    skus = load_rows(
        conn,
        tables["dim_sku_info_zip"],
        where=(tables["dim_sku_info_zip"].c.is_current == 1)
        & (tables["dim_sku_info_zip"].c.sku_id != UNKNOWN_ID),
    )
    return spus, skus


def run_dimensions(ctx: RunContext, tables: dict[str, Table]) -> None:
    with ctx.engine.connect() as conn:
        writer = TableWriter(
            ctx.loader,
            ctx.gen.batch_size,
            ctx.gen.start_date,
            ctx.as_of_time,
        )
        _write_catalog_dimensions(ctx, tables, conn, writer)
        counts = writer.flush_all()
    logger.info("商品维度生成完成 %s", counts)


def run(ctx: RunContext, tables: dict[str, Table]) -> None:
    with ctx.engine.connect() as conn:
        writer = TableWriter(
            ctx.loader,
            ctx.gen.batch_size,
            ctx.gen.start_date,
            ctx.as_of_time,
        )
        shops, categories, brands = _load_catalog_masters(conn, tables)
        spus, skus = _write_catalog_dimensions(ctx, tables, conn, writer)
        spu_by_id = {row["spu_id"]: row for row in spus}
        shop_by_id = {row["shop_id"]: row for row in shops}
        category_by_id = {row["category_id"]: row for row in categories}
        brand_by_id = {row["brand_id"]: row for row in brands}
        sellers = load_rows(
            conn,
            tables["dim_seller_info_zip"],
            where=(tables["dim_seller_info_zip"].c.is_current == 1)
            & (tables["dim_seller_info_zip"].c.seller_id != UNKNOWN_ID),
        )
        seller_by_id = {row["seller_id"]: row for row in sellers}

        writer.add_many(
            "dwd_product_sku_price_change_di",
            _price_rows(
                ctx,
                skus,
                spu_by_id,
                shop_by_id,
                category_by_id,
                brand_by_id,
            ),
        )
        writer.add_many(
            "dwd_product_shop_score_daily_snapshot_df",
            _shop_score_rows(ctx, shops, seller_by_id),
        )
        writer.add_many(
            "dwd_product_sku_operation_daily_snapshot_df",
            _sku_operation_rows(
                ctx,
                skus,
                spu_by_id,
                shop_by_id,
                category_by_id,
            ),
        )
        counts = writer.flush_all()
    logger.info("商品域生成完成 %s", counts)

"""生成会话、页面、搜索、加购和收藏行为"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy import Table

from ..support import (
    UNKNOWN_ID,
    UNKNOWN_SK,
    TableWriter,
    build_version_index,
    date_key,
    fact_audit,
    load_rows,
    price,
    start_of_day,
    version_at,
)
from ...settings import RunContext

logger = logging.getLogger(__name__)


def _distributed_time(ctx: RunContext, index: int, total: int) -> datetime:
    start = start_of_day(ctx.gen.start_date) + timedelta(minutes=10)
    end = ctx.data_end_time - timedelta(hours=1)
    seconds = max(1, int((end - start).total_seconds()))
    return start + timedelta(seconds=seconds * index // max(total, 1))


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
        skus = load_rows(
            conn,
            tables["dim_sku_info_zip"],
            where=(tables["dim_sku_info_zip"].c.is_current == 1)
            & (tables["dim_sku_info_zip"].c.sku_id != UNKNOWN_ID),
        )
        spus = load_rows(
            conn,
            tables["dim_spu_info_zip"],
            where=tables["dim_spu_info_zip"].c.is_current == 1,
        )
        spu_by_id = {row["spu_id"]: row for row in spus}
        shops = load_rows(
            conn,
            tables["dim_shop_info_zip"],
            where=tables["dim_shop_info_zip"].c.is_current == 1,
        )
        shop_by_id = {row["shop_id"]: row for row in shops}
        categories = load_rows(
            conn,
            tables["dim_category_info_zip"],
            where=tables["dim_category_info_zip"].c.is_current == 1,
        )
        category_by_id = {row["category_id"]: row for row in categories}
        channels = load_rows(
            conn,
            tables["dim_channel_info"],
            where=tables["dim_channel_info"].c.channel_code != "UNKNOWN",
        )
        pages = load_rows(conn, tables["dim_page_info"])
        page_by_id = {row["page_id"]: row for row in pages}
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
        prices = load_rows(
            conn,
            tables["dwd_product_sku_price_change_di"],
            order_by=(
                tables["dwd_product_sku_price_change_di"].c.sku_id,
                tables["dwd_product_sku_price_change_di"].c.price_effective_time,
            ),
        )
        latest_price: dict[int, Decimal] = {}
        for row in prices:
            latest_price[row["sku_id"]] = price(row["new_sale_price"])

        session_count = max(
            1, min(ctx.gen.page_view_count, ceil(ctx.gen.page_view_count / 4))
        )
        view_counts = [ctx.gen.page_view_count // session_count] * session_count
        for idx in range(ctx.gen.page_view_count % session_count):
            view_counts[idx] += 1
        search_counts = [ctx.gen.search_count // session_count] * session_count
        for idx in range(ctx.gen.search_count % session_count):
            search_counts[idx] += 1

        page_view_id = 300_000_001
        search_id = 310_000_001
        search_click_id = 320_000_001
        session_fact_id = 330_000_001
        total_search_index = 0
        for session_idx in range(session_count):
            session_id = f"S{session_fact_id}"
            session_start = _distributed_time(ctx, session_idx, session_count)
            is_guest = session_idx % 5 == 0
            current_user = current_users[session_idx % len(current_users)]
            user = (
                None
                if is_guest
                else version_at(user_versions, current_user["user_id"], session_start)
            )
            channel = channels[session_idx % len(channels)]
            region = (
                region_by_district.get(current_user.get("district_code"))
                if user
                else regions[session_idx % len(regions)]
            )
            device_id = f"DEV{session_idx + 1:08d}"
            session_search_ids: list[int] = []
            last_event_time = session_start

            for local_search_idx in range(search_counts[session_idx]):
                event_time = min(
                    session_start + timedelta(seconds=20 + local_search_idx * 30),
                    ctx.data_end_time,
                )
                sku = skus[total_search_index % len(skus)]
                keyword = category_by_id[sku["category_id"]]["category_name"]
                current_search_id = search_id
                session_search_ids.append(current_search_id)
                writer.add(
                    "dwd_traffic_search_di",
                    {
                        "search_detail_id": current_search_id,
                        "event_no": f"SEARCH{current_search_id}",
                        "event_date_key": date_key(event_time),
                        "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                        "user_id": user["user_id"] if user else None,
                        "device_id": device_id,
                        "session_id": session_id,
                        "channel_sk": channel["channel_sk"],
                        "channel_code": channel["channel_code"],
                        "search_keyword": keyword,
                        "normalized_keyword": keyword.lower(),
                        "search_source": "SEARCH_BOX",
                        "result_total_count": 20,
                        "is_no_result": 0,
                        "is_search_success": 1,
                        "event_time": event_time,
                        "biz_date": event_time.date(),
                    }
                    | fact_audit(f"search:{current_search_id}", ctx.batch_id),
                )
                if total_search_index % 2 == 0:
                    spu = spu_by_id[sku["spu_id"]]
                    shop = shop_by_id[sku["shop_id"]]
                    category = category_by_id[sku["category_id"]]
                    click_time = min(
                        event_time + timedelta(seconds=3),
                        ctx.data_end_time,
                    )
                    writer.add(
                        "dwd_traffic_search_click_di",
                        {
                            "search_click_id": search_click_id,
                            "search_detail_id": current_search_id,
                            "event_no": f"SEARCHCLICK{search_click_id}",
                            "event_date_key": date_key(click_time),
                            "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                            "user_id": user["user_id"] if user else None,
                            "device_id": device_id,
                            "session_id": session_id,
                            "channel_sk": channel["channel_sk"],
                            "channel_code": channel["channel_code"],
                            "click_sku_sk": sku["sku_sk"],
                            "click_sku_id": sku["sku_id"],
                            "click_spu_sk": spu["spu_sk"],
                            "click_spu_id": spu["spu_id"],
                            "click_shop_sk": shop["shop_sk"],
                            "click_shop_id": shop["shop_id"],
                            "click_category_sk": category["category_sk"],
                            "click_category_id": category["category_id"],
                            "click_rank": total_search_index % 20 + 1,
                            "event_time": click_time,
                            "biz_date": click_time.date(),
                        }
                        | fact_audit(f"search-click:{search_click_id}", ctx.batch_id),
                    )
                    search_click_id += 1
                    last_event_time = max(last_event_time, click_time)
                search_id += 1
                total_search_index += 1
                last_event_time = max(last_event_time, event_time)

            session_pages: list[dict[str, Any]] = []
            for view_idx in range(view_counts[session_idx]):
                if view_idx == 0:
                    page = page_by_id["HOME"]
                    sku = None
                elif view_idx == 1 and session_search_ids:
                    page = page_by_id["SEARCH"]
                    sku = None
                else:
                    page = page_by_id["PRODUCT"]
                    sku = skus[(session_idx + view_idx) % len(skus)]
                event_time = min(
                    session_start + timedelta(seconds=view_idx * 60),
                    ctx.data_end_time,
                )
                previous = session_pages[-1] if session_pages else None
                spu = spu_by_id[sku["spu_id"]] if sku else None
                shop = shop_by_id[sku["shop_id"]] if sku else None
                category = category_by_id[sku["category_id"]] if sku else None
                linked_search = (
                    session_search_ids[min(view_idx - 2, len(session_search_ids) - 1)]
                    if sku and session_search_ids
                    else None
                )
                row = {
                    "page_view_id": page_view_id,
                    "event_no": f"PV{page_view_id}",
                    "event_date_key": date_key(event_time),
                    "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                    "user_id": user["user_id"] if user else None,
                    "device_id": device_id,
                    "session_id": session_id,
                    "page_sk": page["page_sk"],
                    "page_id": page["page_id"],
                    "last_page_sk": previous["page_sk"] if previous else UNKNOWN_SK,
                    "last_page_id": previous["page_id"] if previous else None,
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "shop_sk": shop["shop_sk"] if shop else UNKNOWN_SK,
                    "shop_id": shop["shop_id"] if shop else None,
                    "sku_sk": sku["sku_sk"] if sku else UNKNOWN_SK,
                    "sku_id": sku["sku_id"] if sku else None,
                    "spu_sk": spu["spu_sk"] if spu else UNKNOWN_SK,
                    "spu_id": spu["spu_id"] if spu else None,
                    "category_sk": category["category_sk"] if category else UNKNOWN_SK,
                    "category_id": category["category_id"] if category else None,
                    "promotion_version_sk": UNKNOWN_SK,
                    "promotion_id": None,
                    "search_detail_id": linked_search,
                    "business_type": None,
                    "business_id": None,
                    "client_type": "APP",
                    "app_version": "8.1.0",
                    "os_type": "Android" if session_idx % 2 == 0 else "iOS",
                    "region_sk": region["region_sk"] if region else UNKNOWN_SK,
                    "region_code": region["region_code"] if region else None,
                    "stay_duration_sec": 20 + view_idx % 100,
                    "event_time": event_time,
                    "biz_date": event_time.date(),
                } | fact_audit(f"page-view:{page_view_id}", ctx.batch_id)
                writer.add("dwd_traffic_page_view_di", row)
                session_pages.append(row)
                page_view_id += 1
                last_event_time = max(last_event_time, event_time)

            session_end = min(
                last_event_time + timedelta(seconds=30),
                ctx.data_end_time,
            )
            duration = max(0, int((session_end - session_start).total_seconds()))
            entry = session_pages[0]
            exit_page = session_pages[-1]
            writer.add(
                "dwd_traffic_session_di",
                {
                    "session_fact_id": session_fact_id,
                    "session_id": session_id,
                    "session_date_key": date_key(session_start),
                    "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                    "user_id": user["user_id"] if user else None,
                    "device_id": device_id,
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "entry_page_sk": entry["page_sk"],
                    "entry_page_id": entry["page_id"],
                    "exit_page_sk": exit_page["page_sk"],
                    "exit_page_id": exit_page["page_id"],
                    "region_sk": region["region_sk"] if region else UNKNOWN_SK,
                    "region_code": region["region_code"] if region else None,
                    "client_type": "APP",
                    "app_version": "8.1.0",
                    "os_type": "Android" if session_idx % 2 == 0 else "iOS",
                    "ip_masked": f"10.{session_idx % 255}.***.***",
                    "page_view_count": view_counts[session_idx],
                    "search_count": search_counts[session_idx],
                    "session_duration_sec": duration,
                    "is_bounce": int(view_counts[session_idx] <= 1),
                    "session_start_time": session_start,
                    "session_end_time": session_end,
                    "biz_date": session_start.date(),
                }
                | fact_audit(f"session:{session_fact_id}", ctx.batch_id),
            )
            session_fact_id += 1

        cart_event_id = 340_000_001
        favor_event_id = 350_000_001
        for user_idx, current_user in enumerate(current_users):
            sku = skus[user_idx % len(skus)]
            spu = spu_by_id[sku["spu_id"]]
            shop = shop_by_id[sku["shop_id"]]
            category = category_by_id[sku["category_id"]]
            channel = channels[user_idx % len(channels)]
            quantity = 0
            for event_idx in range(ctx.gen.cart_events_per_user):
                event_time = _distributed_time(
                    ctx,
                    user_idx * max(1, ctx.gen.cart_events_per_user) + event_idx,
                    len(current_users) * max(1, ctx.gen.cart_events_per_user),
                )
                user = version_at(user_versions, current_user["user_id"], event_time)
                if event_idx % 2 == 0:
                    delta = 1
                    event_type = "加入"
                else:
                    delta = -quantity if quantity > 0 else 1
                    event_type = "移除" if delta < 0 else "加入"
                quantity += delta
                writer.add(
                    "dwd_interaction_cart_event_di",
                    {
                        "cart_event_id": cart_event_id,
                        "event_no": f"CART{cart_event_id}",
                        "event_date_key": date_key(event_time),
                        "user_sk": user["user_sk"],
                        "user_id": user["user_id"],
                        "device_id": f"USERDEV{user['user_id']}",
                        "session_id": f"CARTSESSION{user['user_id']}",
                        "shop_sk": shop["shop_sk"],
                        "shop_id": shop["shop_id"],
                        "sku_sk": sku["sku_sk"],
                        "sku_id": sku["sku_id"],
                        "spu_sk": spu["spu_sk"],
                        "spu_id": spu["spu_id"],
                        "category_sk": category["category_sk"],
                        "category_id": category["category_id"],
                        "channel_sk": channel["channel_sk"],
                        "channel_code": channel["channel_code"],
                        "cart_event_type": event_type,
                        "cart_source": "商品详情页",
                        "sku_qty_delta": delta,
                        "cart_sku_qty_after": quantity,
                        "sku_unit_price": latest_price[sku["sku_id"]],
                        "currency_code": "CNY",
                        "event_time": event_time,
                        "biz_date": event_time.date(),
                    }
                    | fact_audit(f"cart:{cart_event_id}", ctx.batch_id),
                )
                cart_event_id += 1

            for event_idx in range(ctx.gen.favor_events_per_user):
                event_time = _distributed_time(
                    ctx,
                    user_idx * max(1, ctx.gen.favor_events_per_user) + event_idx,
                    len(current_users) * max(1, ctx.gen.favor_events_per_user),
                )
                user = version_at(user_versions, current_user["user_id"], event_time)
                writer.add(
                    "dwd_interaction_favor_event_di",
                    {
                        "favor_event_id": favor_event_id,
                        "event_no": f"FAVOR{favor_event_id}",
                        "event_date_key": date_key(event_time),
                        "user_sk": user["user_sk"],
                        "user_id": user["user_id"],
                        "device_id": f"USERDEV{user['user_id']}",
                        "session_id": f"FAVORSESSION{user['user_id']}",
                        "shop_sk": shop["shop_sk"],
                        "shop_id": shop["shop_id"],
                        "sku_sk": sku["sku_sk"],
                        "sku_id": sku["sku_id"],
                        "spu_sk": spu["spu_sk"],
                        "spu_id": spu["spu_id"],
                        "channel_sk": channel["channel_sk"],
                        "channel_code": channel["channel_code"],
                        "favor_target_type": "商品",
                        "favor_event_type": "收藏"
                        if event_idx % 2 == 0
                        else "取消收藏",
                        "event_time": event_time,
                        "biz_date": event_time.date(),
                    }
                    | fact_audit(f"favor:{favor_event_id}", ctx.batch_id),
                )
                favor_event_id += 1

        counts = writer.flush_all()
    logger.info("行为域生成完成 %s", counts)

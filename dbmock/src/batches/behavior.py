"""生成与订单转化共享会话的日级用户行为"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from math import ceil

from ..reference import ReferenceData
from ..settings import RunContext
from ..support import (
    UNKNOWN_SK,
    TableWriter,
    date_key,
    fact_audit,
    version_at,
)
from ..timeline import ConversionIntent


def generate_day(
    ctx: RunContext,
    refs: ReferenceData,
    writer: TableWriter,
    day: date,
    batch_id: str,
    page_view_count: int,
    search_count: int,
    order_detail_target: int,
) -> list[ConversionIntent]:
    active_profiles = refs.active_profiles(day)
    if not active_profiles:
        if page_view_count or search_count or order_detail_target:
            raise ValueError(f"{day} 没有已上架商品，无法生成行为")
        return []
    rng = random.Random(f"{ctx.gen.seed}:{day}:behavior")
    active_shop_counts: dict[int, int] = {}
    for active_profile in active_profiles:
        shop_id = int(active_profile.shop["shop_id"])
        active_shop_counts[shop_id] = active_shop_counts.get(shop_id, 0) + 1
    eligible_profiles_by_lines = {
        line_count: [
            profile
            for profile in active_profiles
            if active_shop_counts[int(profile.shop["shop_id"])] >= line_count
        ]
        for line_count in (1, 2, 3)
    }
    line_counts = _order_line_counts(order_detail_target, rng)
    session_count = max(
        len(line_counts),
        1 if page_view_count else 0,
        ceil(page_view_count / 4),
    )
    if page_view_count < session_count:
        raise ValueError(
            f"页面访问量不足以承载会话 day={day} "
            f"views={page_view_count} sessions={session_count}"
        )
    view_counts = _spread(page_view_count, session_count, 1)
    search_counts = _spread(search_count, session_count, 0)
    conversion_indexes = _even_indexes(session_count, len(line_counts))
    line_count_by_session = dict(zip(conversion_indexes, line_counts, strict=True))
    conversion_intents: list[ConversionIntent] = []
    search_local = 1
    click_local = 1
    page_view_local = 1
    cart_local = 1
    favor_local = 1

    for session_index in range(session_count):
        session_local = session_index + 1
        session_fact_id = date_key(day) * 1_000_000 + session_local
        session_id = f"S{session_fact_id}"
        is_conversion = session_index in line_count_by_session
        is_guest = not is_conversion and rng.random() < 0.18
        current_user = refs.current_users[
            _long_tail_index(rng, len(refs.current_users), 1.35)
        ]
        start_second = 8 * 3600 + (
            session_index * (15 * 3600) // max(1, session_count)
        )
        session_start = datetime.combine(day, datetime.min.time()) + timedelta(
            seconds=start_second + rng.randrange(0, 45)
        )
        session_start = min(session_start, ctx.data_end_time)
        user = (
            version_at(
                refs.user_versions,
                int(current_user["user_id"]),
                session_start,
            )
            if not is_guest
            else None
        )
        channel = _choose_channel(refs, rng)
        region = (
            refs.regions_by_district.get(str(user.get("district_code")))
            if user and user.get("district_code") is not None
            else None
        )
        required_lines = line_count_by_session.get(session_index, 1)
        eligible_profiles = eligible_profiles_by_lines[required_lines]
        if not eligible_profiles:
            raise ValueError(
                f"{day} 没有可承载 {required_lines} 个订单行的商品"
            )
        profile = eligible_profiles[
            _long_tail_index(rng, len(eligible_profiles), 2.0)
        ]
        device_id = (
            f"USERDEV{user['user_id']}"
            if user
            else f"GUESTDEV{date_key(day)}{session_local:06d}"
        )
        session_search_count = search_counts[session_index]
        search_ids: list[int] = []
        for search_index in range(session_search_count):
            search_id = date_key(day) * 1_000_000 + search_local
            search_time = min(
                session_start + timedelta(seconds=20 + search_index * 35),
                ctx.data_end_time,
            )
            keyword = str(profile.spu["spu_name"])[:80]
            writer.add(
                "dwd_traffic_search_di",
                {
                    "search_detail_id": search_id,
                    "event_no": f"SEARCH{search_id}",
                    "event_date_key": date_key(day),
                    "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                    "user_id": user["user_id"] if user else None,
                    "device_id": device_id,
                    "session_id": session_id,
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "search_keyword": keyword,
                    "normalized_keyword": keyword.lower(),
                    "search_source": "站内搜索框",
                    "result_total_count": 20 + rng.randrange(180),
                    "is_no_result": 0,
                    "is_search_success": 1,
                    "event_time": search_time,
                    "biz_date": day,
                }
                | fact_audit(f"search:{search_id}", batch_id),
            )
            search_ids.append(search_id)
            if is_conversion or rng.random() < 0.62:
                click_id = date_key(day) * 1_000_000 + click_local
                click_time = min(search_time + timedelta(seconds=5), ctx.data_end_time)
                writer.add(
                    "dwd_traffic_search_click_di",
                    {
                        "search_click_id": click_id,
                        "search_detail_id": search_id,
                        "event_no": f"SEARCHCLICK{click_id}",
                        "event_date_key": date_key(day),
                        "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                        "user_id": user["user_id"] if user else None,
                        "device_id": device_id,
                        "session_id": session_id,
                        "channel_sk": channel["channel_sk"],
                        "channel_code": channel["channel_code"],
                        "click_sku_sk": profile.sku["sku_sk"],
                        "click_sku_id": profile.sku["sku_id"],
                        "click_spu_sk": profile.spu["spu_sk"],
                        "click_spu_id": profile.spu["spu_id"],
                        "click_shop_sk": profile.shop["shop_sk"],
                        "click_shop_id": profile.shop["shop_id"],
                        "click_category_sk": profile.category["category_sk"],
                        "click_category_id": profile.category["category_id"],
                        "click_rank": 1 + rng.randrange(12),
                        "event_time": click_time,
                        "biz_date": day,
                    }
                    | fact_audit(f"search-click:{click_id}", batch_id),
                )
                click_local += 1
            search_local += 1

        session_view_count = view_counts[session_index]
        pages = _page_sequence(refs, session_view_count, is_conversion)
        last_page = None
        for view_index, page in enumerate(pages):
            page_view_id = date_key(day) * 1_000_000 + page_view_local
            event_time = min(
                session_start + timedelta(seconds=view_index * 35),
                ctx.data_end_time,
            )
            product_page = page["page_id"] in {"PRODUCT", "CART", "ORDER"}
            active_promotions = refs.active_promotions(event_time)
            promotion = active_promotions[0] if active_promotions else None
            writer.add(
                "dwd_traffic_page_view_di",
                {
                    "page_view_id": page_view_id,
                    "event_no": f"PV{page_view_id}",
                    "event_date_key": date_key(day),
                    "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                    "user_id": user["user_id"] if user else None,
                    "device_id": device_id,
                    "session_id": session_id,
                    "page_sk": page["page_sk"],
                    "page_id": page["page_id"],
                    "last_page_sk": last_page["page_sk"]
                    if last_page
                    else UNKNOWN_SK,
                    "last_page_id": last_page["page_id"] if last_page else None,
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "shop_sk": profile.shop["shop_sk"]
                    if product_page
                    else UNKNOWN_SK,
                    "shop_id": profile.shop["shop_id"] if product_page else None,
                    "sku_sk": profile.sku["sku_sk"]
                    if product_page
                    else UNKNOWN_SK,
                    "sku_id": profile.sku["sku_id"] if product_page else None,
                    "spu_sk": profile.spu["spu_sk"]
                    if product_page
                    else UNKNOWN_SK,
                    "spu_id": profile.spu["spu_id"] if product_page else None,
                    "category_sk": profile.category["category_sk"]
                    if product_page
                    else UNKNOWN_SK,
                    "category_id": profile.category["category_id"]
                    if product_page
                    else None,
                    "promotion_version_sk": promotion["promotion_version_sk"]
                    if promotion
                    else UNKNOWN_SK,
                    "promotion_id": promotion["promotion_id"]
                    if promotion
                    else None,
                    "search_detail_id": search_ids[-1] if search_ids else None,
                    "business_type": None,
                    "business_id": None,
                    "client_type": channel["platform_type"],
                    "app_version": "8.6.0"
                    if channel["channel_code"] == "APP"
                    else None,
                    "os_type": "Android" if session_index % 2 == 0 else "iOS",
                    "region_sk": region["region_sk"] if region else UNKNOWN_SK,
                    "region_code": region["region_code"] if region else None,
                    "stay_duration_sec": 12 + rng.randrange(120),
                    "event_time": event_time,
                    "biz_date": day,
                }
                | fact_audit(f"page-view:{page_view_id}", batch_id),
            )
            page_view_local += 1
            last_page = page

        session_end = min(
            session_start + timedelta(seconds=max(20, session_view_count * 35)),
            ctx.data_end_time,
        )
        if is_conversion and user is not None:
            cart_event_id = date_key(day) * 1_000_000 + cart_local
            cart_time = max(session_start, session_end - timedelta(seconds=20))
            price_point = profile.price_on(day)
            writer.add(
                "dwd_interaction_cart_event_di",
                {
                    "cart_event_id": cart_event_id,
                    "event_no": f"CART{cart_event_id}",
                    "event_date_key": date_key(day),
                    "user_sk": user["user_sk"],
                    "user_id": user["user_id"],
                    "device_id": device_id,
                    "session_id": session_id,
                    "shop_sk": profile.shop["shop_sk"],
                    "shop_id": profile.shop["shop_id"],
                    "sku_sk": profile.sku["sku_sk"],
                    "sku_id": profile.sku["sku_id"],
                    "spu_sk": profile.spu["spu_sk"],
                    "spu_id": profile.spu["spu_id"],
                    "category_sk": profile.category["category_sk"],
                    "category_id": profile.category["category_id"],
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "cart_event_type": "加入",
                    "cart_source": "商品详情页",
                    "sku_qty_delta": 1,
                    "cart_sku_qty_after": 1,
                    "sku_unit_price": price_point.sale_price,
                    "currency_code": "CNY",
                    "event_time": cart_time,
                    "biz_date": day,
                }
                | fact_audit(f"cart:{cart_event_id}", batch_id),
            )
            order_time = min(session_end + timedelta(seconds=30), ctx.data_end_time)
            conversion_intents.append(
                ConversionIntent(
                    order_time=order_time,
                    session_id=session_id,
                    user=user,
                    channel=channel,
                    region=region,
                    primary_sku_id=int(profile.sku["sku_id"]),
                    line_count=line_count_by_session[session_index],
                )
            )
            cart_local += 1
        elif user is not None and rng.random() < 0.08:
            favor_event_id = date_key(day) * 1_000_000 + favor_local
            writer.add(
                "dwd_interaction_favor_event_di",
                {
                    "favor_event_id": favor_event_id,
                    "event_no": f"FAVOR{favor_event_id}",
                    "event_date_key": date_key(day),
                    "user_sk": user["user_sk"],
                    "user_id": user["user_id"],
                    "device_id": device_id,
                    "session_id": session_id,
                    "shop_sk": profile.shop["shop_sk"],
                    "shop_id": profile.shop["shop_id"],
                    "sku_sk": profile.sku["sku_sk"],
                    "sku_id": profile.sku["sku_id"],
                    "spu_sk": profile.spu["spu_sk"],
                    "spu_id": profile.spu["spu_id"],
                    "channel_sk": channel["channel_sk"],
                    "channel_code": channel["channel_code"],
                    "favor_target_type": "商品",
                    "favor_event_type": "收藏",
                    "event_time": session_end,
                    "biz_date": day,
                }
                | fact_audit(f"favor:{favor_event_id}", batch_id),
            )
            favor_local += 1

        entry_page = pages[0]
        exit_page = pages[-1]
        writer.add(
            "dwd_traffic_session_di",
            {
                "session_fact_id": session_fact_id,
                "session_id": session_id,
                "session_date_key": date_key(day),
                "user_sk": user["user_sk"] if user else UNKNOWN_SK,
                "user_id": user["user_id"] if user else None,
                "device_id": device_id,
                "channel_sk": channel["channel_sk"],
                "channel_code": channel["channel_code"],
                "entry_page_sk": entry_page["page_sk"],
                "entry_page_id": entry_page["page_id"],
                "exit_page_sk": exit_page["page_sk"],
                "exit_page_id": exit_page["page_id"],
                "region_sk": region["region_sk"] if region else UNKNOWN_SK,
                "region_code": region["region_code"] if region else None,
                "client_type": channel["platform_type"],
                "app_version": "8.6.0"
                if channel["channel_code"] == "APP"
                else None,
                "os_type": "Android" if session_index % 2 == 0 else "iOS",
                "ip_masked": f"10.{session_index % 255}.***.***",
                "page_view_count": session_view_count,
                "search_count": session_search_count,
                "session_duration_sec": max(
                    0,
                    int((session_end - session_start).total_seconds()),
                ),
                "is_bounce": int(session_view_count == 1),
                "session_start_time": session_start,
                "session_end_time": session_end,
                "biz_date": day,
            }
            | fact_audit(f"session:{session_fact_id}", batch_id),
        )
    return conversion_intents


def _order_line_counts(target: int, rng: random.Random) -> list[int]:
    counts: list[int] = []
    remaining = target
    while remaining:
        draw = rng.random()
        desired = 1 if draw < 0.58 else 2 if draw < 0.9 else 3
        count = min(desired, remaining)
        counts.append(count)
        remaining -= count
    return counts


def _spread(total: int, buckets: int, minimum: int) -> list[int]:
    if buckets == 0:
        return []
    if total < buckets * minimum:
        raise ValueError("总量小于每个分桶的最小值")
    values = [minimum] * buckets
    remaining = total - sum(values)
    for index in range(remaining):
        values[index % buckets] += 1
    return values


def _even_indexes(total: int, selected: int) -> list[int]:
    if selected == 0:
        return []
    return [min(total - 1, index * total // selected) for index in range(selected)]


def _long_tail_index(rng: random.Random, size: int, exponent: float) -> int:
    return min(size - 1, int((rng.random() ** exponent) * size))


def _choose_channel(refs: ReferenceData, rng: random.Random) -> dict:
    weights = {
        "APP": 42,
        "H5": 22,
        "PC": 17,
        "MINI_PROGRAM": 13,
        "SEM": 6,
        "OFFLINE": 0,
    }
    return rng.choices(
        refs.channels,
        weights=[weights.get(str(row["channel_code"]), 1) for row in refs.channels],
        k=1,
    )[0]


def _page_sequence(
    refs: ReferenceData,
    count: int,
    is_conversion: bool,
) -> list[dict]:
    if is_conversion:
        base = ["HOME", "SEARCH", "PRODUCT", "CART", "ORDER"]
    else:
        base = ["HOME", "SEARCH", "PRODUCT", "SHOP"]
    return [refs.pages_by_id[base[min(index, len(base) - 1)]] for index in range(count)]

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
    end_of_day,
    fact_audit,
    version_at,
)
from ..timeline import BusinessState, ConversionIntent


def generate_day(
    ctx: RunContext,
    refs: ReferenceData,
    state: BusinessState,
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
    fulfillment_shop_counts: dict[tuple[int, int], int] = {}
    for active_profile in active_profiles:
        shop_id = int(active_profile.shop["shop_id"])
        active_shop_counts[shop_id] = active_shop_counts.get(shop_id, 0) + 1
        warehouse_id = int(
            refs.warehouse_for_profile(active_profile)["warehouse_id"]
        )
        fulfillment_key = (warehouse_id, shop_id)
        fulfillment_shop_counts[fulfillment_key] = (
            fulfillment_shop_counts.get(fulfillment_key, 0) + 1
        )
    eligible_profiles_by_lines = {
        line_count: [
            profile
            for profile in active_profiles
            if active_shop_counts[int(profile.shop["shop_id"])] >= line_count
        ]
        for line_count in (1, 2, 3)
    }
    eligible_profiles_by_fulfillment: dict[
        tuple[int, int],
        list,
    ] = {}
    for active_profile in active_profiles:
        warehouse_id = int(
            refs.warehouse_for_profile(active_profile)["warehouse_id"]
        )
        shop_id = int(active_profile.shop["shop_id"])
        maximum_lines = min(
            3,
            fulfillment_shop_counts[(warehouse_id, shop_id)],
        )
        for line_count in range(1, maximum_lines + 1):
            eligible_profiles_by_fulfillment.setdefault(
                (warehouse_id, line_count),
                [],
            ).append(active_profile)
    line_counts = _order_line_counts(order_detail_target, rng)
    session_count = max(
        len(line_counts),
        1 if page_view_count else 0,
        ceil(page_view_count / 3.2),
    )
    if page_view_count < session_count:
        raise ValueError(
            f"页面访问量不足以承载会话 day={day} "
            f"views={page_view_count} sessions={session_count}"
        )
    conversion_indexes = sorted(rng.sample(range(session_count), len(line_counts)))
    view_counts = _session_lengths(
        page_view_count,
        session_count,
        set(conversion_indexes),
        rng,
    )
    search_counts = _search_counts(search_count, session_count, rng)
    line_count_by_session = dict(zip(conversion_indexes, line_counts, strict=True))
    conversion_intents: list[ConversionIntent] = []
    day_active_users = refs.active_users(datetime.combine(day, datetime.min.time()))
    if not day_active_users:
        raise ValueError(f"{day} 没有已注册用户，无法生成行为")
    search_local = 1
    click_local = 1
    page_view_local = 1
    cart_local = 1
    favor_local = 1
    day_cutoff = min(end_of_day(day), ctx.data_end_time)

    for session_index in range(session_count):
        session_local = session_index + 1
        session_fact_id = date_key(day) * 1_000_000 + session_local
        session_id = f"S{session_fact_id}"
        is_conversion = session_index in line_count_by_session
        is_guest = not is_conversion and rng.random() < 0.27
        current_user = day_active_users[
            _long_tail_index(rng, len(day_active_users), 1.45)
        ]
        maximum_second = int(
            (
                day_cutoff - datetime.combine(day, datetime.min.time())
            ).total_seconds()
        )
        start_second = _session_start_second(rng, maximum_second)
        session_start = datetime.combine(day, datetime.min.time()) + timedelta(
            seconds=start_second
        )
        session_start = min(session_start, day_cutoff)
        user = (
            version_at(
                refs.user_versions,
                int(current_user["user_id"]),
                session_start,
            )
            if not is_guest
            else None
        )
        channel = _choose_channel(refs, rng, is_conversion)
        region = (
            refs.regions_by_district.get(str(user.get("district_code")))
            if user and user.get("district_code") is not None
            else None
        )
        required_lines = line_count_by_session.get(session_index, 1)
        eligible_profiles = eligible_profiles_by_lines[required_lines]
        if is_conversion:
            service_warehouse_id = int(
                refs.service_warehouse(region)["warehouse_id"]
            )
            eligible_profiles = eligible_profiles_by_fulfillment.get(
                (service_warehouse_id, required_lines),
                [],
            )
        if not eligible_profiles:
            raise ValueError(
                f"{day} 没有可承载 {required_lines} 个订单行的商品"
            )
        profile = _choose_profile(eligible_profiles, day, rng)
        if user is not None:
            user_id = int(user["user_id"])
            state.user_session_counts[user_id] = (
                state.user_session_counts.get(user_id, 0) + 1
            )
            root_category = str(profile.category["root_category_name"])
            category_counts = state.user_category_counts.setdefault(user_id, {})
            category_counts[root_category] = category_counts.get(root_category, 0) + 1
            state.user_last_active_at[user_id] = session_start
        client = _client_attributes(str(channel["channel_code"]), rng)
        device_id = (
            f"USERDEV{user['user_id']}"
            if user
            else f"GUESTDEV{date_key(day)}{session_local:06d}"
        )
        session_search_count = search_counts[session_index]
        search_ids: list[int] = []
        previous_keyword: str | None = None
        for search_index in range(session_search_count):
            search_id = date_key(day) * 1_000_000 + search_local
            search_time = min(
                session_start + timedelta(seconds=20 + search_index * 35),
                day_cutoff,
            )
            keyword, is_no_result = _search_keyword(
                profile,
                rng,
                previous_keyword,
            )
            previous_keyword = keyword
            result_count = 0 if is_no_result else 1 + int(rng.paretovariate(1.8) * 8)
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
                    "result_total_count": min(result_count, 500),
                    "is_no_result": int(is_no_result),
                    "is_search_success": int(not is_no_result),
                    "event_time": search_time,
                    "biz_date": day,
                }
                | fact_audit(f"search:{search_id}", batch_id),
            )
            search_ids.append(search_id)
            click_count = 0
            if not is_no_result and (is_conversion or rng.random() < 0.64):
                click_count = rng.choices([1, 2, 3], [82, 15, 3], k=1)[0]
            for click_index in range(click_count):
                click_profile = (
                    profile
                    if click_index == 0
                    else _choose_profile(active_profiles, day, rng)
                )
                click_id = date_key(day) * 1_000_000 + click_local
                click_time = min(
                    search_time + timedelta(seconds=5 + click_index * 9),
                    day_cutoff,
                )
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
                        "click_sku_sk": click_profile.sku["sku_sk"],
                        "click_sku_id": click_profile.sku["sku_id"],
                        "click_spu_sk": click_profile.spu["spu_sk"],
                        "click_spu_id": click_profile.spu["spu_id"],
                        "click_shop_sk": click_profile.shop["shop_sk"],
                        "click_shop_id": click_profile.shop["shop_id"],
                        "click_category_sk": click_profile.category["category_sk"],
                        "click_category_id": click_profile.category["category_id"],
                        "click_rank": min(100, 1 + int(rng.paretovariate(2.4) * 2)),
                        "event_time": click_time,
                        "biz_date": day,
                    }
                    | fact_audit(f"search-click:{click_id}", batch_id),
                )
                click_local += 1
            search_local += 1

        session_view_count = view_counts[session_index]
        pages = _page_sequence(
            refs,
            session_view_count,
            is_conversion,
            session_search_count > 0,
            rng,
        )
        last_page = None
        for view_index, page in enumerate(pages):
            page_view_id = date_key(day) * 1_000_000 + page_view_local
            event_time = min(
                session_start + timedelta(seconds=view_index * 35),
                day_cutoff,
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
                    "app_version": client["app_version"],
                    "os_type": client["os_type"],
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

        duration_seconds = max(
            8 if session_view_count == 1 else 20,
            session_view_count * rng.randint(24, 58),
            session_search_count * 55,
        )
        session_end = min(
            session_start + timedelta(seconds=duration_seconds),
            day_cutoff,
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
            order_time = min(session_end + timedelta(seconds=30), day_cutoff)
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
                "app_version": client["app_version"],
                "os_type": client["os_type"],
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


def _session_lengths(
    total: int,
    session_count: int,
    conversion_indexes: set[int],
    rng: random.Random,
) -> list[int]:
    values = [5 if index in conversion_indexes else 1 for index in range(session_count)]
    remaining = total - sum(values)
    if remaining < 0:
        raise ValueError("页面访问量不足以承载转化路径")
    candidates = list(range(session_count))
    while remaining:
        index = rng.choice(candidates)
        values[index] += 1
        remaining -= 1
        if values[index] >= 12:
            candidates.remove(index)
            if not candidates and remaining:
                raise ValueError("会话长度上限不足以承载页面访问量")
    return values


def _search_counts(total: int, session_count: int, rng: random.Random) -> list[int]:
    values = [0] * session_count
    candidates = list(range(session_count))
    for _ in range(total):
        index = rng.choice(candidates)
        values[index] += 1
        if values[index] >= 5:
            candidates.remove(index)
            if not candidates and sum(values) < total:
                raise ValueError("单会话搜索次数上限不足")
    return values


def _long_tail_index(rng: random.Random, size: int, exponent: float) -> int:
    return min(size - 1, int((rng.random() ** exponent) * size))


def _choose_channel(
    refs: ReferenceData,
    rng: random.Random,
    is_conversion: bool,
) -> dict:
    weights = (
        {
            "APP": 52,
            "H5": 15,
            "PC": 14,
            "MINI_PROGRAM": 17,
            "SEM": 2,
            "OFFLINE": 0,
        }
        if is_conversion
        else {
            "APP": 39,
            "H5": 24,
            "PC": 14,
            "MINI_PROGRAM": 15,
            "SEM": 8,
            "OFFLINE": 0,
        }
    )
    return rng.choices(
        refs.channels,
        weights=[weights.get(str(row["channel_code"]), 1) for row in refs.channels],
        k=1,
    )[0]


def _page_sequence(
    refs: ReferenceData,
    count: int,
    is_conversion: bool,
    has_search: bool,
    rng: random.Random,
) -> list[dict]:
    if is_conversion:
        entry = "SEARCH" if has_search else rng.choice(["HOME", "CATEGORY", "PRODUCT"])
        middle_count = count - 5
        middle = rng.choices(
            ["CATEGORY", "SEARCH", "PRODUCT", "SHOP"],
            [16, 18 if has_search else 6, 54, 12],
            k=middle_count,
        )
        page_ids = [entry, *middle, "PRODUCT", "CART", "ORDER", "CHECKOUT"]
        return [refs.pages_by_id[page_id] for page_id in page_ids]

    current = (
        "SEARCH"
        if has_search and rng.random() < 0.58
        else rng.choices(
            ["HOME", "CATEGORY", "PRODUCT", "SHOP"],
            [43, 18, 32, 7],
            k=1,
        )[0]
    )
    page_ids = [current]
    transitions = {
        "HOME": (["CATEGORY", "SEARCH", "PRODUCT", "SHOP"], [28, 31, 34, 7]),
        "CATEGORY": (["CATEGORY", "SEARCH", "PRODUCT", "HOME"], [18, 16, 58, 8]),
        "SEARCH": (["SEARCH", "PRODUCT", "CATEGORY", "HOME"], [18, 62, 12, 8]),
        "PRODUCT": (["PRODUCT", "SHOP", "SEARCH", "CATEGORY", "HOME"], [48, 14, 16, 14, 8]),
        "SHOP": (["PRODUCT", "SHOP", "SEARCH", "HOME"], [57, 18, 15, 10]),
    }
    while len(page_ids) < count:
        choices, weights = transitions[current]
        current = rng.choices(choices, weights=weights, k=1)[0]
        page_ids.append(current)
    return [refs.pages_by_id[page_id] for page_id in page_ids]


def _session_start_second(rng: random.Random, maximum_second: int) -> int:
    hours = list(range(24))
    weights = [
        1,
        1,
        1,
        1,
        2,
        4,
        8,
        14,
        22,
        27,
        31,
        38,
        48,
        43,
        35,
        32,
        34,
        42,
        57,
        72,
        83,
        76,
        47,
        20,
    ]
    eligible_hours = [hour for hour in hours if hour * 3600 <= maximum_second]
    eligible_weights = weights[: len(eligible_hours)]
    hour = rng.choices(eligible_hours, weights=eligible_weights, k=1)[0]
    upper = min(3599, maximum_second - hour * 3600)
    return hour * 3600 + rng.randrange(upper + 1)


def _client_attributes(channel_code: str, rng: random.Random) -> dict[str, str | None]:
    if channel_code == "APP":
        os_type = rng.choices(["Android", "iOS", "HarmonyOS"], [63, 29, 8], k=1)[0]
        version = rng.choices(
            ["8.7.1", "8.7.0", "8.6.2", "8.5.4"],
            [52, 28, 15, 5],
            k=1,
        )[0]
        return {"os_type": os_type, "app_version": version}
    if channel_code in {"H5", "MINI_PROGRAM"}:
        os_type = rng.choices(["Android", "iOS", "HarmonyOS"], [67, 27, 6], k=1)[0]
        return {"os_type": os_type, "app_version": None}
    if channel_code == "PC":
        os_type = rng.choices(["Windows", "macOS", "Linux"], [82, 16, 2], k=1)[0]
        return {"os_type": os_type, "app_version": None}
    return {"os_type": None, "app_version": None}


def _choose_profile(
    profiles: list,
    day: date,
    rng: random.Random,
):
    candidates = [
        profiles[_long_tail_index(rng, len(profiles), 2.35)] for _ in range(6)
    ]
    seasonal_roots = {
        1: {"家用电器", "食品饮料", "服饰鞋包"},
        2: {"美妆个护", "服饰鞋包", "运动户外"},
        6: {"手机数码", "电脑办公", "家用电器"},
        9: {"电脑办公", "母婴玩具", "服饰鞋包"},
        11: {"手机数码", "家用电器", "美妆个护"},
        12: {"食品饮料", "家居家装", "服饰鞋包"},
    }
    seasonal = seasonal_roots.get(day.month, set())
    return rng.choices(
        candidates,
        weights=[
            (1.8 if str(profile.category["root_category_name"]) in seasonal else 1.0)
            * (0.62 if int(profile.shop.get("is_self_operated") or 0) else 1.0)
            for profile in candidates
        ],
        k=1,
    )[0]


def _search_keyword(
    profile,
    rng: random.Random,
    previous_keyword: str | None,
) -> tuple[str, bool]:
    brand = str(profile.brand["brand_name"]) if profile.brand else ""
    root = str(profile.category.get("root_category_name") or "")
    leaf = str(profile.category.get("category_name") or root)
    title = str(profile.spu["spu_name"])
    title_parts = [part for part in title.replace("/", " ").split() if len(part) >= 2]
    short_title = " ".join(title_parts[:2])[:32] or title[:24]
    if previous_keyword and rng.random() < 0.22:
        keyword = rng.choice([brand, leaf, short_title]) or leaf
    else:
        keyword = rng.choices(
            [brand, leaf, f"{brand} {leaf}".strip(), short_title, f"{leaf} 推荐"],
            [15, 27, 24, 28, 6],
            k=1,
        )[0]
    is_no_result = rng.random() < 0.075
    if is_no_result:
        keyword = rng.choice(
            [
                f"{keyword} 冷门型号{rng.randrange(1000, 9999)}",
                keyword[:-1] if len(keyword) > 2 else f"{keyword}x",
                f"{keyword} 已停产",
            ]
        )
    return keyword[:80], is_no_result

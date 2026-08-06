"""生成公共维度、主数据维度和用户标签桥表"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from faker import Faker
from sqlalchemy import Table

from ..support import (
    END_OF_TIME,
    UNKNOWN_ID,
    UNKNOWN_SK,
    TableWriter,
    dimension_audit,
    iter_dates,
    load_json_rows,
    start_of_day,
)
from ..settings import RunContext
from ..work_calendar import build_work_calendar

logger = logging.getLogger(__name__)

DAY_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
CHANNELS = (
    ("APP", "移动应用", "自有", "APP", "直接访问"),
    ("H5", "移动网页", "自有", "H5", "直接访问"),
    ("PC", "桌面网站", "自有", "PC", "直接访问"),
    ("MINI_PROGRAM", "微信小程序", "小程序", "MINI_PROGRAM", "社交"),
    ("OFFLINE", "线下门店", "线下", "OFFLINE", "线下"),
    ("SEM", "搜索广告", "付费", "ALL", "搜索"),
)
PAGES = (
    ("HOME", "首页", "首页", "流量", "/"),
    ("SEARCH", "搜索结果页", "搜索", "流量", "/search"),
    ("PRODUCT", "商品详情页", "商品", "商品", "/product/{spu_id}"),
    ("SHOP", "店铺首页", "店铺", "商品", "/shop/{shop_id}"),
    ("CART", "购物车", "购物车", "交易", "/cart"),
    ("ORDER", "订单确认页", "订单", "交易", "/order/confirm"),
    ("PAY", "支付页", "支付", "支付", "/pay/{pay_order_no}"),
)
USER_TAGS = (
    ("NEW_USER", "新客", "生命周期"),
    ("ACTIVE_USER", "活跃用户", "活跃度"),
    ("PRICE_SENSITIVE", "价格敏感", "消费偏好"),
    ("HIGH_VALUE", "高价值用户", "用户价值"),
    ("DIGITAL_LOVER", "数码偏好", "品类偏好"),
    ("FASHION_LOVER", "服饰偏好", "品类偏好"),
    ("FOOD_LOVER", "食品偏好", "品类偏好"),
    ("PARENTING", "母婴人群", "人群属性"),
)


def _scd(
    attributes: dict[str, Any],
    ctx: RunContext,
    start_time: datetime,
    end_time: datetime = END_OF_TIME,
    version_no: int = 1,
    is_current: int = 1,
) -> dict[str, Any]:
    return (
        attributes
        | {
            "effective_start_time": start_time,
            "effective_end_time": end_time,
            "version_no": version_no,
            "is_current": is_current,
            "is_deleted": attributes.get("is_deleted", 0),
        }
        | dimension_audit(attributes, ctx.initial_batch_id)
    )


def _type1(
    attributes: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    return attributes | dimension_audit(
        attributes,
        ctx.initial_batch_id,
    )


def _date_rows(ctx: RunContext):
    work_calendar = build_work_calendar(ctx.gen.start_date, ctx.gen.end_date)
    for day in iter_dates(ctx.gen.start_date, ctx.gen.end_date):
        iso = day.isocalendar()
        arrangement = work_calendar[day]
        yield {
            "date_key": day.year * 10000 + day.month * 100 + day.day,
            "full_date": day,
            "calendar_year": day.year,
            "calendar_quarter": (day.month - 1) // 3 + 1,
            "calendar_month": day.month,
            "year_month_code": day.strftime("%Y-%m"),
            "week_of_year": iso.week,
            "day_of_month": day.day,
            "day_of_week": day.weekday() + 1,
            "day_name_cn": DAY_NAMES[day.weekday()],
            "is_weekend": int(day.weekday() >= 5),
            "is_holiday": arrangement.is_holiday,
            "is_workday": arrangement.is_workday,
            "holiday_name": arrangement.holiday_name,
            "fiscal_year": day.year,
            "fiscal_quarter": (day.month - 1) // 3 + 1,
        }


def _channel_rows(ctx: RunContext):
    unknown = {
        "channel_sk": UNKNOWN_SK,
        "channel_code": "UNKNOWN",
        "channel_name": "未知渠道",
        "channel_group": "未知",
        "platform_type": "UNKNOWN",
        "traffic_source_type": "未知",
        "channel_status": 1,
        "is_deleted": 0,
    }
    yield _type1(unknown, ctx)
    for code, name, group, platform, source_type in CHANNELS:
        yield _type1(
            {
                "channel_code": code,
                "channel_name": name,
                "channel_group": group,
                "platform_type": platform,
                "traffic_source_type": source_type,
                "channel_status": 1,
                "is_deleted": 0,
            },
            ctx,
        )


def _page_rows(ctx: RunContext):
    yield _type1(
        {
            "page_sk": UNKNOWN_SK,
            "page_id": "UNKNOWN",
            "page_name": "未知页面",
            "page_type": "未知",
            "business_domain": "未知",
            "page_path_pattern": None,
            "page_status": 1,
            "is_deleted": 0,
        },
        ctx,
    )
    for page_id, name, page_type, domain, pattern in PAGES:
        yield _type1(
            {
                "page_id": page_id,
                "page_name": name,
                "page_type": page_type,
                "business_domain": domain,
                "page_path_pattern": pattern,
                "page_status": 1,
                "is_deleted": 0,
            },
            ctx,
        )


def _geo_rows(ctx: RunContext):
    effective_start = start_of_day(ctx.gen.start_date)
    unknown = {
        "region_sk": UNKNOWN_SK,
        "region_code": "UNKNOWN",
        "region_name": "未知区域",
        "region_level": 1,
        "parent_region_code": None,
        "country_code": "UNKNOWN",
        "country_name": "未知",
        "province_code": None,
        "province_name": None,
        "city_code": None,
        "city_name": None,
        "district_code": None,
        "district_name": None,
        "region_path": "未知区域",
        "zip_code": None,
        "region_status": 1,
        "is_deleted": 0,
    }
    yield _scd(unknown, ctx, datetime(1900, 1, 1))
    country = {
        "region_code": "CN",
        "region_name": "中国",
        "region_level": 1,
        "parent_region_code": None,
        "country_code": "CN",
        "country_name": "中国",
        "province_code": None,
        "province_name": None,
        "city_code": None,
        "city_name": None,
        "district_code": None,
        "district_name": None,
        "region_path": "中国",
        "zip_code": None,
        "region_status": 1,
        "is_deleted": 0,
    }
    yield _scd(country, ctx, effective_start)
    seeds = load_json_rows(ctx.gen.master_data_path("geo_regions.json"))
    for seed in seeds:
        names = [
            "中国",
            seed.get("province_name"),
            seed.get("city_name"),
            seed.get("district_name"),
        ]
        if seed["region_name"] not in names:
            names.append(seed["region_name"])
        row = {
            "region_code": str(seed["region_code"]),
            "region_name": seed["region_name"],
            "region_level": int(seed["region_level"]) + 1,
            "parent_region_code": seed.get("parent_region_code") or "CN",
            "country_code": "CN",
            "country_name": "中国",
            "province_code": seed.get("province_code"),
            "province_name": seed.get("province_name"),
            "city_code": seed.get("city_code"),
            "city_name": seed.get("city_name"),
            "district_code": seed.get("district_code"),
            "district_name": seed.get("district_name"),
            "region_path": "/".join(str(name) for name in names if name),
            "zip_code": seed.get("zip_code"),
            "region_status": int(seed.get("status", 1)),
            "is_deleted": 0,
        }
        yield _scd(row, ctx, effective_start)


def _brand_rows(ctx: RunContext):
    yield _type1(
        {
            "brand_sk": UNKNOWN_SK,
            "brand_id": UNKNOWN_ID,
            "brand_name": "未知品牌",
            "brand_name_en": "UNKNOWN",
            "brand_alias": None,
            "brand_logo_url": None,
            "brand_story": None,
            "country_code": None,
            "country_name": None,
            "first_letter": None,
            "brand_status": 1,
            "is_deleted": 0,
        },
        ctx,
    )
    for seed in load_json_rows(ctx.gen.master_data_path("brands.json")):
        row = {
            key: seed.get(key)
            for key in (
                "brand_id",
                "brand_name",
                "brand_name_en",
                "brand_alias",
                "brand_logo_url",
                "brand_story",
                "country_code",
                "country_name",
                "first_letter",
            )
        } | {"brand_status": int(seed.get("status", 1)), "is_deleted": 0}
        yield _type1(row, ctx)


def _payment_rows(ctx: RunContext):
    yield _type1(
        {
            "payment_type_sk": UNKNOWN_SK,
            "payment_type_code": "UNKNOWN",
            "payment_type_name": "未知支付方式",
            "payment_institution_code": None,
            "payment_institution_name": None,
            "is_online": 0,
            "is_installment": 0,
            "payment_type_status": 1,
            "is_deleted": 0,
        },
        ctx,
    )
    for seed in load_json_rows(ctx.gen.master_data_path("payment_types.json")):
        row = {
            "payment_type_code": seed["payment_type_code"],
            "payment_type_name": seed["payment_type_name"],
            "payment_institution_code": seed.get("channel_code"),
            "payment_institution_name": seed.get("channel_name"),
            "is_online": int(seed.get("is_online", 1)),
            "is_installment": int(seed.get("is_installment", 0)),
            "payment_type_status": int(seed.get("status", 1)),
            "is_deleted": 0,
        }
        yield _type1(row, ctx)


def _logistics_rows(ctx: RunContext):
    yield _type1(
        {
            "logistics_company_sk": UNKNOWN_SK,
            "logistics_company_id": UNKNOWN_ID,
            "logistics_company_code": "UNKNOWN",
            "logistics_company_name": "未知物流公司",
            "logistics_type": "未知",
            "service_phone": None,
            "is_trace_supported": 0,
            "logistics_company_status": 1,
            "is_deleted": 0,
        },
        ctx,
    )
    for seed in load_json_rows(ctx.gen.master_data_path("logistics_companies.json")):
        row = {
            "logistics_company_id": seed["logistics_company_id"],
            "logistics_company_code": seed["logistics_company_code"],
            "logistics_company_name": seed["logistics_company_name"],
            "logistics_type": seed.get("logistics_type"),
            "service_phone": seed.get("service_phone"),
            "is_trace_supported": int(seed.get("is_trace_supported", 1)),
            "logistics_company_status": int(seed.get("status", 1)),
            "is_deleted": 0,
        }
        yield _type1(row, ctx)


def _seller_and_shop_rows(ctx: RunContext):
    effective_start = start_of_day(ctx.gen.start_date)
    seeds = load_json_rows(ctx.gen.master_data_path("shops.json"))
    seller_rows = [
        _scd(
            {
                "seller_sk": UNKNOWN_SK,
                "seller_id": UNKNOWN_ID,
                "seller_name": "未知商家",
                "seller_type": "未知",
                "industry_type": None,
                "country_code": None,
                "province_code": None,
                "city_code": None,
                "settle_date": None,
                "seller_status": "正常",
                "is_deleted": 0,
            },
            ctx,
            datetime(1900, 1, 1),
        )
    ]
    seen_sellers: set[int] = set()
    for seed in seeds:
        seller_id = int(seed["seller_id"])
        if seller_id in seen_sellers:
            continue
        seen_sellers.add(seller_id)
        open_time = (
            datetime.fromisoformat(str(seed["open_time"]))
            if seed.get("open_time")
            else None
        )
        seller_rows.append(
            _scd(
                {
                    "seller_id": seller_id,
                    "seller_name": seed["seller_name"],
                    "seller_type": (
                        "平台自营"
                        if int(seed.get("is_self_operated", 0))
                        else "第三方商家"
                    ),
                    "industry_type": seed.get("industry_type"),
                    "country_code": None,
                    "province_code": seed.get("province_code"),
                    "city_code": seed.get("city_code"),
                    "settle_date": open_time.date() if open_time else None,
                    "seller_status": "正常",
                    "is_deleted": int(seed.get("is_deleted", 0)),
                },
                ctx,
                effective_start,
            )
        )

    shop_rows = [
        _scd(
            {
                "shop_sk": UNKNOWN_SK,
                "shop_id": UNKNOWN_ID,
                "shop_name": "未知店铺",
                "shop_type": "未知",
                "seller_id": UNKNOWN_ID,
                "industry_type": None,
                "open_time": None,
                "province_code": None,
                "city_code": None,
                "district_code": None,
                "is_self_operated": 0,
                "is_cross_border": 0,
                "shop_status": "营业",
                "is_deleted": 0,
            },
            ctx,
            datetime(1900, 1, 1),
        )
    ]
    for seed in seeds:
        open_time = (
            datetime.fromisoformat(str(seed["open_time"]))
            if seed.get("open_time")
            else None
        )
        shop_rows.append(
            _scd(
                {
                    "shop_id": int(seed["shop_id"]),
                    "shop_name": seed["shop_name"],
                    "shop_type": seed["shop_type"],
                    "seller_id": int(seed["seller_id"]),
                    "industry_type": seed.get("industry_type"),
                    "open_time": open_time,
                    "province_code": seed.get("province_code"),
                    "city_code": seed.get("city_code"),
                    "district_code": seed.get("district_code"),
                    "is_self_operated": int(seed.get("is_self_operated", 0)),
                    "is_cross_border": int(seed.get("is_cross_border", 0)),
                    "shop_status": seed.get("shop_status", "营业"),
                    "is_deleted": int(seed.get("is_deleted", 0)),
                },
                ctx,
                effective_start,
            )
        )
    return seller_rows, shop_rows


def _category_rows(ctx: RunContext):
    effective_start = start_of_day(ctx.gen.start_date)
    seeds = load_json_rows(ctx.gen.master_data_path("categories.json"))
    by_id = {int(row["category_id"]): row for row in seeds}
    levels = {"一级": 1, "二级": 2, "三级": 3}

    yield _scd(
        {
            "category_sk": UNKNOWN_SK,
            "category_id": UNKNOWN_ID,
            "category_name": "未知类目",
            "category_level": 1,
            "parent_category_id": None,
            "parent_category_name": None,
            "root_category_id": UNKNOWN_ID,
            "root_category_name": "未知类目",
            "category_path_ids": "0",
            "category_path_names": "未知类目",
            "is_leaf": 1,
            "sort_order": 0,
            "category_status": 1,
            "is_deleted": 0,
        },
        ctx,
        datetime(1900, 1, 1),
    )

    for seed in seeds:
        path_ids = [int(seed["category_id"])]
        parent_id = seed.get("parent_category_id")
        while parent_id:
            path_ids.append(int(parent_id))
            parent_id = by_id[int(parent_id)].get("parent_category_id")
        path_ids.reverse()
        path_names = [by_id[item]["category_name"] for item in path_ids]
        row = {
            "category_id": int(seed["category_id"]),
            "category_name": seed["category_name"],
            "category_level": levels[seed["category_level"]],
            "parent_category_id": seed.get("parent_category_id"),
            "parent_category_name": seed.get("parent_category_name"),
            "root_category_id": int(seed.get("root_category_id") or path_ids[0]),
            "root_category_name": seed.get("root_category_name") or path_names[0],
            "category_path_ids": "/".join(str(item) for item in path_ids),
            "category_path_names": "/".join(path_names),
            "is_leaf": int(seed.get("is_leaf", 0)),
            "sort_order": int(seed.get("sort_order", 0)),
            "category_status": int(seed.get("status", 1)),
            "is_deleted": 0,
        }
        yield _scd(
            row,
            ctx,
            effective_start,
        )


def _warehouse_rows(ctx: RunContext, shops: list[dict[str, Any]]):
    yield _scd(
        {
            "warehouse_sk": UNKNOWN_SK,
            "warehouse_id": UNKNOWN_ID,
            "warehouse_code": "UNKNOWN",
            "warehouse_name": "未知仓库",
            "warehouse_type": "未知",
            "owner_type": "未知",
            "owner_id": None,
            "country_code": None,
            "province_code": None,
            "city_code": None,
            "district_code": None,
            "address": None,
            "warehouse_status": 1,
            "is_deleted": 0,
        },
        ctx,
        datetime(1900, 1, 1),
    )
    for idx in range(ctx.gen.warehouse_count):
        shop = shops[idx % len(shops)]
        warehouse_id = 6_000_001 + idx
        row = {
            "warehouse_id": warehouse_id,
            "warehouse_code": f"WH{idx + 1:04d}",
            "warehouse_name": f"区域中心仓{idx + 1:02d}",
            "warehouse_type": "中心仓" if idx % 3 == 0 else "区域仓",
            "owner_type": "平台",
            "owner_id": None,
            "country_code": "CN",
            "province_code": shop.get("province_code"),
            "city_code": shop.get("city_code"),
            "district_code": shop.get("district_code"),
            "address": f"{shop.get('province_code') or ''}***仓储园区",
            "warehouse_status": 1,
            "is_deleted": 0,
        }
        yield _scd(row, ctx, start_of_day(ctx.gen.start_date))


def _user_rows(ctx: RunContext, region_codes: list[dict[str, Any]]):
    fake = Faker("zh_CN")
    fake.seed_instance(ctx.gen.seed)
    start_time = start_of_day(ctx.gen.start_date)
    total_seconds = max(
        1,
        int(
            (
                start_of_day(ctx.gen.end_date + timedelta(days=1)) - start_time
            ).total_seconds()
        ),
    )
    change_time = start_time + timedelta(seconds=total_seconds // 2)

    yield _scd(
        {
            "user_sk": UNKNOWN_SK,
            "user_id": UNKNOWN_ID,
            "user_name": "未知用户",
            "nick_name": "未知用户",
            "gender": "未知",
            "birthday": None,
            "phone": None,
            "email": None,
            "register_time": None,
            "register_channel_code": None,
            "register_source": None,
            "user_level": "0",
            "is_vip": 0,
            "province_code": None,
            "city_code": None,
            "district_code": None,
            "occupation": None,
            "income_level": None,
            "education_level": None,
            "marital_status": None,
            "user_status": "正常",
            "is_deleted": 0,
        },
        ctx,
        datetime(1900, 1, 1),
    )

    for idx in range(ctx.gen.user_count):
        user_id = 1_000_001 + idx
        region = region_codes[idx % len(region_codes)]
        name = fake.name()
        register_time = start_time - timedelta(
            days=1 + (idx * 37) % (365 * 5),
            seconds=(idx * 7919) % 86400,
        )
        base = {
            "user_id": user_id,
            "user_name": name[0] + "**",
            "nick_name": f"用户{user_id}",
            "gender": "男" if idx % 2 == 0 else "女",
            "birthday": fake.date_of_birth(minimum_age=18, maximum_age=65),
            "phone": f"13{idx % 10}****{idx % 10000:04d}",
            "email": f"u***{idx % 1000}@example.com",
            "register_time": register_time,
            "register_channel_code": CHANNELS[idx % len(CHANNELS)][0],
            "register_source": "自然注册",
            "user_level": str(idx % 5 + 1),
            "is_vip": int(idx % 5 >= 2),
            "province_code": region.get("province_code"),
            "city_code": region.get("city_code"),
            "district_code": region.get("district_code"),
            "occupation": ("互联网", "制造业", "教育", "服务业")[idx % 4],
            "income_level": ("3k-8k", "8k-15k", "15k-30k")[idx % 3],
            "education_level": ("大专", "本科", "硕士")[idx % 3],
            "marital_status": "已婚" if idx % 3 == 0 else "未婚",
            "user_status": "正常",
            "is_deleted": 0,
        }
        has_change = idx % 10 == 0 and change_time > start_time
        if not has_change:
            yield _scd(base, ctx, start_time)
            continue
        yield _scd(base, ctx, start_time, change_time, 1, 0)
        changed = base | {
            "user_level": str(min(5, int(base["user_level"]) + 1)),
            "is_vip": 1,
        }
        yield _scd(changed, ctx, change_time, END_OF_TIME, 2, 1)


def _tag_rows(ctx: RunContext):
    yield {
        "user_tag_sk": UNKNOWN_SK,
        "tag_code": "UNKNOWN",
        "tag_name": "未知标签",
        "tag_group": "未知",
        "tag_value_type": "BOOLEAN",
        "tag_description": "未知标签成员",
        "tag_status": 1,
        "load_batch_id": ctx.initial_batch_id,
    }
    for code, name, group in USER_TAGS:
        yield {
            "tag_code": code,
            "tag_name": name,
            "tag_group": group,
            "tag_value_type": "BOOLEAN",
            "tag_description": f"{name}模拟标签",
            "tag_status": 1,
            "load_batch_id": ctx.initial_batch_id,
        }


def _tag_relation_rows(
    ctx: RunContext,
    users: list[dict[str, Any]],
    tags: list[dict[str, Any]],
):
    active_tags = [row for row in tags if row["user_tag_sk"] != UNKNOWN_SK]
    for idx, user in enumerate(users):
        for offset in (0, 3):
            tag = active_tags[(idx + offset) % len(active_tags)]
            yield {
                "user_id": user["user_id"],
                "user_tag_sk": tag["user_tag_sk"],
                "tag_value": "1",
                "tag_score": "0.900000",
                "effective_start_time": start_of_day(ctx.gen.start_date),
                "effective_end_time": END_OF_TIME,
                "is_current": 1,
                "load_batch_id": ctx.initial_batch_id,
            }


def run(ctx: RunContext, tables: dict[str, Table]) -> None:
    with ctx.engine.connect() as conn:
        writer = TableWriter(
            ctx.loader,
            ctx.gen.batch_size,
            ctx.gen.stream_load_workers,
            ctx.gen.start_date,
            ctx.as_of_time,
        )
        writer.add_many("dim_date", _date_rows(ctx))
        writer.add_many("dim_channel_info", _channel_rows(ctx))
        writer.add_many("dim_page_info", _page_rows(ctx))
        writer.add_many("dim_geo_region_zip", _geo_rows(ctx))
        writer.add_many("dim_brand_info", _brand_rows(ctx))
        writer.add_many("dim_payment_type", _payment_rows(ctx))
        writer.add_many("dim_logistics_company", _logistics_rows(ctx))
        seller_rows, shop_rows = _seller_and_shop_rows(ctx)
        writer.add_many("dim_seller_info_zip", seller_rows)
        writer.add_many("dim_shop_info_zip", shop_rows)
        writer.add_many("dim_category_info_zip", _category_rows(ctx))
        writer.flush_all()

        actual_shops = [row for row in shop_rows if row["shop_id"] != UNKNOWN_ID]
        writer.add_many("dim_warehouse_info_zip", _warehouse_rows(ctx, actual_shops))
        district_regions = [
            row
            for row in load_json_rows(ctx.gen.master_data_path("geo_regions.json"))
            if int(row["region_level"]) >= 3
        ]
        writer.add_many("dim_user_info_zip", _user_rows(ctx, district_regions))
        writer.add_many("dim_user_tag_info", _tag_rows(ctx))
        writer.flush_all()

        users = [
            dict(row)
            for row in conn.execute(
                tables["dim_user_info_zip"]
                .select()
                .where(
                    tables["dim_user_info_zip"].c.is_current == 1,
                    tables["dim_user_info_zip"].c.user_id != UNKNOWN_ID,
                )
            ).mappings()
        ]
        tags = [
            dict(row)
            for row in conn.execute(tables["dim_user_tag_info"].select()).mappings()
        ]
        writer.add_many(
            "bridge_user_tag_relation_zip",
            _tag_relation_rows(ctx, users, tags),
        )
        counts = writer.flush_all()
    logger.info("公共维度生成完成 %s", counts)

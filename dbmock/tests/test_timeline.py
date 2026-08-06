from __future__ import annotations

import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from src.batches import behavior, commerce, products
from src.reference import PricePoint, ProductProfile, ReferenceData
from src.settings import RunContext
from src.support import END_OF_TIME, TableWriter
from src.timeline import (
    BusinessState,
    ConversionIntent,
    build_period_targets,
    month_periods,
)


class FakeLoader:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def load(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        self.rows[table_name].extend(dict(row) for row in rows)


class TimelineTest(unittest.TestCase):
    def test_period_targets_preserve_totals(self) -> None:
        config = SimpleNamespace(
            start_date=date(2024, 8, 6),
            end_date=date(2026, 8, 6),
            page_view_count=4_000_000,
            search_count=600_000,
            order_detail_count=100_000,
        )
        periods = month_periods(config.start_date, config.end_date)
        targets = build_period_targets(cast(Any, config), periods)
        self.assertEqual(sum(row.page_views for row in targets.values()), 4_000_000)
        self.assertEqual(sum(row.searches for row in targets.values()), 600_000)
        self.assertEqual(sum(row.order_details for row in targets.values()), 100_000)
        self.assertEqual(periods[0].key, "2024-08")
        self.assertEqual(periods[-1].key, "2026-08")

    def test_daily_flow_links_behavior_orders_and_inventory(self) -> None:
        day = date(2026, 8, 6)
        ctx = _context(day)
        refs = _references(day)
        state = BusinessState()
        loader = FakeLoader()
        writer = TableWriter(
            cast(Any, loader),
            10_000,
            1,
            day,
            cast(Any, ctx).as_of_time,
        )
        products.generate_price_events(
            cast(RunContext, ctx),
            refs,
            writer,
            day,
            "TEST-2026-08",
        )
        intents = behavior.generate_day(
            cast(RunContext, ctx),
            refs,
            state,
            writer,
            day,
            "TEST-2026-08",
            120,
            20,
            12,
        )
        commerce.generate_day(
            cast(RunContext, ctx),
            refs,
            state,
            writer,
            day,
            "TEST-2026-08",
            intents,
        )
        writer.flush_all()

        rows = loader.rows
        self.assertEqual(len(rows["dwd_traffic_page_view_di"]), 120)
        self.assertEqual(len(rows["dwd_traffic_search_di"]), 20)
        self.assertEqual(len(rows["dwd_trade_order_detail_di"]), 12)
        sessions = {
            row["session_id"] for row in rows["dwd_traffic_session_di"]
        }
        carts = {
            (row["session_id"], row["sku_id"])
            for row in rows["dwd_interaction_cart_event_di"]
            if row["cart_event_type"] == "加入"
        }
        for detail in rows["dwd_trade_order_detail_di"]:
            self.assertIn(detail["source_session_id"], sessions)
            self.assertIn(
                (detail["source_session_id"], detail["sku_id"]),
                carts,
            )
            self.assertGreater(detail["cost_amount"], 0)
        for position in state.inventory.values():
            self.assertGreaterEqual(position.on_hand, 0)
            self.assertGreaterEqual(position.reserved, 0)
            self.assertLessEqual(position.reserved, position.on_hand)
        self.assertGreaterEqual(
            len(rows["dwd_inventory_change_di"]),
            len(refs.profiles),
        )

    def test_behavior_events_stay_within_the_business_day(self) -> None:
        day = date(2026, 7, 31)
        ctx = _context(day)
        refs = _references(day)
        state = BusinessState()
        loader = FakeLoader()
        writer = TableWriter(
            cast(Any, loader),
            20_000,
            1,
            day,
            cast(Any, ctx).as_of_time,
        )

        intents = behavior.generate_day(
            cast(RunContext, ctx),
            refs,
            state,
            writer,
            day,
            "TEST-2026-07",
            10_000,
            500,
            300,
        )
        writer.flush_all()

        self.assertTrue(intents)
        self.assertTrue(all(intent.order_time.date() == day for intent in intents))
        for table_name in (
            "dwd_traffic_session_di",
            "dwd_traffic_page_view_di",
            "dwd_traffic_search_di",
            "dwd_traffic_search_click_di",
            "dwd_interaction_cart_event_di",
            "dwd_interaction_favor_event_di",
        ):
            for row in loader.rows[table_name]:
                event_time = row.get("event_time") or row["session_end_time"]
                self.assertEqual(event_time.date(), row["biz_date"])

    def test_cross_month_facts_are_loaded_when_the_event_becomes_due(self) -> None:
        july_day = date(2026, 7, 31)
        august_day = date(2026, 8, 1)
        as_of_time = datetime(2026, 8, 7, 23, 59, 59)
        ctx = _range_context(july_day, as_of_time.date(), as_of_time)
        refs = _references(july_day)
        state = BusinessState()
        loader = FakeLoader()
        july_writer = TableWriter(
            cast(Any, loader),
            10_000,
            1,
            july_day,
            as_of_time,
        )
        intent = _conversion_intent(refs, datetime(2026, 7, 31, 23, 58))

        commerce.generate_day(
            cast(RunContext, ctx),
            refs,
            state,
            july_writer,
            july_day,
            "TEST-2026-07",
            [intent],
        )
        july_writer.flush_all()

        self.assertEqual(loader.rows["dwd_trade_pay_detail_di"], [])
        self.assertEqual(
            [
                row["after_order_status"]
                for row in loader.rows["dwd_trade_order_status_event_di"]
            ],
            ["CREATED"],
        )
        self.assertTrue(state.pending_facts)
        self.assertTrue(
            all(fact.event_time > datetime(2026, 7, 31, 23, 59, 59, 999999) for fact in state.pending_facts)
        )

        august_writer = TableWriter(
            cast(Any, loader),
            10_000,
            1,
            july_day,
            as_of_time,
        )
        commerce.generate_day(
            cast(RunContext, ctx),
            refs,
            state,
            august_writer,
            august_day,
            "TEST-2026-08",
            [],
        )
        august_writer.flush_all()

        pay_rows = loader.rows["dwd_trade_pay_detail_di"]
        self.assertEqual(len(pay_rows), 1)
        self.assertEqual(pay_rows[0]["biz_date"], august_day)
        self.assertEqual(pay_rows[0]["load_batch_id"], "TEST-2026-08")
        august_statuses = [
            row
            for row in loader.rows["dwd_trade_order_status_event_di"]
            if row["biz_date"] == august_day
        ]
        self.assertTrue(august_statuses)
        self.assertTrue(
            all(row["load_batch_id"] == "TEST-2026-08" for row in august_statuses)
        )

    def test_final_cutoff_keeps_future_order_events_pending(self) -> None:
        day = date(2026, 7, 31)
        as_of_time = datetime(2026, 7, 31, 23, 59)
        ctx = _range_context(day, day, as_of_time)
        refs = _references(day)
        state = BusinessState()
        loader = FakeLoader()
        writer = TableWriter(
            cast(Any, loader),
            10_000,
            1,
            day,
            as_of_time,
        )

        commerce.generate_day(
            cast(RunContext, ctx),
            refs,
            state,
            writer,
            day,
            "TEST-2026-07",
            [_conversion_intent(refs, datetime(2026, 7, 31, 23, 58))],
        )
        writer.flush_all()

        self.assertEqual(loader.rows["dwd_trade_pay_detail_di"], [])
        self.assertEqual(
            [
                row["after_order_status"]
                for row in loader.rows["dwd_trade_order_status_event_di"]
            ],
            ["CREATED"],
        )
        self.assertTrue(state.pending_facts)
        self.assertTrue(
            all(fact.event_time > as_of_time for fact in state.pending_facts)
        )


def _context(day: date) -> SimpleNamespace:
    as_of_time = datetime.combine(day, datetime.max.time())
    return SimpleNamespace(
        gen=SimpleNamespace(seed=42, start_date=day, end_date=day),
        as_of_time=as_of_time,
        data_end_time=as_of_time,
    )


def _range_context(
    start_date: date,
    end_date: date,
    as_of_time: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        gen=SimpleNamespace(seed=42, start_date=start_date, end_date=end_date),
        as_of_time=as_of_time,
        data_end_time=as_of_time,
    )


def _conversion_intent(
    refs: ReferenceData,
    order_time: datetime,
) -> ConversionIntent:
    return ConversionIntent(
        order_time=order_time,
        session_id="CROSS-MONTH-SESSION",
        user=refs.current_users[0],
        channel=refs.channels[0],
        region=next(iter(refs.regions_by_district.values())),
        primary_sku_id=int(refs.profiles[0].sku["sku_id"]),
        line_count=1,
    )


def _references(day: date) -> ReferenceData:
    user = {
        "user_sk": 1,
        "user_id": 1,
        "user_name": "用**",
        "phone": "138****0000",
        "birthday": date(1990, 1, 1),
        "register_time": datetime(2020, 1, 1),
        "district_code": "110101",
        "effective_start_time": datetime(2020, 1, 1),
        "effective_end_time": END_OF_TIME,
        "is_current": 1,
    }
    shop = {
        "shop_sk": 1,
        "shop_id": 1,
        "seller_id": 1,
        "is_cross_border": 0,
        "is_self_operated": 0,
        "province_code": "110000",
    }
    seller = {"seller_sk": 1, "seller_id": 1}
    category = {
        "category_sk": 1,
        "category_id": 1,
        "category_name": "测试类目",
        "root_category_name": "手机数码",
    }
    brand = {"brand_sk": 1, "brand_id": 1, "brand_name": "测试品牌"}
    profiles = []
    for index in range(3):
        sku_id = index + 1
        point = PricePoint(
            effective_date=day,
            list_price=Decimal("120.0000"),
            sale_price=Decimal("100.0000"),
            cost_price=Decimal("65.0000"),
            reason_code="INITIAL",
            reason_description="商品上架定价",
        )
        profiles.append(
            ProductProfile(
                sku={"sku_sk": sku_id, "sku_id": sku_id},
                spu={
                    "spu_sk": sku_id,
                    "spu_id": sku_id,
                    "spu_name": f"测试商品{sku_id}",
                    "is_presale": 0,
                    "weight_kg": Decimal("0.500"),
                },
                shop=shop,
                category=category,
                brand=brand,
                listing_date=day,
                warning_stock_qty=10,
                initial_stock_qty=30,
                price_points=(point,),
            )
        )
    pages = {
        page_id: {"page_sk": index + 1, "page_id": page_id}
        for index, page_id in enumerate(
            (
                "HOME",
                "SEARCH",
                "CATEGORY",
                "PRODUCT",
                "SHOP",
                "CART",
                "ORDER",
                "CHECKOUT",
            )
        )
    }
    promotion = {
        "promotion_version_sk": 1,
        "promotion_id": 1,
        "rule_version_no": 1,
        "promotion_type": "满减",
        "threshold_amount": Decimal("50"),
        "discount_amount": Decimal("5"),
        "discount_rate": None,
        "max_discount_amount": None,
        "activity_start_time": datetime.combine(day, datetime.min.time()),
        "activity_end_time": datetime.combine(
            day + timedelta(days=1),
            datetime.min.time(),
        ),
    }
    coupon = {
        "coupon_template_version_sk": 1,
        "coupon_template_id": 1,
        "threshold_amount": Decimal("50"),
        "discount_amount": Decimal("3"),
        "discount_rate": None,
        "max_discount_amount": None,
        "use_start_time": datetime.combine(day, datetime.min.time()),
        "use_end_time": datetime.combine(
            day + timedelta(days=1),
            datetime.min.time(),
        ),
    }
    return ReferenceData(
        user_versions={1: [user]},
        current_users=[user],
        user_registration_times=[user["register_time"]],
        tags_by_code={},
        user_tag_relations={},
        shops=[shop],
        shop_by_id={1: shop},
        sellers_by_id={1: seller},
        channels=[
            {
                "channel_sk": 1,
                "channel_code": "APP",
                "platform_type": "APP",
            }
        ],
        pages_by_id=pages,
        payments=[{"payment_type_sk": 1, "payment_type_code": "ALIPAY"}],
        logistics=[
            {"logistics_company_sk": 1, "logistics_company_id": 1}
        ],
        warehouses=[
            {
                "warehouse_sk": 1,
                "warehouse_id": 1,
                "warehouse_name": "测试仓",
                "district_code": "110101",
                "address": "测试仓地址",
            }
        ],
        regions_by_district={
            "110101": {
                "region_sk": 1,
                "region_code": "110101",
            }
        },
        promotions=[promotion],
        coupons=[coupon],
        promotion_scopes={
            1: [
                {
                    "scope_type": "ALL",
                    "scope_business_id": "*",
                    "is_excluded": 0,
                }
            ]
        },
        coupon_scopes={
            1: [
                {
                    "scope_type": "ALL",
                    "scope_business_id": "*",
                    "is_excluded": 0,
                }
            ]
        },
        profiles=profiles,
        profile_by_sku={int(row.sku["sku_id"]): row for row in profiles},
        profiles_by_listing_date={day: profiles},
        price_points_by_date={
            day: [(row, row.price_points[0]) for row in profiles]
        },
    )


if __name__ == "__main__":
    unittest.main()

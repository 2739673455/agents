"""按月编排所需的时间计划和跨月业务状态"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from .settings import GenerateConfig
from .support import iter_dates


@dataclass(frozen=True, slots=True)
class MonthPeriod:
    index: int
    key: str
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class PeriodTargets:
    page_views: int
    searches: int
    order_details: int


@dataclass(frozen=True, slots=True)
class ConversionIntent:
    order_time: datetime
    session_id: str
    user: dict[str, Any]
    channel: dict[str, Any]
    region: dict[str, Any] | None
    primary_sku_id: int
    line_count: int


@dataclass(slots=True)
class InventoryPosition:
    on_hand: int
    reserved: int
    in_transit: int
    unit_cost: Decimal

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


@dataclass(frozen=True, slots=True)
class ScheduledFact:
    table_name: str
    source_record_id: str
    event_time: datetime
    row: dict[str, Any]


@dataclass(slots=True)
class BusinessState:
    inventory: dict[int, InventoryPosition] = field(default_factory=dict)
    user_order_counts: dict[int, int] = field(default_factory=dict)
    pending_inventory_events: list[dict[str, Any]] = field(default_factory=list)
    pending_facts: list[ScheduledFact] = field(default_factory=list)
    generated_counts: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = {
            "inventory": {
                str(sku_id): {
                    **asdict(position),
                    "unit_cost": str(position.unit_cost),
                }
                for sku_id, position in self.inventory.items()
            },
            "user_order_counts": {
                str(user_id): count
                for user_id, count in self.user_order_counts.items()
            },
            "pending_inventory_events": [
                _serialize_value(event) for event in self.pending_inventory_events
            ],
            "pending_facts": [
                _serialize_value(asdict(fact)) for fact in self.pending_facts
            ],
            "generated_counts": self.generated_counts,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: str) -> BusinessState:
        payload = json.loads(value)
        return cls(
            inventory={
                int(sku_id): InventoryPosition(
                    on_hand=int(position["on_hand"]),
                    reserved=int(position["reserved"]),
                    in_transit=int(position["in_transit"]),
                    unit_cost=Decimal(str(position["unit_cost"])),
                )
                for sku_id, position in payload.get("inventory", {}).items()
            },
            user_order_counts={
                int(user_id): int(count)
                for user_id, count in payload.get("user_order_counts", {}).items()
            },
            pending_inventory_events=[
                _mapping(_deserialize_value(event))
                for event in payload.get("pending_inventory_events", [])
            ],
            pending_facts=[
                _scheduled_fact(_mapping(_deserialize_value(fact)))
                for fact in payload.get("pending_facts", [])
            ],
            generated_counts={
                str(name): int(count)
                for name, count in payload.get("generated_counts", {}).items()
            },
        )


def month_periods(start_date: date, end_date: date) -> list[MonthPeriod]:
    periods: list[MonthPeriod] = []
    current = start_date
    while current <= end_date:
        next_month = (
            current.replace(year=current.year + 1, month=1, day=1)
            if current.month == 12
            else current.replace(month=current.month + 1, day=1)
        )
        period_end = min(end_date, next_month - timedelta(days=1))
        periods.append(
            MonthPeriod(
                index=len(periods),
                key=f"{current:%Y-%m}",
                start_date=current,
                end_date=period_end,
            )
        )
        current = next_month
    return periods


def build_period_targets(
    config: GenerateConfig,
    periods: list[MonthPeriod],
) -> dict[str, PeriodTargets]:
    weights = [
        sum(_day_weight(day, config.start_date) for day in iter_dates(period.start_date, period.end_date))
        for period in periods
    ]
    page_views = _allocate(config.page_view_count, weights)
    searches = _allocate(config.search_count, weights)
    order_details = _allocate(config.order_detail_count, weights)
    return {
        period.key: PeriodTargets(
            page_views=page_views[index],
            searches=searches[index],
            order_details=order_details[index],
        )
        for index, period in enumerate(periods)
    }


def day_targets(total: int, period: MonthPeriod, start_date: date) -> dict[date, int]:
    days = list(iter_dates(period.start_date, period.end_date))
    values = _allocate(total, [_day_weight(day, start_date) for day in days])
    return dict(zip(days, values, strict=True))


def _day_weight(day: date, start_date: date) -> float:
    elapsed_years = (day - start_date).days / 365.25
    growth = 1.0 + elapsed_years * 0.12
    weekday = 1.12 if day.weekday() >= 5 else 1.0
    campaign = 1.0
    if day.month == 6 and 15 <= day.day <= 20:
        campaign = 2.2
    elif day.month == 11 and 8 <= day.day <= 12:
        campaign = 3.0
    elif day.month == 12 and 10 <= day.day <= 13:
        campaign = 1.8
    elif day.month in {1, 2} and day.day <= 7:
        campaign = 1.25
    return growth * weekday * campaign


def _allocate(total: int, weights: list[float]) -> list[int]:
    if not weights:
        return []
    weight_sum = sum(weights)
    exact = [total * weight / weight_sum for weight in weights]
    allocated = [int(value) for value in exact]
    remainder = total - sum(allocated)
    order = sorted(
        range(len(weights)),
        key=lambda index: exact[index] - allocated[index],
        reverse=True,
    )
    for index in order[:remainder]:
        allocated[index] += 1
    return allocated


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__dbmock_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__dbmock_type__": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__dbmock_type__": "decimal", "value": str(value)}
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _deserialize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_deserialize_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    value_type = value.get("__dbmock_type__")
    if value_type == "datetime":
        return datetime.fromisoformat(str(value["value"]))
    if value_type == "date":
        return date.fromisoformat(str(value["value"]))
    if value_type == "decimal":
        return Decimal(str(value["value"]))
    return {str(key): _deserialize_value(item) for key, item in value.items()}


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("检查点事件必须是对象")
    return {str(key): item for key, item in value.items()}


def _scheduled_fact(payload: dict[str, Any]) -> ScheduledFact:
    event_time = payload.get("event_time")
    row = payload.get("row")
    if not isinstance(event_time, datetime) or not isinstance(row, dict):
        raise ValueError("待处理事实检查点格式无效")
    return ScheduledFact(
        table_name=str(payload["table_name"]),
        source_record_id=str(payload["source_record_id"]),
        event_time=event_time,
        row={str(key): value for key, value in row.items()},
    )

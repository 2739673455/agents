"""数据生成配置"""

from __future__ import annotations

import os
import random
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import dotenv
from sqlalchemy import URL, Engine, create_engine

if TYPE_CHECKING:
    from .database import DorisStreamLoader

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"
BUSINESS_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")

dotenv.load_dotenv(ENV_FILE)


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _now() -> datetime:
    return datetime.now(tz=BUSINESS_TIMEZONE).replace(tzinfo=None)


def _today() -> date:
    return _now().date()


def _two_years_ago() -> date:
    today = _today()
    try:
        return today.replace(year=today.year - 2)
    except ValueError:
        return today.replace(year=today.year - 2, day=28)


@dataclass(slots=True)
class DorisConfig:
    host: str = field(
        default_factory=lambda: os.getenv("DB_HOST", "127.0.0.1")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("DB_PORT", "9030"))
    )
    http_port: int = field(
        default_factory=lambda: int(os.getenv("DB_HTTP_PORT", "8030"))
    )
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "root"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    database: str = field(
        default_factory=lambda: os.getenv("DB_NAME", "ecommerce")
    )

    @property
    def sqlalchemy_url(self) -> URL:
        return URL.create(
            drivername="mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )


@dataclass(slots=True)
class GenerateConfig:
    start_date: date = field(
        default_factory=lambda: date.fromisoformat(
            os.getenv("DBMOCK_START_DATE", _two_years_ago().isoformat())
        )
    )
    end_date: date = field(
        default_factory=lambda: date.fromisoformat(
            os.getenv("DBMOCK_END_DATE", _today().isoformat())
        )
    )
    batch_size: int = field(
        default_factory=lambda: _env_int("DBMOCK_BATCH_SIZE", 50_000)
    )
    seed: int = field(default_factory=lambda: _env_int("DBMOCK_SEED", 42))
    user_count: int = field(default_factory=lambda: _env_int("DBMOCK_USER_COUNT", 3000))
    spu_count: int = field(default_factory=lambda: _env_int("DBMOCK_SPU_COUNT", 30_000))
    promotion_count: int = field(
        default_factory=lambda: _env_int("DBMOCK_PROMOTION_COUNT", 50)
    )
    coupon_count: int = field(
        default_factory=lambda: _env_int("DBMOCK_COUPON_COUNT", 100)
    )
    order_detail_count: int = field(
        default_factory=lambda: _env_int("DBMOCK_ORDER_DETAIL_COUNT", 100000)
    )
    page_view_count: int = field(
        default_factory=lambda: _env_int("DBMOCK_PAGE_VIEW_COUNT", 30000)
    )
    search_count: int = field(
        default_factory=lambda: _env_int("DBMOCK_SEARCH_COUNT", 6000)
    )
    cart_events_per_user: int = field(
        default_factory=lambda: _env_int("DBMOCK_CART_EVENTS_PER_USER", 2)
    )
    favor_events_per_user: int = field(
        default_factory=lambda: _env_int("DBMOCK_FAVOR_EVENTS_PER_USER", 1)
    )
    warehouse_count: int = field(
        default_factory=lambda: _env_int("DBMOCK_WAREHOUSE_COUNT", 12)
    )
    data_dir: Path = field(default_factory=lambda: ROOT_DIR / "data")

    @property
    def catalog_product_source_system(self) -> str:
        return "PIM"

    @property
    def catalog_merchant_source_system(self) -> str:
        return "MERCHANT_CENTER"

    def master_data_path(self, filename: str) -> Path:
        return self.data_dir / filename

    @classmethod
    def smoke(cls) -> GenerateConfig:
        end_date = _today()
        return cls(
            start_date=end_date - timedelta(days=6),
            end_date=end_date,
            batch_size=50_000,
            user_count=20,
            spu_count=8,
            promotion_count=3,
            coupon_count=3,
            order_detail_count=60,
            page_view_count=80,
            search_count=20,
            cart_events_per_user=2,
            favor_events_per_user=1,
            warehouse_count=3,
        )

    def validate(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("DBMOCK_START_DATE 不能晚于 DBMOCK_END_DATE")
        if self.end_date > _today():
            raise ValueError("DBMOCK_END_DATE 不能晚于任务执行日期")
        positive_values = {
            "DBMOCK_BATCH_SIZE": self.batch_size,
            "DBMOCK_USER_COUNT": self.user_count,
            "DBMOCK_SPU_COUNT": self.spu_count,
            "DBMOCK_PROMOTION_COUNT": self.promotion_count,
            "DBMOCK_COUPON_COUNT": self.coupon_count,
            "DBMOCK_ORDER_DETAIL_COUNT": self.order_detail_count,
            "DBMOCK_PAGE_VIEW_COUNT": self.page_view_count,
            "DBMOCK_SEARCH_COUNT": self.search_count,
            "DBMOCK_WAREHOUSE_COUNT": self.warehouse_count,
            "DBMOCK_CART_EVENTS_PER_USER": self.cart_events_per_user,
            "DBMOCK_FAVOR_EVENTS_PER_USER": self.favor_events_per_user,
        }
        invalid = [name for name, value in positive_values.items() if value <= 0]
        if invalid:
            raise ValueError(f"以下配置必须大于 0: {', '.join(invalid)}")
        if self.order_detail_count < 20:
            raise ValueError("DBMOCK_ORDER_DETAIL_COUNT 不能小于 20")
        required_files = (
            "manifest.json",
            "brands.json",
            "categories.json",
            "geo_regions.json",
            "logistics_companies.json",
            "payment_types.json",
            "shops.json",
            "spus.jsonl",
            "skus.jsonl",
            "lineage.jsonl",
        )
        missing = [
            filename
            for filename in required_files
            if not (self.data_dir / filename).exists()
        ]
        if missing:
            raise ValueError(
                "data 目录不完整，请执行 uv run scripts/prepare_real_catalog.py: "
                + ", ".join(missing)
            )
        manifest = json.loads(
            (self.data_dir / "manifest.json").read_text(encoding="utf-8")
        )
        if (
            int(manifest.get("schema_version", 0)) != 4
            or manifest.get("source", {}).get("dataset_name") != "国内公开电商商品页"
        ):
            raise ValueError(
                "商品目录来源已过期，请重新执行 "
                "uv run scripts/prepare_real_catalog.py"
            )


@dataclass(slots=True)
class RunContext:
    db: DorisConfig
    gen: GenerateConfig
    batch_id: str
    as_of_time: datetime = field(default_factory=_now)
    engine: Engine = field(init=False)
    loader: DorisStreamLoader = field(init=False)
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        from .database import DorisStreamLoader

        self.gen.validate()
        self.engine = create_engine(
            self.db.sqlalchemy_url,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        self.loader = DorisStreamLoader(self.db, self.batch_id)
        self.rng = random.Random(self.gen.seed)

    @property
    def data_end_time(self) -> datetime:
        """本次构建允许的最大业务时间"""
        configured_end = datetime.combine(self.gen.end_date, time.max)
        return min(configured_end, self.as_of_time)

    def close(self) -> None:
        self.loader.close()
        self.engine.dispose()

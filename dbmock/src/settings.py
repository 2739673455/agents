"""数据生成全局配置"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import dotenv
from sqlalchemy import Engine, create_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"

dotenv.load_dotenv(ENV_FILE)

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]
BATCH_SIZE = 5000
SEED = 42

USER_INITIAL_COUNT = 1_000
USER_FINAL_COUNT = 3_000

SPU_TARGET_COUNT = 500
SKU_PER_SPU = 5

PROMOTION_TARGET_COUNT = 50
COUPON_TARGET_COUNT = 100

ORDER_DETAIL_TARGET_COUNT = 100_000

CART_EVENTS_PER_USER = 2
FAVOR_EVENTS_PER_USER = 1
PAGE_VIEW_EVENTS_PER_USER = 10
SEARCH_EVENTS_PER_USER = 2


def _today_iso() -> str:
    return date.today().isoformat()


def _three_years_ago_iso() -> str:
    today = date.today()
    try:
        return today.replace(year=today.year - 3).isoformat()
    except ValueError:
        # 处理闰日回退，例如 2024-02-29 回退到 2021-02-28
        return today.replace(year=today.year - 3, day=28).isoformat()


@dataclass(slots=True)
class DBConfig:
    host: str = DB_HOST
    port: int = DB_PORT
    user: str = DB_USER
    password: str = DB_PASSWORD
    database: str = DB_NAME

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(slots=True)
class GenerateConfig:
    batch_size: int = BATCH_SIZE
    seed: int = SEED
    start_date: str = field(default_factory=_three_years_ago_iso)
    end_date: str = field(default_factory=_today_iso)
    seed_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent / "seeds"
    )


@dataclass(slots=True)
class RunContext:
    db: DBConfig
    gen: GenerateConfig
    engine: Engine = field(init=False)
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.engine = create_engine(self.db.db_url, pool_pre_ping=True)
        self.rng = random.Random(self.gen.seed)

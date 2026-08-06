"""电商数仓模拟数据生成入口"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from src.generation import quality, support
from src.generation.batches import (
    behavior,
    commerce,
    dimensions,
    marketing,
    products,
    snapshots,
)
from src.settings import BUSINESS_TIMEZONE, DorisConfig, GenerateConfig, RunContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成电商数仓模拟数据")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="使用七天小数据集验证完整链路",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="只执行数据质量校验",
    )
    parser.add_argument(
        "--dimensions-only",
        action="store_true",
        help="只加载公共维度、SPU和SKU并执行维度质量校验",
    )
    return parser.parse_args()


def run(ctx: RunContext, args: argparse.Namespace) -> None:
    tables = support.reflect_tables(ctx.engine)

    if args.validate_only:
        quality.validate_database(ctx, tables)
        return

    with ctx.engine.connect() as conn:
        support.assert_empty(conn, tables)

    if args.dimensions_only:
        dimensions.run(ctx, tables)
        products.run_dimensions(ctx, tables)
        quality.validate_catalog_dimensions(ctx)
        logger.info("维度数据生成并校验完成 batch_id=%s", ctx.batch_id)
        return

    generators = [
        dimensions.run,
        products.run,
        marketing.run,
        commerce.run,
        behavior.run,
        snapshots.run,
    ]
    for generator in generators:
        logger.info("开始执行 %s", generator.__module__)
        generator(ctx, tables)

    quality.validate_database(ctx, tables)
    logger.info("全部数据生成并校验完成 batch_id=%s", ctx.batch_id)


def main() -> None:
    args = parse_args()
    gen = GenerateConfig.smoke() if args.smoke else GenerateConfig()
    batch_id = f"dbmock-{datetime.now(tz=BUSINESS_TIMEZONE):%Y%m%d%H%M%S}"
    ctx = RunContext(DorisConfig(), gen, batch_id)
    try:
        run(ctx, args)
    finally:
        ctx.close()


if __name__ == "__main__":
    main()

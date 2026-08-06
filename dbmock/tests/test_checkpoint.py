from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from src.checkpoint import CheckpointStore
from src.settings import RunContext
from src.timeline import (
    BusinessState,
    InventoryPosition,
    MonthPeriod,
    ScheduledFact,
)


class FakeContext:
    def __init__(self, data_dir: Path) -> None:
        self.run_id = "dbmock-test-run"
        self.catalog_hash = "catalog-hash"
        self.config_hash = "config-hash"
        self.as_of_time = datetime(2026, 8, 6, 14, 30)
        self.gen = SimpleNamespace(
            start_date=date(2026, 7, 31),
            end_date=date(2026, 8, 6),
            data_dir=data_dir,
        )

    def adopt_run(
        self,
        run_id: str,
        start_date: date,
        end_date: date,
        as_of_time: datetime,
    ) -> None:
        self.run_id = run_id
        self.gen.start_date = start_date
        self.gen.end_date = end_date
        self.as_of_time = as_of_time


class CheckpointStoreTest(unittest.TestCase):
    def test_json_checkpoint_resumes_latest_completed_period(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            ctx = FakeContext(data_dir)
            store = CheckpointStore(cast(RunContext, ctx))
            state = BusinessState(
                inventory={
                    1001: InventoryPosition(
                        on_hand=80,
                        reserved=5,
                        in_transit=0,
                        unit_cost=Decimal("35.5000"),
                    )
                },
                user_order_counts={2001: 3},
                pending_facts=[
                    ScheduledFact(
                        table_name="dwd_trade_order_status_event_di",
                        source_record_id="order-status:1:2",
                        event_time=datetime(2026, 8, 1, 0, 5),
                        row={
                            "biz_date": date(2026, 8, 1),
                            "approved_amount": Decimal("12.34"),
                        },
                    )
                ],
            )
            july = MonthPeriod(0, "2026-07", date(2026, 7, 31), date(2026, 7, 31))
            august = MonthPeriod(1, "2026-08", date(2026, 8, 1), date(2026, 8, 6))

            store.start_initialization()
            store.complete_initialization(state)
            store.start_period(july)
            store.complete_period(july, state, {"test_table": 12})

            status = store.run_status()
            self.assertEqual(status.completed_periods, 1)
            self.assertEqual(status.unfinished_periods, 0)
            self.assertEqual(status.last_period_end, july.end_date)

            resumed_ctx = FakeContext(data_dir)
            resumed_ctx.run_id = "new-run"
            resumed_ctx.gen.start_date = date(2026, 8, 1)
            resumed_ctx.gen.end_date = date(2026, 8, 7)
            resumed = CheckpointStore(cast(RunContext, resumed_ctx))
            self.assertTrue(resumed.adopt_resumable_run())
            self.assertEqual(resumed_ctx.run_id, ctx.run_id)
            self.assertEqual(resumed_ctx.gen.start_date, ctx.gen.start_date)
            self.assertEqual(resumed_ctx.gen.end_date, ctx.gen.end_date)
            checkpoint = resumed.latest_completed()
            self.assertIsNotNone(checkpoint)
            assert checkpoint is not None
            self.assertEqual(checkpoint.period_key, july.key)
            self.assertEqual(checkpoint.state.inventory[1001].on_hand, 80)
            pending_fact = checkpoint.state.pending_facts[0]
            self.assertEqual(
                pending_fact.table_name,
                "dwd_trade_order_status_event_di",
            )
            self.assertEqual(pending_fact.event_time, datetime(2026, 8, 1, 0, 5))
            self.assertEqual(pending_fact.row["biz_date"], date(2026, 8, 1))
            self.assertEqual(pending_fact.row["approved_amount"], Decimal("12.34"))

            resumed.start_period(august)
            resumed.fail_period(august, RuntimeError("测试失败"))
            failed_status = resumed.run_status()
            self.assertEqual(failed_status.completed_periods, 1)
            self.assertEqual(failed_status.unfinished_periods, 1)
            latest = resumed.latest_completed()
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual(latest.period_key, july.key)

            payload = json.loads(store.path.read_text(encoding="utf-8"))
            run = payload["runs"][0]
            self.assertIn("state", run["resume"])
            self.assertNotIn("state", run["periods"][july.key])
            self.assertEqual(
                run["periods"][july.key]["row_counts"],
                {"test_table": 12},
            )


if __name__ == "__main__":
    unittest.main()

"""本地 JSON 月度生成检查点"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .settings import BUSINESS_TIMEZONE, RunContext
from .timeline import BusinessState, MonthPeriod

CHECKPOINT_FILENAME = "generation_checkpoint.json"
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Checkpoint:
    period_key: str
    status: str
    state: BusinessState


@dataclass(frozen=True, slots=True)
class RunCheckpointStatus:
    completed_periods: int
    unfinished_periods: int
    last_period_end: date | None


class CheckpointStore:
    def __init__(self, ctx: RunContext, path: Path | None = None) -> None:
        self._ctx = ctx
        self._path = path or ctx.gen.data_dir / CHECKPOINT_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def latest_completed(self) -> Checkpoint | None:
        run = self._find_run(self._load(), self._ctx.run_id)
        if run is None:
            return None
        resume = run.get("resume")
        if not isinstance(resume, dict):
            return None
        period_key = str(resume["period_key"])
        periods = self._periods(run)
        period = periods.get(period_key)
        if not isinstance(period, dict) or period.get("status") != "COMPLETED":
            raise ValueError(f"本地检查点恢复状态异常: {self._path}")
        state = resume.get("state")
        if not isinstance(state, dict):
            raise ValueError(f"本地检查点缺少业务状态: {self._path}")
        return Checkpoint(
            period_key=period_key,
            status="COMPLETED",
            state=BusinessState.from_json(self._json_text(state)),
        )

    def adopt_resumable_run(self) -> bool:
        candidates = [
            run
            for run in self._runs(self._load())
            if run.get("catalog_hash") == self._ctx.catalog_hash
            and run.get("config_hash") == self._ctx.config_hash
            and self._is_resumable(run)
        ]
        if not candidates:
            return False
        run = max(candidates, key=self._updated_at)
        self._adopt(run)
        return True

    def adopt_latest_run(self) -> bool:
        candidates = [
            run
            for run in self._runs(self._load())
            if run.get("catalog_hash") == self._ctx.catalog_hash
            and run.get("config_hash") == self._ctx.config_hash
        ]
        if not candidates:
            return False
        run = max(candidates, key=self._updated_at)
        self._adopt(run)
        return True

    def run_status(self) -> RunCheckpointStatus:
        run = self._find_run(self._load(), self._ctx.run_id)
        if run is None:
            return RunCheckpointStatus(0, 0, None)
        return self._status(run)

    def start_initialization(self) -> None:
        self._write("INIT", None, None, "RUNNING", None, {})

    def complete_initialization(self, state: BusinessState) -> None:
        self._write("INIT", None, None, "COMPLETED", state, {})

    def start_period(self, period: MonthPeriod) -> None:
        self._write(
            period.key,
            period.start_date,
            period.end_date,
            "RUNNING",
            None,
            {},
        )

    def complete_period(
        self,
        period: MonthPeriod,
        state: BusinessState,
        row_counts: dict[str, int],
    ) -> None:
        self._write(
            period.key,
            period.start_date,
            period.end_date,
            "COMPLETED",
            state,
            row_counts,
        )

    def fail_period(self, period: MonthPeriod, error: Exception) -> None:
        self._write(
            period.key,
            period.start_date,
            period.end_date,
            "FAILED",
            None,
            {},
            str(error)[:2000],
        )

    def _write(
        self,
        period_key: str,
        period_start: date | None,
        period_end: date | None,
        status: str,
        state: BusinessState | None,
        row_counts: dict[str, int],
        error_message: str | None = None,
    ) -> None:
        payload = self._load()
        run = self._find_run(payload, self._ctx.run_id)
        updated_at = self._now().isoformat(timespec="microseconds")
        if run is None:
            run = {
                "run_id": self._ctx.run_id,
                "data_start_date": self._ctx.gen.start_date.isoformat(),
                "data_end_date": self._ctx.gen.end_date.isoformat(),
                "run_as_of_time": self._ctx.as_of_time.isoformat(
                    timespec="microseconds"
                ),
                "catalog_hash": self._ctx.catalog_hash,
                "config_hash": self._ctx.config_hash,
                "created_at": updated_at,
                "updated_at": updated_at,
                "periods": {},
                "resume": None,
            }
            self._runs(payload).append(run)
        periods = self._periods(run)
        periods[period_key] = {
            "period_key": period_key,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "status": status,
            "row_counts": row_counts,
            "error_message": error_message,
            "updated_at": updated_at,
        }
        if status == "COMPLETED":
            if state is None:
                raise ValueError("完成检查点必须包含可恢复业务状态")
            run["resume"] = {
                "period_key": period_key,
                "state": json.loads(state.to_json()),
            }
        run["updated_at"] = updated_at
        self._save(payload)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"schema_version": SCHEMA_VERSION, "runs": []}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"本地检查点读取失败: {self._path}") from error
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != SCHEMA_VERSION
            or not isinstance(payload.get("runs"), list)
        ):
            raise ValueError(f"本地检查点格式无效: {self._path}")
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.tmp")
        with temporary.open("w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, separators=(",", ":"))
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, self._path)

    def _adopt(self, run: dict[str, Any]) -> None:
        self._ctx.adopt_run(
            str(run["run_id"]),
            date.fromisoformat(str(run["data_start_date"])),
            date.fromisoformat(str(run["data_end_date"])),
            datetime.fromisoformat(str(run["run_as_of_time"])),
        )

    @staticmethod
    def _runs(payload: dict[str, Any]) -> list[dict[str, Any]]:
        runs = payload["runs"]
        if not isinstance(runs, list) or not all(
            isinstance(run, dict) for run in runs
        ):
            raise ValueError("本地检查点 runs 格式无效")
        return runs

    @staticmethod
    def _periods(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
        periods = run.get("periods")
        if not isinstance(periods, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in periods.items()
        ):
            raise ValueError("本地检查点 periods 格式无效")
        return periods

    @classmethod
    def _find_run(
        cls,
        payload: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any] | None:
        return next(
            (run for run in cls._runs(payload) if run.get("run_id") == run_id),
            None,
        )

    @classmethod
    def _is_resumable(cls, run: dict[str, Any]) -> bool:
        status = cls._status(run)
        data_end = date.fromisoformat(str(run["data_end_date"]))
        return (
            status.last_period_end is None
            or status.last_period_end < data_end
            or status.unfinished_periods > 0
        )

    @classmethod
    def _status(cls, run: dict[str, Any]) -> RunCheckpointStatus:
        periods = cls._periods(run).values()
        completed = [
            period
            for period in periods
            if period.get("period_key") != "INIT"
            and period.get("status") == "COMPLETED"
        ]
        completed_ends = [
            date.fromisoformat(str(period["period_end"]))
            for period in completed
            if period.get("period_end") is not None
        ]
        return RunCheckpointStatus(
            completed_periods=len(completed),
            unfinished_periods=sum(
                period.get("status") in {"RUNNING", "FAILED"}
                for period in periods
            ),
            last_period_end=max(completed_ends, default=None),
        )

    @staticmethod
    def _updated_at(run: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(str(run["updated_at"]))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(tz=BUSINESS_TIMEZONE).replace(tzinfo=None)

    @staticmethod
    def _json_text(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

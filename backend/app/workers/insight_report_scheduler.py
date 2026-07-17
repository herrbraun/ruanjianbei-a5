from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time

from app.database import SessionLocal
from app.services.insight_report import (
    create_due_reports,
    ensure_default_report_schedules,
    pending_report_ids,
    process_report,
    recover_stale_reports,
)


def run_once() -> dict[str, int]:
    with SessionLocal() as db:
        recovered = recover_stale_reports(db, datetime.now(timezone.utc) - timedelta(minutes=10))
        schedules = ensure_default_report_schedules(db)
        created = len(create_due_reports(db))
        pending = pending_report_ids(db)
    for report_id in pending:
        process_report(report_id)
    return {
        "schedules": schedules,
        "created": created,
        "processed": len(pending),
        "recovered": recovered,
    }


def run_forever(interval_seconds: int) -> None:
    print(f"Insight report worker started; interval={interval_seconds}s", flush=True)
    while True:
        try:
            result = run_once()
            if any(result.values()):
                print(
                    f"Insight report jobs: schedules={result['schedules']}, "
                    f"created={result['created']}, processed={result['processed']}, "
                    f"recovered={result['recovered']}",
                    flush=True,
                )
        except Exception as exc:
            print(f"Insight report worker iteration failed: {exc}", flush=True)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="游客感受度报告自动生成 worker")
    parser.add_argument("--once", action="store_true", help="仅执行一轮后退出")
    parser.add_argument("--interval", type=int, default=60, help="轮询间隔秒数")
    args = parser.parse_args()
    if args.once:
        print(run_once())
    else:
        run_forever(max(10, args.interval))

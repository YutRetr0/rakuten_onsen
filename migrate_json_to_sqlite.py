"""One-shot migration from legacy JSON files to SQLite.

Usage:
    python migrate_json_to_sqlite.py [--dry-run]
"""
import json
import os
import sys
from db import get_conn, init_db

WATCH_FILE = os.getenv("WATCH_FILE", "watchlist.json")
STATE_FILE = os.getenv("STATE_FILE", "state.json")


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(dry_run=False):
    init_db()
    watches = load(WATCH_FILE, [])
    state = load(STATE_FILE, {})
    print(f"Found {len(watches)} watches, {len(state)} state entries")
    if dry_run:
        return
    with get_conn() as conn:
        for w in watches:
            conn.execute(
                """INSERT OR REPLACE INTO watches
                   (id, region, hotel_no, hotel_name, checkin, checkout,
                    adults, rooms, room_keywords, max_price, channels, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (w["id"], w["region"], int(w["hotel_no"]), w.get("hotel_name", ""),
                 w["checkin"], w["checkout"],
                 int(w.get("adults", 2)), int(w.get("rooms", 1)),
                 json.dumps(w.get("room_keywords", []), ensure_ascii=False),
                 w.get("max_price"),
                 json.dumps(w.get("channels", ["wecom"])),
                 w.get("created_at", "")),
            )
        for wid, st in state.items():
            conn.execute(
                """INSERT OR REPLACE INTO watch_state
                   (watch_id, last_available, last_notified_at, last_check_at, matched_count)
                   VALUES (?,?,?,?,?)""",
                (wid, int(bool(st.get("last_available"))),
                 st.get("last_notified_at"),
                 st.get("last_check_at"),
                 int(st.get("matched_count", 0))),
            )
    print("Migration complete. Suggest renaming the legacy JSON files to .bak.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)

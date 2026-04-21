import json
import uuid
import logging
from datetime import datetime
from dateutil import parser as dateparser

from notifier import notify
from db import get_conn, init_db

log = logging.getLogger(__name__)
init_db()  # ensure schema exists at import time


def _row_to_watch(row):
    return {
        "id":            row["id"],
        "region":        row["region"],
        "hotel_no":      row["hotel_no"],
        "hotel_name":    row["hotel_name"] or "",
        "checkin":       row["checkin"],
        "checkout":      row["checkout"],
        "adults":        row["adults"],
        "rooms":         row["rooms"],
        "room_keywords": json.loads(row["room_keywords"] or "[]"),
        "max_price":     row["max_price"],
        "channels":      json.loads(row["channels"] or '["wecom"]'),
        "created_at":    row["created_at"],
    }


def list_watches():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM watches ORDER BY created_at").fetchall()
    return [_row_to_watch(r) for r in rows]


def add_watch(item):
    item["id"] = "w_" + uuid.uuid4().hex[:8]
    item["created_at"] = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO watches (id, region, hotel_no, hotel_name, checkin, checkout,
                                    adults, rooms, room_keywords, max_price, channels, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item["id"], item["region"], int(item["hotel_no"]), item.get("hotel_name", ""),
             item["checkin"], item["checkout"],
             int(item.get("adults", 2)), int(item.get("rooms", 1)),
             json.dumps(item.get("room_keywords", []), ensure_ascii=False),
             item.get("max_price"),
             json.dumps(item.get("channels", ["wecom"])),
             item["created_at"]),
        )
    return item


def remove_watch(wid):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM watches WHERE id = ?", (wid,))
        deleted = cur.rowcount > 0
    return deleted


def _match_rooms(rooms, keywords, max_price):
    matched = []
    for r in rooms:
        if not r.get("available"):
            continue
        if max_price and r.get("price") and r["price"] > max_price:
            continue
        if keywords:
            text = f"{r.get('room_name') or ''} {r.get('plan_name') or ''}"
            if not any(k.lower() in text.lower() for k in keywords):
                continue
        matched.append(r)
    return matched


def check_all(client):
    watches = list_watches()
    if not watches:
        return

    for w in watches:
        try:
            ci = dateparser.parse(w["checkin"])
            co = dateparser.parse(w["checkout"])
            data = client.search_vacant_onsen(
                w["region"], ci, co,
                adults=w.get("adults", 2),
                rooms=w.get("rooms", 1),
                page=1,
            )
            hotels = client.normalize(data, w["region"], ci, co)
            target = next((h for h in hotels if h["hotel_no"] == w["hotel_no"]), None)

            available_rooms = []
            if target:
                available_rooms = _match_rooms(
                    target["rooms"],
                    w.get("room_keywords", []),
                    w.get("max_price"),
                )

            with get_conn() as conn:
                row = conn.execute(
                    "SELECT last_available FROM watch_state WHERE watch_id = ?",
                    (w["id"],),
                ).fetchone()
                prev = bool(row["last_available"]) if row else False
                now_available = bool(available_rooms)
                should_notify = (now_available and not prev)

                if should_notify:
                    hotel_name = w.get("hotel_name") or (target["name"] if target else "?")
                    lines = [f"Hotel: {hotel_name}",
                             f"Date: {w['checkin']} -> {w['checkout']}",
                             f"Guests: {w.get('adults',2)} adults / {w.get('rooms',1)} room(s)",
                             "", "Available rooms:"]
                    for r in available_rooms[:8]:
                        price = f"{r['price']:,} JPY" if r.get("price") else "-"
                        lines.append(
                            f"- {r.get('room_name') or '?'} | {r.get('plan_name') or ''} "
                            f"| {price} | {r.get('available')} left"
                        )
                    notify(
                        w.get("channels", ["wecom"]),
                        title=f"Onsen available: {hotel_name}",
                        body="\n".join(lines),
                        url=(target or {}).get("url") or "",
                    )
                    log.info("notified watch %s", w["id"])
                    conn.execute(
                        """INSERT INTO notification_history (watch_id, notified_at, matched_count, channels)
                           VALUES (?, ?, ?, ?)""",
                        (w["id"], datetime.utcnow().isoformat(),
                         len(available_rooms),
                         json.dumps(w.get("channels", ["wecom"]))),
                    )

                conn.execute(
                    """INSERT INTO watch_state (watch_id, last_available, last_notified_at, last_check_at, matched_count)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(watch_id) DO UPDATE SET
                          last_available = excluded.last_available,
                          last_notified_at = COALESCE(excluded.last_notified_at, watch_state.last_notified_at),
                          last_check_at = excluded.last_check_at,
                          matched_count = excluded.matched_count""",
                    (w["id"], int(now_available),
                     datetime.utcnow().isoformat() if should_notify else None,
                     datetime.utcnow().isoformat(),
                     len(available_rooms)),
                )
        except Exception as e:
            log.exception("check watch %s failed: %s", w.get("id"), e)
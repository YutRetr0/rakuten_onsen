import os
import json
import uuid
import logging
import threading
from datetime import datetime
from dateutil import parser as dateparser

from notifier import notify

log = logging.getLogger(__name__)

WATCH_FILE = os.getenv("WATCH_FILE", "watchlist.json")
STATE_FILE = os.getenv("STATE_FILE", "state.json")
_lock = threading.Lock()

def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def list_watches():
    with _lock:
        return _load(WATCH_FILE, [])

def add_watch(item):
    item["id"] = "w_" + uuid.uuid4().hex[:8]
    item["created_at"] = datetime.utcnow().isoformat()
    with _lock:
        data = _load(WATCH_FILE, [])
        data.append(item)
        _save(WATCH_FILE, data)
    return item

def remove_watch(wid):
    with _lock:
        data = _load(WATCH_FILE, [])
        new = [w for w in data if w["id"] != wid]
        _save(WATCH_FILE, new)
        st = _load(STATE_FILE, {})
        st.pop(wid, None)
        _save(STATE_FILE, st)
        return len(new) != len(data)

def _match_rooms(rooms, keywords, max_price):
    matched = []
    for r in rooms:
        if not r.get("available"):
            continue
        if max_price and r.get("price") and r["price"] > max_price:
            continue
        if keywords:
            text = f"{{r.get('room_name') or ''}} {{r.get('plan_name') or ''}}"
            if not any(k.lower() in text.lower() for k in keywords):
                continue
        matched.append(r)
    return matched

def check_all(client):
    watches = list_watches()
    if not watches:
        return
    state = _load(STATE_FILE, {})

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

            prev = state.get(w["id"], {}).get("last_available", False)
            now_available = bool(available_rooms)
            should_notify = (now_available and not prev)

            if should_notify:
                hotel_name = w.get("hotel_name") or (target["name"] if target else "?")
                lines = [f"Hotel: {{hotel_name}}",
                         f"Date: {{w['checkin']}} -> {{w['checkout']}}",
                         f"Guests: {{w.get('adults',2)}} adults / {{w.get('rooms',1)}} room(s)",
                         "", "Available rooms:"]
                for r in available_rooms[:8]:
                    price = f"{{r['price']:,}} JPY" if r.get("price") else "-"
                    lines.append(
                        f"- {{r.get('room_name') or '?'}} | {{r.get('plan_name') or ''}} "
                        f"| {{price}} | {{r.get('available')}} left"
                    )
                notify(
                    w.get("channels", ["wecom"]),
                    title=f"Onsen available: {{hotel_name}}",
                    body="\n".join(lines),
                    url=(target or {}).get("url") or "",
                )
                log.info("notified watch %s", w["id"])

            state[w["id"]] = {
                "last_available": now_available,
                "last_notified_at": datetime.utcnow().isoformat() if should_notify
                                 else state.get(w["id"], {}).get("last_notified_at"),
                "last_check_at": datetime.utcnow().isoformat(),
                "matched_count": len(available_rooms),
            }
        except Exception as e:
            log.exception("check watch %s failed: %s", w.get("id"), e)

    _save(STATE_FILE, state)
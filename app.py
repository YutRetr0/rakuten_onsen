import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from cache import TTLCache
from rakuten import REGIONS, RakutenTravel
from watcher import add_watch, check_all, list_watches, remove_watch

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = Flask(__name__)

client = RakutenTravel(
    app_id=os.getenv("RAKUTEN_APP_ID"),
    affiliate_id=os.getenv("RAKUTEN_AFFILIATE_ID") or None,
)
cache = TTLCache(ttl=300)


class InputError(ValueError):
    pass


def _scheduler_enabled():
    value = os.getenv("ENABLE_SCHEDULER", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _parse_date(value, field_name):
    if not value:
        raise InputError(f"invalid {field_name}")
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise InputError(f"invalid {field_name}") from exc


def _parse_positive_int(value, field_name, *, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"invalid {field_name}") from exc
    if parsed < 1 or (maximum is not None and parsed > maximum):
        raise InputError(f"invalid {field_name}")
    return parsed


def _parse_optional_int(value, field_name, *, minimum=None):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"invalid {field_name}") from exc
    if minimum is not None and parsed < minimum:
        raise InputError(f"invalid {field_name}")
    return parsed


def _normalize_region(value):
    region = (value or "").strip().lower()
    if region not in REGIONS:
        raise InputError("invalid region")
    return region


def _parse_stay_dates(args):
    if args.get("checkin") or args.get("checkout"):
        if not (args.get("checkin") and args.get("checkout")):
            raise InputError("invalid date")
        checkin = _parse_date(args.get("checkin"), "checkin")
        checkout = _parse_date(args.get("checkout"), "checkout")
    else:
        date_value = args.get("date")
        checkin = _parse_date(date_value, "date") if date_value else datetime.today() + timedelta(days=1)
        checkout = checkin + timedelta(days=1)
    if checkout <= checkin:
        raise InputError("checkout must be after checkin")
    return checkin, checkout


def _build_watch_item(body):
    required = ["region", "hotel_no", "checkin", "checkout"]
    for key in required:
        if key not in body:
            raise InputError(f"missing field: {key}")
    checkin = _parse_date(body["checkin"], "checkin")
    checkout = _parse_date(body["checkout"], "checkout")
    if checkout <= checkin:
        raise InputError("checkout must be after checkin")
    return {
        "region": _normalize_region(body["region"]),
        "hotel_no": _parse_positive_int(body["hotel_no"], "hotel_no"),
        "hotel_name": body.get("hotel_name", ""),
        "checkin": checkin.strftime("%Y-%m-%d"),
        "checkout": checkout.strftime("%Y-%m-%d"),
        "adults": _parse_positive_int(body.get("adults", 2), "adults"),
        "rooms": _parse_positive_int(body.get("rooms", 1), "rooms"),
        "room_keywords": body.get("room_keywords", []),
        "max_price": _parse_optional_int(body.get("max_price"), "max_price", minimum=0),
        "channels": body.get("channels", ["wecom"]),
    }


scheduler = None
if _scheduler_enabled():
    scheduler = BackgroundScheduler()
    scheduler.add_job(cache.invalidate_all, "interval", minutes=5, id="refresh", replace_existing=True)
    scheduler.add_job(
        lambda: check_all(client), "interval", minutes=5, id="watcher", replace_existing=True, max_instances=1
    )
    scheduler.start()


def _do_search(region, ci, co, adults, rooms, max_charge, max_pages):
    all_hotels = []
    for page in range(1, max_pages + 1):
        try:
            data = client.search_vacant_onsen(
                region, ci, co, adults=adults, rooms=rooms, max_charge=max_charge, page=page
            )
        except Exception as e:
            if "404" in str(e):
                break
            raise
        hotels = client.normalize(data, region, ci, co)
        if not hotels:
            break
        all_hotels.extend(hotels)
        page_info = data.get("pagingInfo", {})
        if page >= page_info.get("pageCount", 1):
            break
    return all_hotels


@app.route("/")
def index():
    return render_template("index.html", regions=sorted(REGIONS.keys()))


@app.route("/api/search")
def api_search():
    try:
        region = _normalize_region(request.args.get("region", "oita"))
        ci, co = _parse_stay_dates(request.args)
        adults = _parse_positive_int(request.args.get("adults", 2), "adults")
        rooms = _parse_positive_int(request.args.get("rooms", 1), "rooms")
        max_charge = _parse_optional_int(request.args.get("max_charge"), "max_charge", minimum=0)
        pages = _parse_positive_int(request.args.get("pages", 2), "pages", maximum=5)
    except InputError as e:
        return jsonify({"error": str(e)}), 400

    key = f"{region}:{ci.date()}:{co.date()}:{adults}:{rooms}:{max_charge}:{pages}"
    try:
        hotels = cache.get_or_set(key, lambda: _do_search(region, ci, co, adults, rooms, max_charge, pages))
    except Exception as e:
        app.logger.exception("API failed")
        return jsonify({"error": str(e)}), 500

    return jsonify(
        {
            "region": region,
            "checkin": ci.strftime("%Y-%m-%d"),
            "checkout": co.strftime("%Y-%m-%d"),
            "adults": adults,
            "rooms": rooms,
            "count": len(hotels),
            "cache_ttl_seconds": cache.ttl,
            "hotels": hotels,
        }
    )


@app.route("/api/watch", methods=["GET"])
def api_watch_list():
    return jsonify(list_watches())


@app.route("/api/watch", methods=["POST"])
def api_watch_add():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid JSON body"}), 400
    try:
        item = _build_watch_item(body)
    except InputError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(add_watch(item))


@app.route("/api/watch/<wid>", methods=["DELETE"])
def api_watch_del(wid):
    return jsonify({"deleted": remove_watch(wid)})


@app.route("/api/watch/check_now", methods=["POST"])
def api_watch_check_now():
    check_all(client)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

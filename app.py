import logging
import os
from datetime import datetime, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as dateparser
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


class InvalidInputError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _scheduler_enabled():
    """Return whether the embedded scheduler should run in this process."""
    return os.getenv("ENABLE_SCHEDULER", "1").lower() not in {"0", "false", "no"}


def _parse_date(value, field_name):
    """Parse a user-provided date and raise a safe validation error on failure."""
    try:
        parsed = dateparser.parse(value)
    except (TypeError, ValueError) as exc:
        raise InvalidInputError(f"invalid {field_name}") from exc
    if parsed is None:
        raise InvalidInputError(f"invalid {field_name}")
    return parsed


def _parse_int(value, field_name, *, minimum=None, maximum=None):
    """Parse an integer constraint from user input."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidInputError(f"invalid {field_name}") from exc
    if minimum is not None and parsed < minimum:
        raise InvalidInputError(f"invalid {field_name}")
    if maximum is not None and parsed > maximum:
        raise InvalidInputError(f"invalid {field_name}")
    return parsed


def _validate_region(region):
    """Normalize and validate a region query value."""
    normalized = (region or "").strip().lower()
    if normalized not in REGIONS:
        raise InvalidInputError("invalid region")
    return normalized


def _parse_search_dates(args):
    """Validate supported search date inputs and return check-in/check-out datetimes."""
    has_checkin = "checkin" in args
    has_checkout = "checkout" in args
    if has_checkin != has_checkout:
        raise InvalidInputError("checkin and checkout must be provided together")
    if has_checkin:
        ci = _parse_date(args["checkin"], "checkin")
        co = _parse_date(args["checkout"], "checkout")
    else:
        d = args.get("date")
        ci = _parse_date(d, "date") if d else datetime.today() + timedelta(days=1)
        co = ci + timedelta(days=1)
    if co <= ci:
        raise InvalidInputError("checkout must be after checkin")
    return ci, co


def _validate_watch_item(item):
    """Validate and normalize a watch creation payload."""
    validated = {
        "region": _validate_region(item["region"]),
        "hotel_no": _parse_int(item["hotel_no"], "hotel_no", minimum=1),
        "hotel_name": item.get("hotel_name", ""),
        "checkin": _parse_date(item["checkin"], "checkin").strftime("%Y-%m-%d"),
        "checkout": _parse_date(item["checkout"], "checkout").strftime("%Y-%m-%d"),
        "adults": _parse_int(item.get("adults", 2), "adults", minimum=1),
        "rooms": _parse_int(item.get("rooms", 1), "rooms", minimum=1),
        "room_keywords": item.get("room_keywords", []),
        "channels": item.get("channels", ["wecom"]),
    }
    if validated["checkout"] <= validated["checkin"]:
        raise InvalidInputError("checkout must be after checkin")
    max_price = item.get("max_price")
    validated["max_price"] = None if max_price in (None, "") else _parse_int(max_price, "max_price", minimum=1)
    return validated


scheduler = None
if _scheduler_enabled():
    scheduler = BackgroundScheduler()
    scheduler.add_job(cache.invalidate_all, "interval", minutes=5, id="refresh", replace_existing=True)
    scheduler.add_job(
        lambda: check_all(client), "interval", minutes=5, id="watcher", replace_existing=True, max_instances=1
    )
    scheduler.start()
else:
    app.logger.info("scheduler disabled by ENABLE_SCHEDULER")


def _do_search(region, ci, co, adults, rooms, max_charge, max_pages):
    all_hotels = []
    for page in range(1, max_pages + 1):
        try:
            data = client.search_vacant_onsen(
                region, ci, co, adults=adults, rooms=rooms, max_charge=max_charge, page=page
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
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
        region = _validate_region(request.args.get("region", "oita"))
        ci, co = _parse_search_dates(request.args)
        adults = _parse_int(request.args.get("adults", 2), "adults", minimum=1)
        rooms = _parse_int(request.args.get("rooms", 1), "rooms", minimum=1)
        max_charge_raw = request.args.get("max_charge")
        max_charge = None if max_charge_raw in (None, "") else _parse_int(max_charge_raw, "max_charge", minimum=1)
        pages = _parse_int(request.args.get("pages", 2), "pages", minimum=1, maximum=5)
    except InvalidInputError as exc:
        return jsonify({"error": exc.message}), 400

    key = f"{region}:{ci.date()}:{co.date()}:{adults}:{rooms}:{max_charge}:{pages}"
    try:
        hotels = cache.get_or_set(key, lambda: _do_search(region, ci, co, adults, rooms, max_charge, pages))
    except requests.RequestException:
        app.logger.exception("API failed")
        return jsonify({"error": "internal server error"}), 500

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
    body = request.get_json(force=True)
    required = ["region", "hotel_no", "checkin", "checkout"]
    for k in required:
        if k not in body:
            return jsonify({"error": f"missing field: {k}"}), 400
    try:
        item = _validate_watch_item(body)
    except InvalidInputError as exc:
        return jsonify({"error": exc.message}), 400
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

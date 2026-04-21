import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as dateparser
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from cache import TTLCache
from rakuten import REGIONS, RakutenTravel
from watcher import add_watch, check_all, list_watches, remove_watch

load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = Flask(__name__)

client = RakutenTravel(
    app_id=os.getenv("RAKUTEN_APP_ID"),
    affiliate_id=os.getenv("RAKUTEN_AFFILIATE_ID") or None,
)
cache = TTLCache(ttl=300)

scheduler = BackgroundScheduler()
scheduler.add_job(cache.invalidate_all, "interval", minutes=5,
                  id="refresh", replace_existing=True)
scheduler.add_job(lambda: check_all(client), "interval", minutes=5,
                  id="watcher", replace_existing=True, max_instances=1)
scheduler.start()


def _do_search(region, ci, co, adults, rooms, max_charge, max_pages):
    all_hotels = []
    for page in range(1, max_pages + 1):
        try:
            data = client.search_vacant_onsen(
                region, ci, co, adults=adults, rooms=rooms,
                max_charge=max_charge, page=page
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
    region = request.args.get("region", "oita")

    if request.args.get("checkin") and request.args.get("checkout"):
        ci = dateparser.parse(request.args["checkin"])
        co = dateparser.parse(request.args["checkout"])
    else:
        d = request.args.get("date")
        ci = dateparser.parse(d) if d else datetime.today() + timedelta(days=1)
        co = ci + timedelta(days=1)

    if co <= ci:
        return jsonify({"error": "checkout must be after checkin"}), 400

    adults     = int(request.args.get("adults", 2))
    rooms      = int(request.args.get("rooms", 1))
    max_charge = request.args.get("max_charge", type=int)
    pages      = min(int(request.args.get("pages", 2)), 5)

    key = f"{region}:{ci.date()}:{co.date()}:{adults}:{rooms}:{max_charge}:{pages}"
    try:
        hotels = cache.get_or_set(
            key,
            lambda: _do_search(region, ci, co, adults, rooms, max_charge, pages)
        )
    except Exception as e:
        app.logger.exception("API failed")
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "region": region,
        "checkin": ci.strftime("%Y-%m-%d"),
        "checkout": co.strftime("%Y-%m-%d"),
        "adults": adults,
        "rooms": rooms,
        "count": len(hotels),
        "cache_ttl_seconds": cache.ttl,
        "hotels": hotels,
    })


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
    item = {
        "region":        body["region"],
        "hotel_no":      int(body["hotel_no"]),
        "hotel_name":    body.get("hotel_name", ""),
        "checkin":       body["checkin"],
        "checkout":      body["checkout"],
        "adults":        int(body.get("adults", 2)),
        "rooms":         int(body.get("rooms", 1)),
        "room_keywords": body.get("room_keywords", []),
        "max_price":     body.get("max_price"),
        "channels":      body.get("channels", ["wecom"]),
    }
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

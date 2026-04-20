"""
Rakuten Travel API client.
"""
import time
import logging
from datetime import datetime
from typing import Optional

import requests

log = logging.getLogger(__name__)

VACANT_URL = "https://app.rakuten.co.jp/services/api/Travel/VacantHotelSearch/20170426"
AREA_URL   = "https://app.rakuten.co.jp/services/api/Travel/GetAreaClass/20131024"

REGIONS = {
    "hokkaido":  {"large": "japan", "middle": "hokkaido"},
    "aomori":    {"large": "japan", "middle": "aomori"},
    "iwate":     {"large": "japan", "middle": "iwate"},
    "miyagi":    {"large": "japan", "middle": "miyagi"},
    "akita":     {"large": "japan", "middle": "akita"},
    "yamagata":  {"large": "japan", "middle": "yamagata"},
    "fukushima": {"large": "japan", "middle": "fukushima"},
    "tokyo":     {"large": "japan", "middle": "tokyo"},
    "kanagawa":  {"large": "japan", "middle": "kanagawa"},
    "chiba":     {"large": "japan", "middle": "chiba"},
    "shizuoka":  {"large": "japan", "middle": "shizuoka"},
    "nagano":    {"large": "japan", "middle": "nagano"},
    "gifu":      {"large": "japan", "middle": "gifu"},
    "ishikawa":  {"large": "japan", "middle": "ishikawa"},
    "kyoto":     {"large": "japan", "middle": "kyoto"},
    "osaka":     {"large": "japan", "middle": "osaka"},
    "hyogo":     {"large": "japan", "middle": "hyogo"},
    "wakayama":  {"large": "japan", "middle": "wakayama"},
    "tottori":   {"large": "japan", "middle": "tottori"},
    "shimane":   {"large": "japan", "middle": "shimane"},
    "okayama":   {"large": "japan", "middle": "okayama"},
    "hiroshima": {"large": "japan", "middle": "hiroshima"},
    "ehime":     {"large": "japan", "middle": "ehime"},
    "fukuoka":   {"large": "japan", "middle": "fukuoka"},
    "oita":      {"large": "japan", "middle": "oita"},
    "kumamoto":  {"large": "japan", "middle": "kumamoto"},
    "kagoshima": {"large": "japan", "middle": "kagoshima"},
    "okinawa":   {"large": "japan", "middle": "okinawa"},
}


class RakutenTravel:
    def __init__(self, app_id: str, affiliate_id: Optional[str] = None,
                 min_interval: float = 1.1, timeout: int = 15):
        if not app_id:
            raise ValueError("RAKUTEN_APP_ID is required")
        self.app_id = app_id
        self.affiliate_id = affiliate_id
        self.min_interval = min_interval
        self.timeout = timeout
        self._last_call = 0.0
        self.session = requests.Session()

    def _throttle(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()

    def _get(self, url, params):
        params = {**params, "applicationId": self.app_id, "format": "json"}
        if self.affiliate_id:
            params["affiliateId"] = self.affiliate_id
        self._throttle()
        log.info("GET %s", url)
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code >= 400:
            log.warning("API error %s: %s", resp.status_code, resp.text[:300])
        resp.raise_for_status()
        return resp.json()

    def search_vacant_onsen(self, region_key, checkin, checkout,
                            adults=2, rooms=1, max_charge=None, page=1):
        region = REGIONS.get(region_key.lower())
        if not region:
            raise ValueError(f"Unknown region: {region_key}")

        params = {
            "largeClassCode":  region["large"],
            "middleClassCode": region["middle"],
            "checkinDate":     checkin.strftime("%Y-%m-%d"),
            "checkoutDate":    checkout.strftime("%Y-%m-%d"),
            "adultNum":        adults,
            "roomNum":         rooms,
            "onsenFlag":       1,
            "hits":            30,
            "page":            page,
            "datumType":       1,
            "responseType":    "large",
        }
        if max_charge:
            params["maxCharge"] = max_charge
        return self._get(VACANT_URL, params)

    @staticmethod
    def normalize(api_json, region_key, checkin, checkout):
        hotels_out = []
        for entry in api_json.get("hotels", []):
            blocks = entry.get("hotel", [])
            if not blocks:
                continue

            basic   = next((b["hotelBasicInfo"]  for b in blocks if "hotelBasicInfo"  in b), {})
            rating  = next((b["hotelRatingInfo"] for b in blocks if "hotelRatingInfo" in b), {})
            room_infos = [b["roomInfo"] for b in blocks if "roomInfo" in b]

            rooms = []
            for ri in room_infos:
                rb = next((x.get("roomBasicInfo") for x in ri if "roomBasicInfo" in x), {})
                dc = next((x.get("dailyCharge")   for x in ri if "dailyCharge"   in x), {})
                rooms.append({
                    "plan_name":     rb.get("planName"),
                    "room_name":     rb.get("roomName"),
                    "room_class":    rb.get("roomClass"),
                    "max_occupancy": rb.get("maxOccupancy"),
                    "smoking":       rb.get("nonSmoking"),
                    "available":     rb.get("availableRoomNum"),
                    "price":         dc.get("total") or dc.get("rakutenCharge"),
                    "stay_date":     dc.get("stayDate"),
                    "plan_url":      rb.get("planContentsUrl"),
                })

            hotels_out.append({
                "region":         region_key,
                "hotel_no":       basic.get("hotelNo"),
                "name":           basic.get("hotelName"),
                "kana":           basic.get("hotelKanaName"),
                "url":            basic.get("hotelInformationUrl"),
                "image":          basic.get("hotelImageUrl"),
                "address":        (basic.get("address1") or "") + (basic.get("address2") or ""),
                "access":         basic.get("access"),
                "telephone":      basic.get("telephoneNo"),
                "min_charge":     basic.get("hotelMinCharge"),
                "review_avg":     basic.get("reviewAverage"),
                "review_count":   basic.get("reviewCount"),
                "service_score":  rating.get("serviceAverage"),
                "location_score": rating.get("locationAverage"),
                "room_score":     rating.get("roomAverage"),
                "bath_score":     rating.get("bathAverage"),
                "meal_score":     rating.get("mealAverage"),
                "special":        basic.get("hotelSpecial"),
                "onsen_types":    RakutenTravel._extract_onsen_types(basic.get("hotelSpecial", "")),
                "checkin":        checkin.strftime("%Y-%m-%d"),
                "checkout":       checkout.strftime("%Y-%m-%d"),
                "rooms":          rooms,
                "total_rooms":    sum((r.get("available") or 0) for r in rooms),
            })
        return hotels_out

    @staticmethod
    def _extract_onsen_types(text):
        if not text:
            return []
        keywords = [
            "単純温泉", "単純泉", "硫黄泉", "塩化物泉", "炭酸水素塩泉",
            "硫酸塩泉", "含鉄泉", "酸性泉", "放射能泉", "ラジウム泉",
            "ナトリウム泉", "カルシウム泉", "マグネシウム泉",
            "アルカリ性", "炭酸泉", "美肌の湯", "源泉かけ流し", "露天風呂",
        ]
        return sorted({k for k in keywords if k in text})

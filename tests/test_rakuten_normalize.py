from datetime import datetime

from rakuten import RakutenTravel

FIXTURE = {
    "hotels": [
        {
            "hotel": [
                {
                    "hotelBasicInfo": {
                        "hotelNo": "123456",
                        "hotelName": "別府温泉テストホテル",
                        "hotelKanaName": "べっぷおんせんてすとほてる",
                        "hotelInformationUrl": "https://travel.rakuten.co.jp/HOTEL/123456/",
                        "hotelImageUrl": "https://example.com/img.jpg",
                        "address1": "大分県",
                        "address2": "別府市北浜1-1-1",
                        "access": "JR別府駅から徒歩5分",
                        "telephoneNo": "0977-00-0000",
                        "hotelMinCharge": 8000,
                        "reviewAverage": 4.5,
                        "reviewCount": 200,
                        "hotelSpecial": "硫黄泉、源泉かけ流し、露天風呂がございます",
                    }
                },
                {
                    "hotelRatingInfo": {
                        "serviceAverage": 4.6,
                        "locationAverage": 4.7,
                        "roomAverage": 4.4,
                        "bathAverage": 4.8,
                        "mealAverage": 4.5,
                    }
                },
                {
                    "roomInfo": [
                        {
                            "roomBasicInfo": {
                                "roomClass": "standard",
                                "roomName": "和室",
                                "planName": "素泊まりプラン",
                                "maxOccupancy": 2,
                                "nonSmoking": "1",
                                "availableRoomNum": 3,
                                "planContentsUrl": "https://travel.rakuten.co.jp/HOTEL/123456/plan/",
                            }
                        },
                        {
                            "dailyCharge": {
                                "stayDate": "2026-05-01",
                                "total": 10000,
                                "rakutenCharge": 9800,
                            }
                        },
                    ]
                },
                {
                    "roomInfo": [
                        {
                            "roomBasicInfo": {
                                "roomClass": "deluxe",
                                "roomName": "露天風呂付き客室",
                                "planName": "朝食付きプラン",
                                "maxOccupancy": 2,
                                "nonSmoking": "1",
                                "availableRoomNum": 1,
                                "planContentsUrl": "https://travel.rakuten.co.jp/HOTEL/123456/plan2/",
                            }
                        },
                        {
                            "dailyCharge": {
                                "stayDate": "2026-05-01",
                                "total": None,
                                "rakutenCharge": 25000,
                            }
                        },
                    ]
                },
            ]
        }
    ]
}


def test_normalize_returns_one_hotel():
    result = RakutenTravel.normalize(
        FIXTURE, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    assert len(result) == 1


def test_normalize_basic_fields():
    result = RakutenTravel.normalize(
        FIXTURE, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    hotel = result[0]
    assert hotel["hotel_no"] == "123456"
    assert hotel["name"] == "別府温泉テストホテル"
    assert hotel["address"] == "大分県別府市北浜1-1-1"
    assert hotel["url"] == "https://travel.rakuten.co.jp/HOTEL/123456/"
    assert hotel["review_avg"] == 4.5


def test_normalize_checkin_checkout_strings():
    result = RakutenTravel.normalize(
        FIXTURE, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    hotel = result[0]
    assert hotel["checkin"] == "2026-05-01"
    assert hotel["checkout"] == "2026-05-02"


def test_normalize_rooms_length_and_fields():
    result = RakutenTravel.normalize(
        FIXTURE, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    hotel = result[0]
    assert len(hotel["rooms"]) == 2

    room0 = hotel["rooms"][0]
    assert room0["room_name"] == "和室"
    assert room0["plan_name"] == "素泊まりプラン"
    assert room0["available"] == 3
    assert room0["price"] == 10000


def test_normalize_price_fallback_to_rakuten_charge():
    result = RakutenTravel.normalize(
        FIXTURE, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    room1 = result[0]["rooms"][1]
    assert room1["price"] == 25000


def test_normalize_total_rooms():
    result = RakutenTravel.normalize(
        FIXTURE, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    assert result[0]["total_rooms"] == 4


def test_normalize_empty_hotels():
    result = RakutenTravel.normalize(
        {"hotels": []}, region_key="oita",
        checkin=datetime(2026, 5, 1), checkout=datetime(2026, 5, 2),
    )
    assert result == []


def test_extract_onsen_types_deduped_sorted():
    text = "硫黄泉、源泉かけ流し、露天風呂"
    result = RakutenTravel._extract_onsen_types(text)
    assert isinstance(result, list)
    assert result == sorted(set(result))
    assert "硫黄泉" in result
    assert "源泉かけ流し" in result
    assert "露天風呂" in result


def test_extract_onsen_types_empty_string():
    assert RakutenTravel._extract_onsen_types("") == []


def test_extract_onsen_types_none():
    assert RakutenTravel._extract_onsen_types(None) == []

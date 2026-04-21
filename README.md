# Rakuten Onsen Search

A simple Flask app that searches Japanese onsen (hot spring) hotels using the
free Rakuten Travel API (`VacantHotelSearch`).

## Features
- Filters only onsen hotels (`onsenFlag=1`)
- Search by region + single date or date range
- Returns price, room types, available rooms, ratings, onsen types
- 5-minute in-memory TTL cache (auto-refresh via APScheduler)

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and put your RAKUTEN_APP_ID
python app.py
```
Open http://localhost:5000

## API
```
GET /api/search?region=oita&date=2026-05-01
GET /api/search?region=hyogo&checkin=2026-05-01&checkout=2026-05-03&adults=2&max_charge=30000
```

## Get a Rakuten App ID (free)
1. Register at https://webservice.rakuten.co.jp/
2. Create an app, copy the Application ID
3. Put it in `.env`

## Notes
- Rakuten API limit: ~1 request/second (auto-throttled)
- Run with `debug=False` to avoid duplicate scheduler instances
- For multi-worker deployment, replace TTLCache with Redis

## Storage

Watch list and state are persisted in SQLite at `DB_PATH` (default `rakuten_onsen.db`).
The database is auto-created on first run.

### Migrating from the old JSON files

If you previously ran a version that used `watchlist.json` / `state.json`:

```bash
python migrate_json_to_sqlite.py --dry-run   # preview
python migrate_json_to_sqlite.py             # actually migrate
mv watchlist.json watchlist.json.bak
mv state.json state.json.bak
```

## Development

![CI](https://github.com/YutRetr0/rakuten_onsen/actions/workflows/ci.yml/badge.svg)

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -v
```

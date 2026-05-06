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
# Edit .env and put your RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY
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
2. Create an app, copy the Application ID and Access Key
3. Put them in `.env` as `RAKUTEN_APP_ID` and `RAKUTEN_ACCESS_KEY`

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

## Notification history

The `notification_history` table records every notification sent. The Web UI surfaces this as a "📊 通知历史" panel at the bottom of the home page, showing:

- A bar chart of notifications per day for the last 7 / 30 / 90 days
- A filterable list of recent notifications (per watch, with hotel name / channels)

Two read-only JSON endpoints back this UI:

| Endpoint | Description |
|---|---|
| `GET /api/notifications/history?days=30&watch_id=&limit=200` | Recent notification rows with hotel info (LEFT JOIN watches) |
| `GET /api/notifications/daily?days=30` | Daily aggregated counts; missing days are filled with `count=0` so the chart x-axis is continuous |

## Docker

[![Docker](https://github.com/YutRetr0/rakuten_onsen/actions/workflows/docker.yml/badge.svg)](https://github.com/YutRetr0/rakuten_onsen/actions/workflows/docker.yml)

Run the published image (auto-built from `main`):

```bash
docker run -d --name rakuten_onsen \
  -p 5000:5000 \
  -v $PWD/data:/data \
  -e RAKUTEN_APP_ID=your_app_id \
  -e RAKUTEN_ACCESS_KEY=your_access_key \
  -e WECOM_BOT_WEBHOOK=https://... \
  ghcr.io/yutretr0/rakuten_onsen:latest
```

The image persists SQLite data at `/data/rakuten_onsen.db` (mount `-v $PWD/data:/data` to keep it across container restarts).

If you're upgrading from a pre-SQLite image and have legacy `watchlist.json` / `state.json` in your `/data` volume, run the migration once:

```bash
docker run --rm -v $PWD/data:/data \
  ghcr.io/yutretr0/rakuten_onsen:latest \
  python migrate_json_to_sqlite.py
```

> Note: the app starts an APScheduler `BackgroundScheduler` at module import time.
> The image runs `gunicorn -w 2` by default; if you need exactly-once watch
> execution, set `-w 1` or run a separate scheduler process.

> **First-time setup**: after the image is first pushed to GHCR, go to
> GitHub → Packages → `rakuten_onsen` → Package settings → Change visibility → Public.
> Also verify Settings → Actions → General → Workflow permissions is set to
> "Read and write permissions".

## Development

![CI](https://github.com/YutRetr0/rakuten_onsen/actions/workflows/ci.yml/badge.svg)
![Linted by Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -v
ruff check .
ruff format --check .
```

import os
import json
import time
import threading
import sqlite3
import logging
from flask import Flask, request
import requests
from zoneinfo import ZoneInfo

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class TimezoneFormatter(logging.Formatter):
    """
    Custom logging formatter that formats log timestamps in a specified timezone.

    Args:
        fmt (str): Log message format string.
        datefmt (str): Date/time format string.
        tz (zoneinfo.ZoneInfo): Cached timezone object to use for formatting timestamps. Pass a reused instance for efficiency.

    Usage:
def get_timezone():
def get_timezone():
    """
    Retrieves the timezone specified by the TIMEZONE environment variable, or defaults to UTC if not set or invalid.

    Returns:
        ZoneInfo: The ZoneInfo object for the specified timezone, or UTC if the timezone is invalid or not set.

    If the specified timezone is invalid, a warning is logged and UTC is returned.
    """
    tz_name = os.getenv("TIMEZONE", "UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logging.warning(f"[Config] Unknown timezone: {tz_name}, defaulting to UTC")
        return ZoneInfo("UTC")
CACHED_TZ = get_timezone()

# Update logging configuration
timezone_formatter = TimezoneFormatter(fmt='[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S', tz=CACHED_TZ)
logger = logging.getLogger()
if logger.handlers:
    for handler in logger.handlers:
        handler.setFormatter(timezone_formatter)
else:
    handler = logging.StreamHandler()
    handler.setFormatter(timezone_formatter)
    logger.addHandler(handler)

# Constants
DB_PATH = "watched.db"
CONFIG_PATH = "config.json"

# Globals
app = Flask(__name__)
CONFIG = {}

def load_config():
    global CONFIG
    try:
        with open(CONFIG_PATH) as f:
            CONFIG = json.load(f)
        logging.info("[Config] Reloaded config.json")
    except Exception as e:
        logging.error(f"[Config] Failed to load config.json: {e}")

def start_config_watcher():
    def watcher():
        last_mtime = None
        while True:
            try:
                mtime = os.path.getmtime(CONFIG_PATH)
                if mtime != last_mtime:
                    load_config()
                    last_mtime = mtime
            except Exception:
                pass
            time.sleep(5)
    threading.Thread(target=watcher, daemon=True).start()

def init_db():
    should_create = not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0
    conn = sqlite3.connect(DB_PATH)
    if should_create:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS watched (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating_key TEXT UNIQUE,
                series TEXT,
                season INTEGER,
                episode INTEGER,
                watched_at INTEGER
            )
        """)
        conn.commit()
        logging.info("[DB] Initialized new watched.db")
    conn.close()

def delete_episode(series, season, episode):
    try:
        api_key = CONFIG["sonarr"]["api_key"]
        sonarr_url = CONFIG["sonarr"]["url"].rstrip("/")
        headers = {"X-Api-Key": api_key}

        series_res = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
        series_res.raise_for_status()
        series_data = series_res.json()
        matching_series = next((s for s in series_data if s["title"].lower() == series.lower()), None)
        if not matching_series:
            logging.warning(f"[Sonarr] Series not found: {series}")
            return

        episode_res = requests.get(f"{sonarr_url}/api/v3/episode?seriesId={matching_series['id']}", headers=headers)
        episode_res.raise_for_status()
        episode_data = episode_res.json()
        match = next((ep for ep in episode_data if ep["seasonNumber"] == season and ep["episodeNumber"] == episode), None)
        if not match:
            logging.warning(f"[Sonarr] Episode not found: S{season}E{episode}")
            return

        if match.get("hasFile"):
            requests.delete(f"{sonarr_url}/api/v3/episodefile/{match['episodeFileId']}", headers=headers)
            logging.info(f"[Sonarr] Deleted {series} S{season}E{episode}")
        else:
            logging.info(f"[Sonarr] No file to delete for {series} S{season}E{episode}")

        if CONFIG.get("unmonitor_after_delete", True):
            match["monitored"] = False
            requests.put(f"{sonarr_url}/api/v3/episode/{match['id']}", headers=headers, json=match)
            logging.info(f"[Sonarr] Unmonitored {series} S{season}E{episode}")
    except Exception as e:
        logging.error(f"[Sonarr] Error handling deletion: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        content_type = request.headers.get("Content-Type", "")
        if "multipart/form-data" in content_type:
            payload = json.loads(request.form.get("payload", "{}"))
        else:
            payload = request.get_json(force=True)

        if not payload:
            logging.warning("[Webhook] No payload received.")
            return "", 200

        event_type = payload.get("event")
        logging.info(f"[Webhook] Event received: {event_type}")

        if event_type != "media.scrobble":
            return "", 200

        md = payload.get("Metadata", {})
        if md.get("librarySectionType") != "show":
            logging.info("[Webhook] Ignored non-show media item.")
            return "", 200

        series = md.get("grandparentTitle")
        season = md.get("parentIndex")
        episode = md.get("index")
        rating_key = md.get("ratingKey")
        watched_at = md.get("lastViewedAt", int(time.time()))

        logging.info(f"[Webhook] Scrobbled: {series} S{season}E{episode}")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO watched (rating_key, series, season, episode, watched_at)
            VALUES (?, ?, ?, ?, ?)
        """, (rating_key, series, season, episode, watched_at))
        conn.commit()
        conn.close()

        override = CONFIG.get("series_settings", {}).get(series)
        if override:
            logging.info(f"[Config] Override found for '{series}': {override}")
        else:
            logging.info(f"[Config] No override found for '{series}', using global default.")

        grace_days = override.get("grace_days") if override else CONFIG.get("grace_days", 2)

        if grace_days == 0:
            delete_episode(series, season, episode)

    except Exception as e:
        logging.error(f"[ERROR] Exception in webhook:\n{e}")

    return "", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    load_config()
    start_config_watcher()
    init_db()
    app.run(host="0.0.0.0", port=5000)

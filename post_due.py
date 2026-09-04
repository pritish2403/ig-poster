"""
post_due.py - Post any Instagram reels that are due, from schedule.json.

Runs inside GitHub Actions on a cron. For each schedule item whose post_at time
has arrived and that hasn't been posted yet, it:
  1. tells Instagram to create a reel from the clip's public GitHub URL,
  2. waits for Instagram to finish fetching/processing it,
  3. publishes it,
  4. records the result back into schedule.json.

Stdlib only (no pip installs needed). Reads IG_USER_ID and IG_ACCESS_TOKEN from
environment (GitHub repo secrets). Clip URLs are derived automatically from the
repository, so nothing is hardcoded.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GRAPH_API = "https://graph.facebook.com/v23.0"
SCHEDULE_FILE = Path("schedule.json")
MAX_ATTEMPTS = 5            # give up on a clip after this many failed tries
CONTAINER_POLL_SECONDS = 5
CONTAINER_MAX_WAIT = 240    # seconds to wait for Instagram to process one reel

IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
IG_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
# GitHub sets these automatically inside Actions, e.g. "user/repo" and "main".
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "").strip()
GITHUB_REF_NAME = os.environ.get("GITHUB_REF_NAME", "main").strip() or "main"


def graph_request(method, path, *, params=None, data=None, timeout=60):
    url = f"{GRAPH_API}{path}"
    query = urllib.parse.urlencode(params or {}, doseq=True)
    if query:
        url = f"{url}?{query}"
    body = None
    headers = {}
    if data is not None:
        body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(detail).get("error", {}).get("message") or detail
        except Exception:
            msg = detail or exc.reason
        raise RuntimeError(f"Instagram API error ({exc.code}): {msg}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error reaching Instagram: {exc.reason}") from exc


def clip_url(filename):
    """Public raw URL of a clip committed under clips/ in this repo."""
    quoted = urllib.parse.quote(filename)
    return f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{GITHUB_REF_NAME}/clips/{quoted}"


def post_reel(item):
    video_url = clip_url(item["file"])
    print(f"  video_url = {video_url}")

    media_data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": item.get("caption", ""),
        "access_token": IG_TOKEN,
    }
    # Meta fetches the cover image from this public HTTPS URL when provided.
    cover_url = str(item.get("cover_url", "")).strip()
    if cover_url:
        media_data["cover_url"] = cover_url

    container = graph_request(
        "POST", f"/{IG_USER_ID}/media",
        data=media_data,
        timeout=120,
    )
    container_id = str(container.get("id", "")).strip()
    if not container_id:
        raise RuntimeError("Instagram did not return a container id")

    # Wait for Instagram to fetch + process the video before publishing.
    waited = 0
    while True:
        status = graph_request(
            "GET", f"/{container_id}",
            params={"fields": "status_code", "access_token": IG_TOKEN},
        )
        code = str(status.get("status_code", "IN_PROGRESS")).upper()
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram could not process the reel (status {code})")
        if waited >= CONTAINER_MAX_WAIT:
            raise RuntimeError("Instagram took too long to process the reel")
        time.sleep(CONTAINER_POLL_SECONDS)
        waited += CONTAINER_POLL_SECONDS

    published = graph_request(
        "POST", f"/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN},
        timeout=120,
    )
    media_id = str(published.get("id", "")).strip()
    if not media_id:
        raise RuntimeError("Instagram did not return a published media id")

    details = graph_request(
        "GET", f"/{media_id}",
        params={"fields": "permalink", "access_token": IG_TOKEN},
    )
    return media_id, details.get("permalink", "")


def main():
    if not IG_USER_ID or not IG_TOKEN:
        raise SystemExit("Missing IG_USER_ID / IG_ACCESS_TOKEN secrets.")
    if not SCHEDULE_FILE.exists():
        print("No schedule.json — nothing to do.")
        return

    schedule = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    items = schedule.get("items", [])
    now = datetime.now(timezone.utc)
    changed = False
    posted = 0

    for item in items:
        if item.get("posted"):
            continue
        if item.get("attempts", 0) >= MAX_ATTEMPTS:
            continue
        try:
            post_at = datetime.fromisoformat(str(item["post_at"]).replace("Z", "+00:00"))
            if post_at.tzinfo is None:
                post_at = post_at.replace(tzinfo=timezone.utc)
        except Exception:
            item["error"] = "bad post_at format"
            item["attempts"] = item.get("attempts", 0) + 1
            changed = True
            continue

        if post_at > now:
            continue  # not due yet

        print(f"Posting due reel: {item['file']} (scheduled {item['post_at']})")
        item["attempts"] = item.get("attempts", 0) + 1
        try:
            media_id, permalink = post_reel(item)
            item["posted"] = True
            item["media_id"] = media_id
            item["permalink"] = permalink
            item["error"] = None
            posted += 1
            print(f"  OK -> {permalink or media_id}")
        except Exception as exc:
            item["error"] = str(exc)
            print(f"  FAILED: {exc}")
        changed = True

    if changed:
        SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    print(f"Done. Posted {posted} reel(s) this run.")


if __name__ == "__main__":
    main()

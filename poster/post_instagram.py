"""Post today's GREENLINE Reel to Instagram.

Reads schedule/instagram.json, finds the entry for today (Pacific time),
posts it through the Instagram API with Instagram Login, and records it in
schedule/posted.json so it never posts twice.

Env:
  IG_TOKEN   long-lived Instagram user token (GitHub secret, never printed)
  DRY_RUN    "true" prepares the Reel but does not publish it
  POST_DATE  optional YYYY-MM-DD to use instead of today
  GRAPH_URL  optional API base, for local tests
  MEDIA_URL  optional base for video links, for local tests
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULE = os.path.join(ROOT, "schedule", "instagram.json")
POSTED = os.path.join(ROOT, "schedule", "posted.json")
GRAPH = os.environ.get("GRAPH_URL", "https://graph.instagram.com/v26.0").rstrip("/")
REFRESH_URL = os.environ.get("GRAPH_URL", "https://graph.instagram.com").rstrip("/") + "/refresh_access_token"
REPO = os.environ.get("GITHUB_REPOSITORY", "lafferty767-lang/greenline-media")
MEDIA = os.environ.get("MEDIA_URL", f"https://raw.githubusercontent.com/{REPO}/main").rstrip("/")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
POLL_TRIES = int(os.environ.get("POLL_TRIES", "40"))


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def call(method, url, token, params=None, fatal=True):
    """Call the Graph API. Error messages print the path only, so the token never reaches the log."""
    params = dict(params or {}, access_token=token)
    path = url.replace(GRAPH, "")
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
            detail = f"{err.get('message')} (code {err.get('code')}, subcode {err.get('error_subcode')})"
        except Exception:
            detail = e.reason
        msg = f"Instagram API {method} {path} failed: HTTP {e.code} {detail}"
        if not fatal:
            print(f"::warning::{msg}")
            return None
        fail(msg)


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def main():
    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        fail("IG_TOKEN secret is missing. Add it in Settings > Secrets and variables > Actions.")
    dry = os.environ.get("DRY_RUN", "false").lower() == "true"
    day = os.environ.get("POST_DATE") or datetime.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()

    entry = next((e for e in load(SCHEDULE, []) if e["date"] == day), None)
    if not entry:
        print(f"Nothing scheduled for {day}.")
        return
    posted = load(POSTED, [])
    if not dry and any(p["date"] == day for p in posted):
        print(f"{day} already posted, skipping.")
        return

    me = call("GET", f"{GRAPH}/me", token, {"fields": "user_id,username"})
    ig_id = me.get("user_id") or me.get("id")
    print(f"Account: @{me.get('username')}  Post for {day}: {entry['video']}" + ("  (dry run)" if dry else ""))

    video_url = f"{MEDIA}/{urllib.parse.quote(entry['video'])}"
    container = call("POST", f"{GRAPH}/{ig_id}/media", token, {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": entry["caption"],
        "share_to_feed": "true",
    })["id"]

    for _ in range(POLL_TRIES):
        status = call("GET", f"{GRAPH}/{container}", token, {"fields": "status_code,status"})
        code = status.get("status_code")
        print(f"Video processing: {code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            fail(f"Instagram could not process {entry['video']}: {status.get('status')}")
        time.sleep(POLL_SECONDS)
    else:
        fail("Instagram took too long to process the video.")

    if dry:
        print("Dry run OK: the Reel was prepared but not published.")
    else:
        media_id = call("POST", f"{GRAPH}/{ig_id}/media_publish", token, {"creation_id": container})["id"]
        posted.append({"date": day, "video": entry["video"], "media_id": media_id})
        with open(POSTED, "w") as f:
            json.dump(posted, f, indent=2)
            f.write("\n")
        print(f"Posted {entry['video']} (media {media_id}).")

    refresh = call("GET", REFRESH_URL, token, {"grant_type": "ig_refresh_token"}, fatal=False)
    if not refresh:
        print("Key not refreshed this time (it must be at least a day old). Posting still worked.")
        return
    days = int(refresh.get("expires_in", 0)) // 86400
    if refresh.get("access_token") and refresh["access_token"] != token:
        print("::warning::Instagram issued a new key. Generate a fresh token and update IG_TOKEN before the old one runs out.")
    print(f"Key refreshed, good for about {days} more days.")


if __name__ == "__main__":
    main()

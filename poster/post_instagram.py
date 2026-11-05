"""Post today's GREENLINE Reel to Instagram.

Reads schedule/instagram.json, picks the oldest entry that is due today or
earlier (Pacific time) and not posted yet, posts it through Meta's official
Instagram API, and records it in schedule/posted.json. At most one Reel goes
out per day, and a missed day is caught up on the next run.

GitHub starts scheduled runs late and skips many of them, so the workflow is
set to run every two hours. A run that starts up to MAX_WAIT_HOURS before
POST_AT (Pacific) waits and posts at POST_AT; a run after POST_AT posts right
away. Earlier runs, and runs after the day's Reel is out, do nothing.

IG_TOKEN can be either kind of Meta key:
  - a Facebook Page token (starts with EAA) for the GREENLINE Page that the
    Instagram account is linked to. Made from a long-lived user token, it
    never expires. A long-lived Facebook user token also works (60 days).
  - an Instagram login token (starts with IG), refreshed on every run.

Env:
  IG_TOKEN   the key above (GitHub secret, never printed)
  DRY_RUN    "true" prepares the Reel but does not publish it
  POST_DATE  optional YYYY-MM-DD to use instead of today
  POST_AT    Pacific time of day (HH:MM) to post, default 18:00
  MAX_WAIT_HOURS  how long a run may wait for POST_AT, default 5.5 (jobs stop at 6 hours)
  POST_NOW   "true" posts whatever the time (manual runs)
  IG_UPLOAD  "auto" (link first, then file upload if that fails), "url" or "file"
  FB_GRAPH_URL / IG_GRAPH_URL / MEDIA_URL  optional overrides, for local tests
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
FB_GRAPH = os.environ.get("FB_GRAPH_URL", "https://graph.facebook.com/v26.0").rstrip("/")
IG_HOST = os.environ.get("IG_GRAPH_URL", "https://graph.instagram.com").rstrip("/")
IG_GRAPH = IG_HOST if "IG_GRAPH_URL" in os.environ else IG_HOST + "/v26.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "lafferty767-lang/greenline-media")
MEDIA = os.environ.get("MEDIA_URL", f"https://raw.githubusercontent.com/{REPO}/main").rstrip("/")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
POLL_TRIES = int(os.environ.get("POLL_TRIES", "40"))
ERROR_POLLS = int(os.environ.get("ERROR_POLLS", "6"))
RUPLOAD = os.environ.get("RUPLOAD_URL", "https://rupload.facebook.com/ig-api-upload").rstrip("/")
UPLOAD = os.environ.get("IG_UPLOAD", "auto")


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def call(method, url, token, params=None, fatal=True, warn=True):
    """Call the Graph API. Error messages print the path only, so the token never reaches the log."""
    params = dict(params or {}, access_token=token)
    path = urllib.parse.urlparse(url).path
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
            if warn:
                print(f"::warning::{msg}")
            return None
        fail(msg)


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def make_container(graph, token, ig_id, entry, how):
    """Start a Reel container from the video's public link ("url") or by uploading the file ("file")."""
    params = {"media_type": "REELS", "caption": entry["caption"], "share_to_feed": "true"}
    if how == "url":
        params["video_url"] = f"{MEDIA}/{urllib.parse.quote(entry['video'])}"
        return call("POST", f"{graph}/{ig_id}/media", token, params)["id"]
    params["upload_type"] = "resumable"
    made = call("POST", f"{graph}/{ig_id}/media", token, params)
    path = os.path.join(ROOT, entry["video"])
    size = os.path.getsize(path)
    uri = made.get("uri") or f"{RUPLOAD}/{graph.rstrip('/').rsplit('/', 1)[-1]}/{made['id']}"
    with open(path, "rb") as f:
        req = urllib.request.Request(uri, data=f.read(), method="POST", headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            json.load(r)
    except urllib.error.HTTPError as e:
        print(f"::warning::Instagram file upload failed: HTTP {e.code} {e.reason}")
    return made["id"]


def wait_ready(graph, token, container):
    """Poll a container until it is ready. Returns None when ready, else what went wrong.
    An ERROR can clear up on its own, so it is given a few more polls before giving up."""
    errors = 0
    for _ in range(POLL_TRIES):
        status = call("GET", f"{graph}/{container}", token, {"fields": "status_code,status"})
        code = status.get("status_code")
        print(f"Video processing: {code}", flush=True)
        if code == "FINISHED":
            return None
        if code == "EXPIRED":
            return status.get("status") or code
        if code == "ERROR":
            errors += 1
            if errors >= ERROR_POLLS:
                return status.get("status") or code
        time.sleep(POLL_SECONDS)
    return "it took too long to process the video"


def find_account(token):
    """Return (graph base, token to post with, Instagram account id, username)."""
    if token.startswith("IG"):
        me = call("GET", f"{IG_GRAPH}/me", token, {"fields": "user_id,username"})
        return IG_GRAPH, token, me.get("user_id") or me.get("id"), me.get("username")

    fields = "instagram_business_account{id,username}"
    me = call("GET", f"{FB_GRAPH}/me", token, {"fields": fields}, fatal=False, warn=False) or {}
    if me.get("instagram_business_account"):  # a Page token
        ig = me["instagram_business_account"]
        return FB_GRAPH, token, ig["id"], ig.get("username")

    # A user token: use the first Page that has an Instagram account linked.
    pages = call("GET", f"{FB_GRAPH}/me/accounts", token, {"fields": f"name,access_token,{fields}"})
    for page in pages.get("data", []):
        if page.get("instagram_business_account"):
            ig = page["instagram_business_account"]
            return FB_GRAPH, page["access_token"], ig["id"], ig.get("username")
    fail("This key can't see a Facebook Page with an Instagram account linked. Link @playgreenline2026 to the GREENLINE Page, then make the key again.")


def main():
    dry = os.environ.get("DRY_RUN", "false").lower() == "true"
    now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    day = os.environ.get("POST_DATE") or now.date().isoformat()
    on_time = not (dry or os.environ.get("POST_DATE") or os.environ.get("POST_NOW", "false").lower() == "true")
    h, m = map(int, os.environ.get("POST_AT", "18:00").split(":"))
    post_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    max_wait = datetime.timedelta(hours=float(os.environ.get("MAX_WAIT_HOURS", "5.5")))
    if on_time and now < post_at - max_wait:
        print(f"It's {now:%H:%M} Pacific, too early to wait for {post_at:%H:%M}, so this run does nothing.")
        return

    # One Reel a day: the oldest scheduled entry that is due and not posted yet,
    # so a day that failed (for example before IG_TOKEN was set) is caught up later.
    posted = load(POSTED, [])
    if not dry and any(p.get("posted_on") == day for p in posted):
        print(f"Already posted a Reel on {day}, skipping.")
        return
    done = {p["date"] for p in posted}
    due = sorted((e for e in load(SCHEDULE, []) if e["date"] <= day and e["date"] not in done), key=lambda e: e["date"])
    if not due:
        print(f"Nothing due on {day}.")
        return
    entry = due[0]

    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        print("::notice::IG_TOKEN secret isn't set, so nothing was posted. Add it in Settings > Secrets and variables > Actions to turn posting on.")
        return

    if on_time and now < post_at:
        print(f"Waiting until {post_at:%H:%M} Pacific to post {entry['video']}.", flush=True)
        time.sleep((post_at - datetime.datetime.now(post_at.tzinfo)).total_seconds())

    graph, post_token, ig_id, username = find_account(token)
    print(f"Account: @{username}  Posting {entry['video']} (scheduled {entry['date']})" + ("  (dry run)" if dry else ""))

    # Meta sometimes fails to fetch or process a video it is pointed at (error 2207077),
    # so a failed try is repeated, the second time uploading the file itself.
    order = {"url": ["url"], "file": ["file"]}.get(UPLOAD, ["url", "file", "url"])
    for attempt, how in enumerate(order, 1):
        container = make_container(graph, post_token, ig_id, entry, how)
        problem = wait_ready(graph, post_token, container)
        if not problem:
            break
        print(f"::warning::Try {attempt} ({'link' if how == 'url' else 'file upload'}) failed: {problem}")
    else:
        fail(f"Instagram could not process {entry['video']} after {len(order)} tries: {problem}. The next run tries again.")

    if dry:
        print("Dry run OK: the Reel was prepared but not published.")
    else:
        media_id = call("POST", f"{graph}/{ig_id}/media_publish", post_token, {"creation_id": container})["id"]
        posted.append({"date": entry["date"], "video": entry["video"], "posted_on": day, "media_id": media_id})
        with open(POSTED, "w") as f:
            json.dump(posted, f, indent=2)
            f.write("\n")
        print(f"Posted {entry['video']} (media {media_id}).")

    if token.startswith("IG"):
        refresh = call("GET", f"{IG_HOST}/refresh_access_token", token, {"grant_type": "ig_refresh_token"}, fatal=False)
        if refresh:
            print(f"Key refreshed, good for about {int(refresh.get('expires_in', 0)) // 86400} more days.")


if __name__ == "__main__":
    main()

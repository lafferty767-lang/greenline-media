"""Post today's GREENLINE video to TikTok and YouTube Shorts through Buffer.

Reads schedule/buffer.json and, for each network, picks the oldest entry that is
due today or earlier (Pacific time) and not posted there yet. It sends that
video to the Buffer channel through Buffer's official API to publish right away,
waits to see it go out, and records it in schedule/buffer-posted.json. At most
one video goes to each network per day, and a missed or failed day is caught up
on the next run.

Each schedule entry has a date, a video path, and a block for each network it
should go to:
  "tiktok":  {"caption": "..."}
  "youtube": {"title": "...", "description": "..."}

Env:
  BUFFER_API_KEY  Buffer personal API key (GitHub secret, never printed)
  DRY_RUN         "true" checks the key, the channels and the post fields by
                  saving a Buffer draft and deleting it again; nothing is published
  POST_DATE       optional YYYY-MM-DD to use instead of today
  YOUTUBE_MADE_FOR_KIDS  "true" or "false", YouTube's audience setting
  BUFFER_URL / MEDIA_URL / POLL_SECONDS / POLL_TRIES  optional overrides, for local tests
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
SCHEDULE = os.path.join(ROOT, "schedule", "buffer.json")
POSTED = os.path.join(ROOT, "schedule", "buffer-posted.json")
API = os.environ.get("BUFFER_URL", "https://api.buffer.com")
REPO = os.environ.get("GITHUB_REPOSITORY", "lafferty767-lang/greenline-media")
MEDIA = os.environ.get("MEDIA_URL", f"https://raw.githubusercontent.com/{REPO}/main").rstrip("/")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "15"))
POLL_TRIES = int(os.environ.get("POLL_TRIES", "16"))
MADE_FOR_KIDS = os.environ.get("YOUTUBE_MADE_FOR_KIDS", "true").lower() == "true"
NETWORKS = {"tiktok": "TikTok", "youtube": "YouTube"}

CHANNELS = """query($org: OrganizationId!) {
  channels(input: {organizationId: $org}) { id name service isDisconnected isLocked isQueuePaused }
}"""
CREATE = """mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}"""
STATUS = """query($id: PostId!) {
  post(input: {id: $id}) { status externalLink error { message supportUrl } }
}"""
DELETE = """mutation($id: PostId!) {
  deletePost(input: {id: $id}) { __typename ... on DeletePostSuccess { id } }
}"""


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def gql(key, query, variables=None, fatal=True):
    """Call Buffer's GraphQL API. Errors print Buffer's message only, so the key never reaches the log."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "greenline-poster"}
    for attempt in range(4):
        req = urllib.request.Request(API, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(30 * 2 ** attempt)
                continue
            try:
                out = json.load(e)
            except Exception:
                out = {"errors": [{"message": f"HTTP {e.code} {e.reason}"}]}
        errors = out.get("errors") or []
        codes = [(err.get("extensions") or {}).get("code") for err in errors]
        if "RATE_LIMIT_EXCEEDED" in codes and attempt < 3:
            time.sleep(30 * 2 ** attempt)
            continue
        if out.get("data") is None or (errors and not out.get("data")):
            msg = "; ".join(f"{err.get('message')} ({code})" for err, code in zip(errors, codes)) or "no data"
            if "UNAUTHORIZED" in codes:
                msg += ". The BUFFER_API_KEY secret was rejected: make a new key in Buffer and save it again."
            if not fatal:
                print(f"::warning::Buffer API: {msg}")
                return None
            fail(f"Buffer API: {msg}")
        for err in errors:
            print(f"::warning::Buffer API: {err.get('message')}")
        return out["data"]
    fail("Buffer API kept saying 'too many requests'.")


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save(posted):
    with open(POSTED, "w") as f:
        json.dump(posted, f, indent=2, ensure_ascii=False)
        f.write("\n")


def check(key, rec, tries=1):
    """Refresh a post record from Buffer until it is sent or failed (or tries run out)."""
    for i in range(tries):
        data = gql(key, STATUS, {"id": rec["post_id"]}, fatal=False)
        post = (data or {}).get("post")
        if post:
            rec["status"] = post["status"]
            if post.get("externalLink"):
                rec["link"] = post["externalLink"]
            if post.get("error"):
                rec["error"] = post["error"]["message"] + (f" ({post['error']['supportUrl']})" if post["error"].get("supportUrl") else "")
        if rec.get("status") in ("sent", "error") or i == tries - 1:
            return
        time.sleep(POLL_SECONDS)


def report(rec, problems):
    label = NETWORKS[rec["network"]]
    if rec["status"] == "sent":
        print(f"{label}: {rec['video']} is live" + (f" at {rec['link']}" if rec.get("link") else "") + ".")
    elif rec["status"] == "error":
        problems.append(f"{label}: Buffer couldn't publish {rec['video']}: {rec.get('error', 'no reason given')}. It will be tried again on the next run.")
    else:
        print(f"{label}: {rec['video']} is still publishing ({rec['status']}); the next run checks on it.")


def build_input(net, entry, channel_id):
    inp = {
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "shareNow",
        "assets": [{"video": {"url": f"{MEDIA}/{urllib.parse.quote(entry['video'])}"}}],
    }
    if net == "tiktok":
        inp["text"] = entry["tiktok"]["caption"]
    else:
        yt = entry["youtube"]
        inp["text"] = yt.get("description", "")
        inp["metadata"] = {"youtube": {
            "title": yt["title"],
            "categoryId": "20",  # Gaming
            "privacy": "public",
            "madeForKids": MADE_FOR_KIDS,
            "notifySubscribers": True,
        }}
    return inp


def main():
    dry = os.environ.get("DRY_RUN", "false").lower() == "true"
    day = os.environ.get("POST_DATE") or datetime.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    schedule = load(SCHEDULE, [])
    posted = load(POSTED, [])

    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key:
        print("::notice::BUFFER_API_KEY secret isn't set, so nothing was posted. Add it in Settings > Secrets and variables > Actions to turn TikTok and YouTube posting on.")
        return

    orgs = gql(key, "query { account { organizations { id name } } }")["account"]["organizations"]
    if not orgs:
        fail("This Buffer key can't see a Buffer organization.")
    channels = gql(key, CHANNELS, {"org": orgs[0]["id"]})["channels"]
    problems = []

    # Posts from earlier runs that were still publishing: see how they ended.
    yesterday = (datetime.date.fromisoformat(day) - datetime.timedelta(days=1)).isoformat()
    for rec in posted:
        if rec.get("status") not in ("sent", "error"):
            check(key, rec)
            report(rec, problems)
            if rec["status"] not in ("sent", "error") and rec["posted_on"] < yesterday:
                problems.append(f"{NETWORKS[rec['network']]}: {rec['video']} has been stuck in Buffer since {rec['posted_on']}. Check it at publish.buffer.com.")
    save(posted)

    for net, label in NETWORKS.items():
        channel = next((c for c in channels if c["service"] == net), None)
        if not channel:
            print(f"::notice::No {label} channel is connected in Buffer, so {label} was skipped.")
            continue
        if channel["isDisconnected"] or channel["isLocked"] or channel["isQueuePaused"]:
            state = "disconnected" if channel["isDisconnected"] else "locked" if channel["isLocked"] else "paused"
            problems.append(f"{label} ({channel['name']}) is {state} in Buffer. Reconnect or unpause it at publish.buffer.com.")
            continue

        mine = [r for r in posted if r["network"] == net and r.get("status") != "error"]
        if not dry and any(r["posted_on"] == day for r in mine):
            print(f"{label}: already posted on {day}, skipping.")
            continue
        done = {r["date"] for r in mine}
        waiting = sorted((e for e in schedule if net in e and e["date"] not in done), key=lambda e: e["date"])
        due = [e for e in waiting if e["date"] <= day]
        if dry and not due:
            due = waiting  # a test run checks the next upcoming post instead
        if not due:
            print(f"{label}: nothing due on {day}.")
            continue
        entry = due[0]
        print(f"{label} ({channel['name']}): posting {entry['video']} (scheduled {entry['date']})" + ("  (dry run)" if dry else ""))

        inp = build_input(net, entry, channel["id"])
        if dry:
            inp.update(mode="addToQueue", saveToDraft=True)
        result = gql(key, CREATE, {"input": inp})["createPost"]
        if not result.get("post"):
            problems.append(f"{label}: Buffer refused {entry['video']}: {result.get('message') or result.get('__typename')}")
            continue
        post = result["post"]

        if dry:
            gone = gql(key, DELETE, {"id": post["id"]}, fatal=False)
            print(f"Dry run OK: Buffer accepted the {label} post as a draft" + (" and it was deleted again." if gone else " (delete it in Buffer's Drafts)."))
            continue

        rec = {"network": net, "date": entry["date"], "video": entry["video"], "posted_on": day,
               "post_id": post["id"], "status": post["status"]}
        posted.append(rec)
        save(posted)
        check(key, rec, POLL_TRIES)
        save(posted)
        report(rec, problems)

    for p in problems:
        print(f"::error::{p}")
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()

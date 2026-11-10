"""Collect how each posted GREENLINE video is doing and save it to stats/latest.json.

Read-only. Buffer gives the numbers for TikTok, YouTube Shorts and Facebook Reels
(Buffer refreshes them about once a day), and the Instagram key gives likes and
comments for each Reel (plus views and reach when the key is allowed to read insights).

Env:
  BUFFER_API_KEY  Buffer personal API key (GitHub secret, never printed)
  IG_TOKEN        Instagram key (GitHub secret, never printed)
Either one may be missing; that network is then skipped.
"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_buffer as pb  # noqa: E402
import post_instagram as ig  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "stats", "latest.json")
BATCH = 8
INSIGHTS = "views,reach,likes,comments,saved,shares,total_interactions,ig_reels_avg_watch_time"


def buffer_stats(key):
    posted = [r for r in pb.load(pb.POSTED, []) if r.get("post_id") and r.get("status") == "sent"]
    rows = []
    for i in range(0, len(posted), BATCH):
        chunk = posted[i:i + BATCH]
        parts = [
            f'p{n}: post(input: {{id: "{r["post_id"]}"}}) '
            "{ id status metricsUpdatedAt metrics { type name value unit } }"
            for n, r in enumerate(chunk)
        ]
        data = pb.gql(key, "query {\n" + "\n".join(parts) + "\n}", fatal=False) or {}
        for n, r in enumerate(chunk):
            post = data.get(f"p{n}") or {}
            metrics = {m["type"]: m["value"] for m in post.get("metrics") or []}
            rows.append({
                "network": r["network"], "date": r["date"], "video": os.path.basename(r["video"]),
                "link": r.get("link"), "updated": post.get("metricsUpdatedAt"), "metrics": metrics,
            })
    return rows


def instagram_stats(token):
    graph, token, ig_id, username = ig.find_account(token)
    account = ig.call("GET", f"{graph}/{ig_id}", token, {"fields": "followers_count,media_count"}, fatal=False) or {}
    rows, insights_ok = [], True
    for r in ig.load(ig.POSTED, []):
        if not r.get("media_id"):
            continue
        fields = "like_count,comments_count,permalink,timestamp"
        media = ig.call("GET", f"{graph}/{r['media_id']}", token, {"fields": fields}, fatal=False, warn=False) or {}
        metrics = {k: media[k] for k in ("like_count", "comments_count") if k in media}
        if insights_ok:
            got = ig.call("GET", f"{graph}/{r['media_id']}/insights", token, {"metric": INSIGHTS}, fatal=False)
            if got is None:
                insights_ok = False  # this key can't read insights; don't ask again for every Reel
            for m in (got or {}).get("data", []):
                values = m.get("values") or [{}]
                metrics[m["name"]] = values[0].get("value")
        rows.append({
            "network": "instagram", "date": r["date"], "video": os.path.basename(r["video"]),
            "link": media.get("permalink"), "posted": media.get("timestamp"), "metrics": metrics,
        })
    return {"username": username, **account}, rows


def table(rows):
    lines = ["| Network | Slot | Video | Numbers |", "| --- | --- | --- | --- |"]
    for r in sorted(rows, key=lambda r: (r["network"], r["date"])):
        nums = ", ".join(f"{k} {v:g}" if isinstance(v, (int, float)) else f"{k} {v}" for k, v in r["metrics"].items())
        lines.append(f"| {r['network']} | {r['date']} | {r['video']} | {nums or 'no numbers yet'} |")
    return "\n".join(lines)


def main():
    out = {"collected": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "posts": []}
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if key:
        out["posts"] += buffer_stats(key)
    else:
        print("::notice::No BUFFER_API_KEY, skipping TikTok, YouTube and Facebook.")
    token = os.environ.get("IG_TOKEN", "").strip()
    if token:
        try:
            out["instagram_account"], rows = instagram_stats(token)
            out["posts"] += rows
        except SystemExit:
            print("::warning::Instagram numbers were skipped this time.")
    else:
        print("::notice::No IG_TOKEN, skipping Instagram.")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    text = table(out["posts"])
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("## How the videos are doing\n\n" + text + "\n")


if __name__ == "__main__":
    main()

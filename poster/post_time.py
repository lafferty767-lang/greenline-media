"""What time of day (Pacific) a day's post goes out.

schedule/post-times.json looks like
    {"default": "18:00", "dates": {"2026-11-12": "15:30"}}
A day listed under "dates" uses that time; every other day uses "default".
If the file is missing or broken, the fallback passed in is used, so a bad
edit to that file can never stop the daily post.
"""

import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schedule", "post-times.json")
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def post_at_for(day, fallback="18:00", path=PATH):
    """The HH:MM (Pacific) to post at on day (YYYY-MM-DD)."""
    try:
        with open(path) as f:
            times = json.load(f)
        chosen = times.get("dates", {}).get(day) or times.get("default") or fallback
    except (OSError, ValueError, AttributeError):
        return fallback
    if not isinstance(chosen, str) or not HHMM.match(chosen):
        print(f"::warning::schedule/post-times.json has a time that isn't HH:MM for {day}, so {fallback} is used.")
        return fallback
    return chosen

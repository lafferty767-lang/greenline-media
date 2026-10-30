# GREENLINE media

Public promo videos for GREENLINE, the co-op cube zombie shooter by Tufufal Studios.
Files here are linked by the social media scheduler, so only finished promo content goes in this repo.

- `videos/` vertical 1080x1920 clips for TikTok, Instagram Reels and YouTube Shorts
- `tools/make-beta-form.gs` Google Apps Script that creates the beta signup form
- `schedule/instagram.json` which Reel posts on which day (Pacific time); `schedule/posted.json` records what already went out
- `poster/post_instagram.py` + `.github/workflows/instagram.yml` post the day's Reel every evening using the `IG_TOKEN` secret (a Facebook Page key for the GREENLINE Page linked to @playgreenline2026)
- `schedule/buffer.json` which video goes to TikTok and YouTube Shorts on which day (Pacific time); `schedule/buffer-posted.json` records what went out
- `poster/post_buffer.py` + `.github/workflows/buffer.yml` send the day's video to TikTok and YouTube every evening through Buffer's official API, using the `BUFFER_API_KEY` secret (a personal key from a free Buffer account with both channels connected)
- `weekly/` the week's posting pack: video links, captions, YouTube titles and how to schedule them by hand

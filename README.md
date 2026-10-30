# GREENLINE media

Public promo videos for GREENLINE, the co-op cube zombie shooter by Tufufal Studios.
Files here are linked by the social media scheduler, so only finished promo content goes in this repo.

- `videos/` vertical 1080x1920 clips for TikTok, Instagram Reels and YouTube Shorts
- `tools/make-beta-form.gs` Google Apps Script that creates the beta signup form
- `schedule/instagram.json` which Reel posts on which day (Pacific time); `schedule/posted.json` records what already went out
- `poster/post_instagram.py` + `.github/workflows/instagram.yml` can post the day's Reel using the `IG_TOKEN` secret (daily schedule paused; Reels are scheduled in the Instagram app for now)
- `weekly/` the week's Instagram + YouTube pack: video links, captions, titles and how to schedule them

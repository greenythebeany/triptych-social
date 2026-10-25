# triptych-social

Reels for [Triptych](https://greenybeany.dev/triptych/)'s Instagram, and the workflow that posts them.

- `reels/`: one `.mp4`, a `.jpg` cover and a `.txt` caption per reel. GitHub Pages serves them, so Instagram can fetch them.
- `schedule.json`: which reel goes out on which date, at 18:00 Bratislava time. `posted` is filled in after a reel goes out.
- `.github/workflows/post.yml`: runs every day. If a reel is due, it posts it through Instagram's official API (`post.py`).

## Secrets (Settings → Secrets and variables → Actions)

- `IG_TOKEN`: the Instagram access token from the Meta app (Triptych Social → Instagram → API setup with Instagram login → Generate token).
- `GH_PAT`: a fine-grained GitHub token for this repo only, with **Secrets: read and write**. The workflow uses it to save the renewed Instagram token every week. Without it, the token expires after 60 days.

## Adding a reel

Put `NN-name.mp4`, `.jpg` and `.txt` in `reels/`, add `{"id": "NN-name", "date": "YYYY-MM-DD"}` to `schedule.json`, and push.

## Testing

Actions → Post reel → Run workflow. With **dry run** on, it checks the token, the files and the Instagram account, and posts nothing.

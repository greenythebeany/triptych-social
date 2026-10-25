"""Posts the day's Triptych reel to Instagram through the official Instagram
API (Instagram Login), then records it in schedule.json.

Run by .github/workflows/post.yml. Uses only the Python standard library.

Environment
  IG_TOKEN    the Instagram access token (repository secret)
  GH_PAT      optional: a fine-grained token allowed to write this repo's
              secrets, so a refreshed IG_TOKEN can be saved
  FORCE_ID    optional: post this reel now, whatever the date (manual runs)
  DRY_RUN     "1" = check everything, post nothing
"""
import json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SCHEDULE = HERE / 'schedule.json'
API = 'https://graph.instagram.com/v21.0'
TZ = ZoneInfo('Europe/Bratislava')
TOKEN = os.environ['IG_TOKEN']
DRY = os.environ.get('DRY_RUN') == '1'


def call(method, url, **params):
    data = urllib.parse.urlencode({**params, 'access_token': TOKEN}).encode()
    req = urllib.request.Request(url if method == 'POST' else f'{url}?{data.decode()}', data=data if method == 'POST' else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # never print the request (it holds the token), only Instagram's answer
        sys.exit(f'Instagram API error {e.code}: {e.read().decode(errors="replace")[:500]}')


def reachable(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=30) as r:
            return r.status == 200, r.headers.get('Content-Type', '')
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def refresh_token(state):
    """Long-lived tokens last 60 days; refresh once a week and save the new one."""
    last = state.get('token_refreshed')
    if last and datetime.fromisoformat(last) > datetime.now(timezone.utc) - timedelta(days=7):
        return
    if not os.environ.get('GH_PAT'):
        print('token refresh skipped: no GH_PAT secret to save the new token with')
        return
    # Instagram only renews tokens that are at least 24 hours old; a refusal
    # here is not worth failing the post over, the next run tries again.
    try:
        q = urllib.parse.urlencode({'grant_type': 'ig_refresh_token', 'access_token': TOKEN})
        with urllib.request.urlopen(f'https://graph.instagram.com/refresh_access_token?{q}', timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        print(f'token refresh skipped ({e.code}): {e.read().decode(errors="replace")[:200]}')
        return
    new = data.get('access_token')
    if not new:
        print('token refresh: no token returned'); return
    if not DRY:
        subprocess.run(['gh', 'secret', 'set', 'IG_TOKEN', '--body', new], check=True,
                       env={**os.environ, 'GH_TOKEN': os.environ['GH_PAT']}, stdout=subprocess.DEVNULL)
        state['token_refreshed'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    print('token refreshed, valid for', round(data.get('expires_in', 0) / 86400), 'days')


def main():
    sched = json.loads(SCHEDULE.read_text(encoding='utf-8'))
    now = datetime.now(TZ)
    force = os.environ.get('FORCE_ID')
    if force:
        due = [p for p in sched['posts'] if p['id'] == force]
    else:
        # each post has a local time ("at"); post the earliest one that is due,
        # but not one that is more than 6 hours late (a missed slot is skipped)
        due = sorted((p for p in sched['posts'] if not p.get('posted')
                      and now - timedelta(hours=6) <= datetime.fromisoformat(p['at']).replace(tzinfo=TZ) <= now),
                     key=lambda p: p['at'])
    refresh_token(sched)
    if not due:
        print(f'nothing due at {now:%Y-%m-%d %H:%M} ({TZ.key})')
        SCHEDULE.write_text(json.dumps(sched, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        return
    post = due[0]
    base = sched['base_url'].rstrip('/')
    video, cover = f"{base}/reels/{post['id']}.mp4", f"{base}/reels/{post['id']}.jpg"
    caption = (HERE / 'reels' / f"{post['id']}.txt").read_text(encoding='utf-8')
    for url in (video, cover):
        ok, info = reachable(url)
        if not ok:
            sys.exit(f'{url} is not reachable ({info}); is GitHub Pages deployed?')
    me = call('GET', f'{API}/me', fields='user_id,username')
    print(f"posting {post['id']} to @{me['username']}")
    if DRY:
        print('dry run: stopping before upload'); return
    container = call('POST', f"{API}/{me['user_id']}/media", media_type='REELS', video_url=video,
                     cover_url=cover, caption=caption, share_to_feed='true')['id']
    for _ in range(60):  # Instagram downloads and processes the video
        status = call('GET', f'{API}/{container}', fields='status_code,status')
        if status.get('status_code') == 'FINISHED':
            break
        if status.get('status_code') in ('ERROR', 'EXPIRED'):
            sys.exit(f'Instagram could not process the video: {status}')
        time.sleep(10)
    else:
        sys.exit('Instagram took too long to process the video')
    media = call('POST', f"{API}/{me['user_id']}/media_publish", creation_id=container)['id']
    post['posted'] = datetime.now(TZ).isoformat(timespec='minutes')
    post['media_id'] = media
    SCHEDULE.write_text(json.dumps(sched, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('published', post['id'], media)


if __name__ == '__main__':
    main()

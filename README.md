# Instagram Reel Auto-Poster (GitHub Actions)

Posts Instagram reels on a schedule — **free, no credit card, laptop can be off.**
GitHub runs a job every 15 minutes; any reel whose time has come gets posted.

How it works:
- Your clips live in `clips/` (public raw URLs that Instagram fetches).
- `schedule.json` says which clip posts when.
- `.github/workflows/post.yml` runs `post_due.py` on a cron and posts what's due.

---

## One-time setup

### 1. Create the repo
- Create a free GitHub account (github.com — no card).
- Create a **new repository**, **Public** (required: Instagram must fetch clips
  without a login, and public repos get unlimited Actions minutes).
- Upload these files into it (keep the folders):
  `post_due.py`, `schedule.json`, `clips/`, and `.github/workflows/post.yml`.

### 2. Add your two secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
| --- | --- |
| `IG_USER_ID` | `17841426757295539` |
| `IG_ACCESS_TOKEN` | your Instagram token (ideally the non-expiring Page token) |

### 3. Enable Actions
Open the **Actions** tab → if prompted, click **"I understand my workflows, enable them."**

---

## Posting a batch (each time you have a video)

1. On your laptop, split the video as usual (the Video Part Maker app) to get
   `..._part_01.mp4`, `..._part_02.mp4`, …
2. Put those clips in this repo's **`clips/`** folder.
3. Edit **`schedule.json`** — one entry per clip, with the time (in UTC, ISO format)
   each should post:

```json
{
  "items": [
    {
      "file": "myvideo_part_01.mp4",
      "post_at": "2026-06-14T09:00:00+00:00",
      "caption": "My Video — Part 1\n#shorts #reels #fyp"
    },
    {
      "file": "myvideo_part_02.mp4",
      "post_at": "2026-06-14T10:00:00+00:00",
      "caption": "My Video — Part 2\n#shorts #reels #fyp"
    }
  ]
}
```

4. **Commit** the clips + schedule.json. Done — GitHub posts each part at its time,
   with your laptop off. (The workflow fills in `posted`, `permalink`, etc. automatically.)

> Times are **UTC**. India (IST) is UTC+5:30 — so 2:30 PM IST = `09:00:00+00:00`.
> A small helper to generate `schedule.json` from a start time + interval can be added later.

---

## Test it right now (before trusting a full batch)

1. Put one short clip in `clips/` (e.g. `test_part_01.mp4`).
2. Set `schedule.json` to one item with `post_at` a couple of minutes in the past
   (so it's immediately "due") and `file` = your test clip's name.
3. Commit.
4. **Actions** tab → select **"Post due reels"** → **Run workflow** (manual trigger).
5. Watch the run log. It should print `POSTED ... -> https://instagram.com/reel/...`
   and the reel appears on your account.

If the run fails, open the failed step's log — it prints the exact Instagram error.

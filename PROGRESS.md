# Marble Race Bot — Setup Progress Log

Statuses as of 2026-08-26. Update this file whenever a setup step changes —
session/machine switches have already lost unsaved browser work once, this
file is the durable record.

## Done

- [x] Concept locked: top-down maze race, square racers with faces, code-only
      visuals (pymunk physics + PIL render + numpy SFX), inspired by the
      "Square League" genre but NOT copying its assets/branding. Updated
      2026-08-27: this no longer means "no combat mechanic ever" — see
      "Battle mode" below, added as a second mode alongside the unchanged
      race-to-finish mode, at the user's explicit request.
- [x] Project scaffolded at `D:\marble-race-bot` — `race_sim.py`,
      `video_gen.py`, `scheduler.py`, `tournament_gen.py`.
- [x] Racer-vs-racer collision physics tuned for visible marble-like bounce
      (elasticity 0.92, post-bump steering-recovery window, stuck-detection).
- [x] Maze generator mixes open "rooms" with corridors (not uniformly narrow).
- [x] Tournament mode: 16 racers, single-elimination bracket, landscape
      1920x1080, procedurally-drawn bracket-tree screens between rounds.
      Local test render succeeded (`final_tournament.mp4`, ~230s).
- [x] GitHub repo created: https://github.com/galymzhan120202-cyber/marble-race-bot
      (private).
- [x] Telegram bot created by user; token + chat ID verified working (test
      message delivered) and saved as GitHub Actions secrets:
      `MBALL_TELEGRAM_NOTIFY_TOKEN`, `MBALL_TELEGRAM_NOTIFY_CHAT_ID`.
- [x] YouTube channel "Marble Race" created by user (@MMarbleeRace).
- [x] Google Cloud OAuth client "Marble Race Uploader" (Desktop app) created
      inside the shared `youtube-automation-489306` project (same project
      weapon-ball-bot etc. use — reused instead of hitting the GCP
      project-count quota). Downloaded as `D:\marble-race-bot\client_secrets.json`
      (gitignored, never committed).
- [x] Confirmed OAuth consent screen on that shared project is already
      **"In production"** (not Testing) — refresh tokens won't expire after
      7 days.
- [x] YouTube channel "About" description published (English + Russian).
- [x] Local Shorts test render verified working end-to-end
      (`skip_upload=True`).

- [x] Local OAuth login done via a throwaway `_oauth_login.py` helper
      (auth-only, no upload side effect — deleted after success).
      `youtube_token.json` produced and verified via `channels().list(mine=True)`
      — confirmed it's authorized for the correct "Marble Race" channel
      (id `UCEM-WjLR6EmKnCxJNHOhi0w`).
- [x] All 4 GitHub Actions secrets set on the repo:
      `MBALL_TELEGRAM_NOTIFY_TOKEN`, `MBALL_TELEGRAM_NOTIFY_CHAT_ID`,
      `MBALL_CLIENT_SECRETS_JSON`, `MBALL_YOUTUBE_TOKEN_JSON`.

- [x] Code pushed to GitHub: https://github.com/galymzhan120202-cyber/marble-race-bot
      (main branch, initial commit `c18bb9e`, no secrets included).
- [x] Channel branding (banner + avatar) generated via `generate_branding.py`
      (reuses race_sim's own `make_racer_icon`/`MAZE_THEMES`, no external
      assets) and published to the channel via YouTube Studio.
- [x] Channel keywords set in Studio Settings (marble race, maze race,
      satisfying video, physics simulation, who wins, marble run, tournament
      bracket, oddly satisfying, race simulator, shorts). Upload-defaults
      section intentionally left untouched — irrelevant since `video_gen.py`
      sets title/description/tags/privacy explicitly per-video via the API.
- [x] User flagged the racer icon's front "pennant" nub as visually
      unpleasant (muddy/semi-transparent, clashes with body color) — sent to
      the fork agent currently doing the visual-polish pass to fix alongside
      everything else it's already touching.

## Battle mode (added 2026-08-27)

- [x] Second video mode added alongside the maze race, per user request
      after sharing a reference video (`youtube.com/shorts/GcPda6o7TiE`,
      "Square Race!" by `@the_qzone`) that mixes a shrinking "zone" with
      weapon pickups and elimination. The original "race to finish" mode is
      **unchanged** — this is an addition, not a replacement of the locked
      concept below.
- [x] `race_sim.py`: `simulate_battle`/`build_battle_clip`/
      `build_battle_cold_open_clip`. Revised 2026-08-27 after user feedback
      that watched footage didn't match their mental model (source:
      App Store "Square Race: Color Clash" — mechanic only, not
      assets/design): the finish line from race mode is kept (same
      `MazeGeometry(has_finish=True)`/finish sensor/dist_field), and three
      **kinematic pymunk walls** (top/left/right, bottom stays open onto
      the finish) physically sweep inward over the match — a racer can't
      cross one and gets carried/squeezed by it, no separate damage-tick.
      Weapon pickups (star icon) let an armed racer **throw** an unarmed
      one on collision (`BATTLE_KNOCKBACK_IMPULSE` impulse, not HP loss);
      slamming into any wall within `BATTLE_FLYING_SECONDS` of being thrown
      is what actually eliminates a racer (`BATTLE_WALL_KILL_IMPULSE`
      threshold). First to the finish wins outright; otherwise last-alive,
      or closest-to-finish on a time-out. Reuses the maze generator/theme/
      racer-icon/physics system from race mode throughout.
- [x] New `battle_gen.py` (mirrors `tournament_gen.py`'s structure) —
      own title/description/tag templates, own thumbnail caption
      ("LAST ONE STANDING?" / red banner via `generate_thumbnail`'s new
      `caption`/`banner_color`/`badge_text` params), own `battle_debug.log`.
- [x] `scheduler.py`: the middle daily `POST_TIMES` slot now generates a
      Battle Royale video instead of a maze race (`BATTLE_SLOT` env var,
      default = slot 2) — total daily Shorts volume unchanged.
- [x] `.github/workflows/battle.yml` added (cron `15 11 * * *`, i.e. the
      16:15 KZ slot removed from `upload.yml`) — same total of 3 daily
      Shorts across the two workflows.

## Still to do

- [ ] Do a real (confirmed, explicit) first upload test — either manually
      via `python video_gen.py` or via GitHub Actions `workflow_dispatch` —
      only after the user explicitly OKs a real public video going live on
      the new channel.
- [ ] Drop 2-3 royalty-free fallback music tracks + `fallback_attribution.json`
      into `music/` (currently empty; Openverse fetch is the primary source,
      this is just the safety fallback — see `SETUP.md`).
- [ ] Confirm the 4-day tournament cron (`.github/workflows/tournament.yml`)
      day-of-month approximation is acceptable, or swap in an exact
      "days-since-last-run" check if the user wants precision.
- [ ] Decide on a final distinct App Store brand name before any future game
      port — "Marble Race" is a placeholder/working title only (channel name
      doesn't need to match the eventual app name).

## Key facts to remember

- Shared GCP project for all bots' OAuth clients: `youtube-automation-489306`
  (project name "YouTube-Automation"). Each bot gets its own OAuth Client ID
  (Desktop app) inside it, not its own project — the account had hit its GCP
  project-count quota.
- `client_secrets.json` in this repo is real and intentional (I placed it
  there during live OAuth setup) — not a mystery/leak, already gitignored.
- GitHub repo owner/account: `galymzhan120202-cyber`.
- Video format: Shorts = vertical 1080x1920, posted multiple times/day via
  `POST_TIMES` in `scheduler.py`. Tournament = horizontal 1920x1080, posted
  every 4 days, separate schedule/workflow, NOT tagged as a Short.

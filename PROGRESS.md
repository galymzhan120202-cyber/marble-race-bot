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
- [x] Fixed a real bug post-launch: racers could visibly sit inside the
      red danger tint instead of being cleanly excluded — the closing
      kinematic wall does push them, but a racer's own steering force
      (still aiming at a pickup/enemy on the wrong side) could fight that
      push for a while first. Fix: in the physics step loop, a racer whose
      position is already outside the current safe funnel gets its target
      force-overridden to a direct escape point (with a stronger steer
      gain) instead of whatever the AI was aiming at, until it's back
      inside. Render-side, the tint's punched "safe hole" also grew by
      half the wall's thickness so a racer resting against the wall's
      near face renders cleanly inside the untinted area.

## Marble Drop mode (added 2026-08-27)

- [x] Third video mode, architecturally unlike race/battle: **no maze, no
      steering AI at all**. Per a detailed Unity/Pygame-style spec the user
      provided (gravity + collisions only, dynamic leader-follow camera,
      finish trigger at the bottom) — adapted to this project's actual
      stack (pymunk physics + PIL/moviepy offline video render, not
      pygame/live display). Squares spawn at the top of a long vertical
      track under real gravity and fall through a staggered Plinko peg
      field plus two spinning kinematic blades; first to cross the finish
      line wins.
- [x] `race_sim.py`: `simulate_drop`/`build_drop_clip`. "Vibrant & Cartoon"
      art style per user follow-up: fixed sky-blue background
      (`DROP_SKY_BLUE`), candy-colored racers (`DROP_CANDY_COLORS`,
      overriding `RACER_POOL`'s house colors for this mode only — name/
      weight/confusion still come from the pool), bright orange/white/
      purple pegs+blades (`DROP_OBSTACLE_COLORS`), high elasticity
      (0.8-0.88) everywhere for playful bounciness.
      Fixed one real bug post-launch: racer size was originally derived
      from `n_racers` alone (same formula as race mode's cell sizing),
      which made racers *wider than the gaps between pegs* at low racer
      counts — permanently wedged, nobody ever finished. Fixed by sizing
      `racer_radius` as a fixed fraction of track width and sizing peg
      spacing in racer-radius units with a guaranteed-safe gap margin.
- [x] New `drop_gen.py` (mirrors `battle_gen.py`'s structure).
- [x] `scheduler.py`/`.github/workflows/drop.yml`: own daily slot
      (`DROP_POST_TIME`, default 14:15 UTC / 19:15 KZ), independent of the
      Shorts/Battle rotation and the Tournament's 4-day cadence — same
      pattern as Tournament's own `schedule.every(...)` job.

## Race/Battle physics audit (2026-08-27)

User asked for a systematic self-audit of race/battle simulation logic
rather than one-off spot fixes. Ran batch diagnostics (40-60 seeds each)
checking for: NaN/non-finite positions, races where nobody finishes,
battles where nobody finishes/gets eliminated/all-alive-at-timeout. Found
and fixed three real bugs, in the order the batch runs surfaced them:

- [x] **Race mode deadlock** (was 1/40 seeds, now 0/60): two racers
      head-to-head in a 1-wide corridor could deadlock for the *entire*
      race — their mutual elastic bounce/jitter displaces them a few
      pixels each way every 0.5s sample, which was enough to clear the
      existing raw-displacement stuck-check's threshold even though
      neither was making any real progress. Fix: a second, longer-window
      check (`PROGRESS_CHECK_STEPS`/`PROGRESS_STALL_LIMIT`) that compares
      real flood-fill distance-to-finish instead of raw position, and
      corrects with a forward+sideways impulse (not just forward, since
      forward-only is what caused the head-on deadlock to begin with).
      Added to both `simulate_race` and `simulate_battle`.
- [x] **Battle mode zone-escape targeting a wall** (contributed to ~28%
      of battles ending in "nothing happened" — no finish, no
      elimination, everyone still alive at timeout): the zone-escape fix
      from the previous session (see "Battle mode" section above) aimed a
      racer at a raw XY point when outside the safe funnel, with **no
      awareness of maze wall connectivity** — if a wall stood between the
      racer and that point, steering just pinned it against the wall
      instead of leading it out, for up to 15+ seconds at a time. Fix:
      the escape case now reuses the exact same maze-graph
      (`open_neighbors` + `dist_field`) best-next-cell logic as the normal
      finish-seeking fallback, guaranteeing a reachable target.
- [x] **Battle mode zone could permanently seal off the finish** (the
      real root cause behind the remaining stuck cases — confirmed via
      15+ second motionless stretches that neither fix above could clear,
      because there was genuinely no path): the zone was a generic
      shrinking *rectangle* with no idea where the maze's corridors
      actually run. Once the left/right walls narrowed past whatever
      column the maze's one true route to the finish happened to pass
      through, any racer still on the wrong side was walled off
      *permanently*. Fix: left/right no longer narrow at all — only the
      **top** wall closes in. This is provably safe instead of just
      empirically better: the finish sits at the maze's max-y row, so
      BFS distance-to-finish strictly decreases with y regardless of
      column, and a top-only wall only ever excludes the region *above*
      itself, never the only route to something further down.
      Down from ~28% "nothing happened" to ~13%, and the remaining cases
      are legitimate close-finish congestion in the last few seconds
      (racers still visibly progressing throughout, just don't quite
      make it before the time cap) rather than dead/frozen simulations.

## Second audit pass: presentation contradiction bug (2026-08-27)

Re-ran the batch audit at larger scale (700 race sims across all 7
`n_racers` values 2-8, 100 seeds each) after the first pass. Found the
remaining ~2.3% of "no finish" cases are **not** stuck/frozen simulations
— positions keep changing right up to the time cap (a longer maze for
more racers can occasionally just need more than `max_seconds`). That's
fine on its own, but rendering it exposed a real, viewer-visible bug:

- [x] **Win banner contradicted the HUD counter**: when nobody actually
      crosses the finish, `winner_idx`/`winner_name` still get set (via
      the existing furthest-progress fallback), but the video kept using
      the normal `WIN_TEXT_TEMPLATES` ("{name} CROSSES FIRST!") regardless
      — so a video could show "FINISHED: 0/6" in the HUD at the exact
      same moment a banner declares that racer the winner "crossing
      first." Same bug existed in Drop mode's finish-line fallback too.
      Fix: `simulate_race`/`simulate_drop`/`simulate_battle` all now
      return a `winner_finished` flag; `build_race_clip`/`build_drop_clip`
      use it to pick `TIMEOUT_WIN_TEXT_TEMPLATES` ("TIME'S UP! {name}
      LEADS!") instead of the crossing-line phrasing when nobody actually
      finished. (Battle mode already had this distinction from the
      previous session's `winner_finished`/`BATTLE_WIN_TEXT_TEMPLATES`
      split.)
- [x] Also added `_fit_text_font` (shrinks the win-banner font until the
      formatted text fits within the frame width) after noticing the
      longer timeout templates could otherwise render wider than the
      video and clip off both edges — a latent risk for long racer names
      + the existing templates too, not just the new ones.

## Physics/collision fidelity pass vs reference (2026-08-27)

User asked to "truly copy" Square Race: Color Clash's physics/collision
behavior (not just visual style), specifically calling out collisions.
Investigated further via YouTube thumbnail frames of a related "Square
League" video — turned out to be a different, messier format (100+ tiny
pieces, tournament roster tables) not close to our clean few-racer
style, so not useful as a literal template. Fell back to the earlier,
already-verified App Store description: races are decided by "physics,
inertia, and sharp corner collisions" with racers "spinning wildly."

- [x] **Race mode racers now collide as squares, not circles**, and
      render using **real physics rotation** (`body.angle`) instead of a
      synthetic velocity-heading snap. A circle's collision normal always
      passes through its own center, so it generates ~zero spin on
      impact — physically correct for smooth circles, but is why racers
      never visibly tumbled before. `RACER_SIDE` is sized so the square's
      corner-to-center reach exactly equals the old circle's radius
      (same worst-case corridor clearance as the already-battle-tested
      circle — confirmed via the full batch harness: 700 sims across all
      `n_racers` 2-8, 0 regressions, same 2.3% "ran out of time" rate as
      before). Small poly corner-rounding (8% of side) keeps it from
      being razor-sharp.
- [x] **Battle mode intentionally kept its circle collision body** — tried
      the identical square-body change there too, but it made things
      measurably worse (batch "nothing happened" rate: 13% baseline ->
      16-23% across several corner-rounding values tried, never
      recovering). Root cause: square bodies wedge corner-to-corner in
      multi-racer pileups far more than circles do, and battle mode
      already has more pileup pressure than race mode (the closing zone
      funnels racers together, and knockback throws send them careening
      into chokepoints). Reverted battle mode's racers to circles +
      velocity-heading rendering, its already-proven-stable config from
      the earlier bug-hunting pass. Drop mode already used real square
      bodies/physics rotation from the start and was unaffected.

## Maze structure: open-board layout to match the reference (2026-08-27)

User asked to rebuild the maze specifically according to the reference
game's logic. The reference reads as one big mostly-open board — racers
clash/collide/bounce across open floor with sparse obstacles — not a
tightly-branching 1-wide-corridor labyrinth, which is what most of our 10
`MAZE_STRUCTURE_KINDS` produce.

- [x] `pick_maze_structure` now weights selection (`MAZE_STRUCTURE_WEIGHTS`)
      so the open/wide kinds (`open_rooms`, `classic`, `scatter_pillars`,
      `terraces` — 80% combined) dominate, while the tighter/artsier kinds
      (`spiral`, `radial`, `double_helix`, `symmetric`, `sparse_labyrinth`,
      `spine_branches` — 20% combined) still show up occasionally for
      variety instead of every board looking identical.
- [x] `open_rooms` itself widened further (loop probability 0.55->0.72,
      bigger/denser rooms) now that it's the primary structure instead of
      one of ten equally-likely options.
- [x] Nice side effect, confirmed via the batch harness: wider corridors
      are far less prone to multi-racer chokepoint deadlocks than a true
      labyrinth. Race mode's "ran out of time" rate dropped further,
      2.3% -> 0.7% (700 sims, all n_racers 2-8). Battle mode unaffected
      (13.3%, same as its established baseline).

## Race mode: fixing racers colliding and stalling in one spot (2026-09-02)

User reported racers visibly colliding and getting stuck jostling in one
spot in both Race and Battle mode, and asked for a systematic audit rather
than a one-off fix, plus specifically asked to look at real collision-physics
tuning (elasticity/friction/bounce), not just more stall-detection patches.

- [x] **Confirmed the regression, quantified with a new metric.** The
      existing batch-audit checks (raw per-frame displacement, non-finite
      positions, "ran out of time") all read ~0% on current `main` — they
      genuinely don't catch this failure mode, because a jammed pair of
      racers keeps jittering a few pixels every frame from the elastic
      bounce, which clears the old displacement threshold even with zero
      real progress. Added a same-maze-cell-dwell check instead (how long a
      racer stays in the exact same grid cell) and found Race mode
      genuinely regressed: **15.0% of races** (40 seeds x 7 `n_racers`,
      matched sample) had at least one racer stuck in the same cell for
      3+ seconds, up to ~9s in the worst cases — never caught because
      nobody re-ran the batch harness after `b911037` (square collision
      bodies) landed immediately followed by `dd04184` (open-board maze
      weighting, which packs more racers into open rooms = more
      simultaneous pileups). This is the same corner-wedging failure mode
      already proven to hurt Battle mode when square bodies were tried
      there, now reproduced in Race mode by the combination of both
      changes together.
- [x] **Tried real collision-physics tuning first, per the user's request
      — batch-tested it, and it made things WORSE, not better:**
      - Rounding the racer squares' corners further (0.08 -> 0.18 of side,
        theory: bigger/cleaner contact normal = a more "ball-like" bounce)
        pushed the dwell rate UP to ~22%. Root cause: a corner-vs-corner
        hit's actual escape mechanism is the *torque* it imparts, which
        shunts a racer sideways at an angle past whatever it's jammed
        against — rounding the corners suppresses exactly that torque, so
        hits land closer to head-on and racers just bounce straight back
        into the same jam instead of glancing off it. Reverted.
      - Forcing lower racer-vs-racer friction (0.35 -> 0.08, theory: real
        marbles don't "grab" each other tangentially) made no measurable
        improvement in isolation and stacked with the corner-rounding
        change made things worse. Reverted.
      - More pymunk solver iterations (10 -> 20, theory: a dense pileup's
        contacts are under-resolved by the default iteration count) also
        made things slightly worse in isolation (13.7% -> 16.6%), not
        better. Reverted.
      - Conclusion: the collision *material* physics (elasticity/friction/
        corner shape) were not the actual bug — `RACER_VS_RACER_ELASTICITY
        = 0.92` was already producing a strong, correct bounce on contact.
        The bug is that the *continuous steering force* reasserts itself
        every single 1/120s physics step regardless of what the collision
        just did, so on a soft/repeated contact (below the 15.0 impulse
        threshold that opens the post-bump recovery window) the bounce
        gets steered right back into the same jam before it can ever
        separate the racers.
- [x] **Real fix: a short-range separation force, gated on closing speed**
      (new `simulate_race` block, module constants `REPEL_RADIUS_CELLS`/
      `_REPEL_STRENGTH` near `RACER_TYPE_BASE`). Every racer's steering
      target comes purely from the maze graph with zero awareness of where
      other racers currently are, so several racers converging on the same
      doorway all aim at the literal same point and pile on top of each
      other — this adds a small extra repulsion force between any two
      racers within `REPEL_RADIUS_CELLS` (1.6 cells) of each other, so they
      start nudging apart before/while jammed instead of relying solely on
      the post-collision recovery window to pull them apart after the fact.
      Critically, it's **gated on relative closing speed**: a fast, real
      bump (two racers actively approaching each other) is left completely
      alone so the elastic collision itself produces the visible bounce/
      spin — the repulsion only engages when a nearby pair's relative speed
      along the line between them is near zero or negative, i.e. they're
      genuinely idling against each other, which is what an actual wedge
      looks like as opposed to a passing hit. An earlier ungated version of
      this cut the dwell rate hard (15% -> ~2%) but also suppressed ~95% of
      the visible racer-vs-racer bump/spin events (125.6 -> 6.5 avg
      bump-flagged frames/race, 6-racer sample) — it was shoving racers
      apart before they ever visibly touched, defeating the point of the
      square-body physics change. The closing-speed gate keeps the tradeoff
      reasonable: at the shipped tuning (radius 1.6 cells, strength 1200),
      avg racer-vs-racer bump-flagged frames per race is 21.5 (vs. 120.8
      baseline, 6-racer sample) — a real drop from what was mostly
      repeated stutter-collisions off a jam rather than distinct bumps, not
      a race with no visible contact.
- [x] **Result, 350-sim confirmatory batch (50 seeds x 7 `n_racers`,
      2-8):** same-cell dwell 3+s: 15.0% -> **3.7%**. Non-finite positions:
      0% (unchanged). "Ran out of time" (timeout): 0% (down from 0.4%
      pre-fix at matched sample size). No errors.
- [x] **Battle mode: audited, found NOT regressed, left untouched.** Same
      same-cell-dwell check on Battle mode reads high (52.4% of battles
      have a racer dwelling 3+s in one cell, up to 17s+ in the worst
      cases) — but Battle's own "nothing happened" metric (no finish, no
      elimination, everyone still alive at timeout — the actual bug
      signal from the original 2026-08-27 audit) measured 14.8% on 210
      sims, statistically indistinguishable from the already-investigated
      and accepted ~13.3% baseline. The high dwell number is explained by
      Battle's fundamentally different objective: unlike Race (where two
      racers meeting is always friction to minimize), Battle's core
      mechanic is chasing pickups/enemies and fighting within a small
      area, which legitimately keeps a racer in the same maze cell for
      many seconds without that being stuck/broken — confirmed via the
      same confined-jitter check used for Race, which read 0% for Battle
      too (no racer was ever pixel-frozen, just moving around within one
      cell region, consistent with active combat rather than a wedge).
      Applying Race's separation-force fix to Battle would work against
      its intended design (racers need to be able to reach each other to
      fight/pick up items) and risks repeating the exact regression the
      2026-08-27 audit already found when square-body physics were tried
      in Battle — so it was deliberately left alone rather than
      "fixed" without evidence of an actual bug.

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

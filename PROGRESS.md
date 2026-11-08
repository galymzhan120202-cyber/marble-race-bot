# Marble Race Bot — Setup Progress Log

Latest update: 2026-11-08. Update this file whenever a setup step changes —
session/machine switches have already lost unsaved browser work once, this
file is the durable record.

## YouTube motion and arena rollout (2026-11-08)

- Ported the browser's reactive motion to the Python video generators.
  `video_motion.py` records physical contact normals and impulses, then renders
  a damped squash/rebound, speed-dependent ribbons and directional sparks.
  Contact history, trail samples and particles are bounded; static arena art
  and portraits are cached, and offscreen effects are culled.
- Race, Battle, Drop and tournament heats share deterministic presentation
  timelines. MoviePy can request frames out of order without changing pixels
  or simulation state. The camera eases up to 1.12x around current action and
  the deciding finish; HUD/event text remains crisp and visibility indicators
  use the actual camera crop. Camera planning does not inspect future results.
- Sixteen character victory profiles run for 3.2 seconds in result cards,
  qualifier tiles and the tournament champion outro. Audio follows the full
  clip duration. Recorded Shorts retain the configured 60 FPS.
- Added Aurora Loops and Pulse Grid to the Python maze rotation, and Diamond
  Drift and Pinwheel Pass to Drop. Python now has 12 maze layouts and 8 Drop
  layouts. New maze palettes and arena titles distinguish the courses.
  Maze/Battle accept `arena_kind` as well as seed for explicit replays;
  automatic arena selection includes the new layouts.
- Validation: 865 Python tests and 32 Node tests passed. All new arenas have
  connectivity/collision-clearance, real-finish and cross-FPS checks. An exact
  comparison of 52 original seeded Race/Battle/Drop runs preserved every
  physics frame, bump, finish and final ranking with the arena held fixed.
  Boundary regressions pin their historical arena instead of depending on
  a changing automatic arena list.
- Offline 60 FPS previews for all four new arenas are in
  `.audit-work/youtube-motion/`; validation logs and frame sheets are retained
  there. A fifth Battle preview also passed, and the actual four video
  pipelines encoded/decoded with audio and matching durations, including a
  74.95-second abbreviated tournament. The final 1080p camera path uses an
  opaque RGB resize instead of an RGBA affine transform; a local 30-frame
  sample averaged 105ms per frame (about 190s of rendering for a 30s/60FPS
  video, excluding encoding). This is a local measurement, not a runner SLA.
  Publishing and messaging are disabled in pipeline QA. The scheduled
  GitHub workflows load the updated default branch on their next run;
  already published YouTube videos remain unchanged.
- The first Linux release check exposed a marginal Pinwheel Pass seed:
  two racers finished at 21.92s on Windows but exceeded 22s on Linux. Its
  five rotors now turn at 72% of the original rate to reduce repeated upward
  launches. The other arenas retain their exact original rotor speeds. The
  existing finish regression remains strict; 503 affected Windows checks
  passed after the change, with Linux release validation repeated separately.

## Reactive animation and four new arenas (2026-11-08)

- Collision contacts now record their normal and speed. Racers squash along
  that normal, rebound with a damped spring and settle; repeated resting
  contacts cannot restart the motion indefinitely. Fast racers leave tapered
  ribbons and speed streaks. Contact strength controls directional sparks,
  with bounded history and a per-frame particle budget.
- The render-only camera eases into a crop of at most 12% for lead changes,
  close races, strong hits and the finish. It keeps the selected camera target
  visible and clamps to the real course. Reduced motion restores a fixed view.
- Each of the 16 characters has a victory motion profile: floating, hopping,
  tumbling, wobbling, bowing or character-specific gestures. Shared champions
  animate independently within their tiles. Gestures settle after 3.2 seconds,
  suspend for help/hidden tabs, and stop on navigation or reduced motion.
  The result composition was informed by the inspected
  [Duolingo match-complete screen](https://mobbin.com/screens/cdc6c47f-f54a-4ac8-838f-cd25e99b2988).
  The existing project art is used; these gestures are implemented in Canvas.
- Mobile rendering caps high-DPI backing buffers, adapts decorative quality
  to sustained frame workload, culls offscreen content, caches the radar
  background and throttles radar redraws. Standings cancel/measure/animate
  rows in batches to avoid one forced layout per row. Resize work is coalesced.
- Added four browser arenas, bringing the total to six Maze and eight Drop:
  Aurora Loops has connected loop chambers with alternating exits; Pulse Grid
  has parallel lanes and staggered crossovers; Diamond Drift has weaving peg
  corridors; Pinwheel Pass has five rotors alternating across the track.
  New cards have a NEW marker. Cup selection, settings, replay and share
  links all include these layouts. Existing race-link version 2 remains valid.
- Validation: 32 Node tests passed, including all-layout connectivity,
  collision clearance, real finishes, varied-roster podiums, camera framing,
  bounded effects, 16 distinct gestures that stay inside their tiles, and adaptive quality.
  An exact comparison of 30 seeded podiums on the original ten arenas
  retained every terminal position, velocity, rotation and finish step.
  Browser checks passed at 1440x1000, 390x844, 360x640 and 844x390 with no
  page errors. Each size also selects all four new arenas and checks exact
  replay/share outcomes, persistence and accessible result controls.
- A 390x844 Chromium/Edge sample at DPR 3 and 4x CPU throttling recorded 120
  full-motion frames: median interval 16.7ms, p95 interval 33.4ms, median JS
  frame work 7.4ms and p95 work 21.6ms, with a 373,800-pixel render buffer.
  These are local emulation measurements, not a native-device FPS guarantee.
  Evidence: `.audit-work/ui-v2/motion-performance.json`, screenshots in that
  directory, `.audit-work/arena-node-results.txt` and `arena-browser-results.txt`.
  The subsequent YouTube rollout above ports this motion and these arenas
  to Python; this section records the browser implementation and its QA.

## Mobbin-led browser design and motion (2026-11-08)

- Reviewed the static browser UI, fixed-step canvas engines, shared racer
  assets, Cup/replay/history persistence, Python video pipeline and test
  workflow. The browser and Python/Pymunk simulations remain separate.
  Main UI gaps were a static lobby illustration, weak visual hierarchy,
  limited track context and no user-controlled motion preference.
- Rebuilt the lobby with a locally hosted Anton headline, slate/lime/lavender
  palette, an actual independent race preview, illustrated Maze/Drop/Cup
  entry cards, the saved pick and race statistics. Refined setup, live
  standings, result views, responsive typography and touch targets.
- Added fixed-step render interpolation for racers, camera and spinners;
  tapered trails, collision rings/sparks, selected-racer highlighting,
  animated countdown and two-axis standings transitions. Final results
  receive a finite, one-time confetti animation. Drawing no longer prunes
  simulation effects: their lifetime is bounded by physics steps, including
  headless runs. The presentation never consumes race RNG or changes scores.
- Added a full-course radar and desktop track expansion. The lobby preview
  pauses when hidden, scrolled away, manually paused, help is open or the
  player leaves the lobby. It cannot add results. Reduced motion follows
  the OS until explicitly changed; that choice persists across reloads.
- Added `npm run dev` at `http://127.0.0.1:4173`. The local server exposes
  only `index.html`, `web/`, `assets/` and `fonts/`; browser tests reuse it.
  Static deployments now need the existing `fonts/` directory as well.
- Validation: 24 Node tests and 703 Python tests passed. Browser scenarios
  passed at 1440x1000, 390x844, 360x640 and 844x390 without page errors or
  horizontal overflow, including 44px touch targets, Cup podiums, replay,
  sharing, history, timeout handling, cross-tab progress and failure recovery.
  Full-motion checks also cover preview lifecycle, system/user preferences,
  focus resizing, radar and celebration cleanup. Rendering/motion cadence
  regressions verify unchanged seeded podiums and side-effect-free draws.
  Visual evidence is in `.audit-work/ui-v2/`; test logs are in `.audit-work/`.
- Scope: browser UI and animation changes are implemented. Python video
  animations were not redesigned in this pass; their existing tests passed.
  Browser QA used Chromium/Edge; Safari/Firefox and physical devices have
  not been exercised. No publication or remote deployment was performed.

Design references inspected through the connected Mobbin tool:
[Duolingo match lobby](https://mobbin.com/screens/8a6c7562-5295-49e4-b54f-1868c6bb61fc)
for mascot emphasis and a clear primary action,
[Base44 game menu](https://mobbin.com/screens/269556ae-3bd5-4a9e-b963-e2d90dad1162)
for a compact play/settings hierarchy, and
[Shopify Editions hero](https://mobbin.com/sites/sections/47c5f830-b25e-4912-8484-47377cd8a238)
for bold racing typography. The game's own art and engine provide the
implementation. Game references: [Marble It Up!](https://marbleitup.com/)
and [Marbles on Stream / Pixel by Pixel](https://www.pixelbypixelstudios.live/).

## Follow-up bug audit (2026-10-18)

- Shared links and history replays now adopt the opened race's mode, arena,
  selected racer and field size. New race keeps that setup. Navigation clears
  the consumed launch URL, while starting another race updates its URL.
- Clipboard results are scoped to the race that requested them. A delayed
  permission response cannot show an old link or steal the next screen's focus.
- Saving settings reads current stored progress before writing, preventing an
  older tab from erasing a newer tab's results. Storage events refresh counters
  and history; failed writes retain pending results for a later retry.
- Fast Drop racers could outrun the camera in short viewports for 0.74 seconds.
  Camera smoothing now keeps its target visible without changing the physics
  or existing race-link version. All 90 camera audit cases keep the target in
  frame; 600 additional Maze cases cover all three sizes and edge seeds.
- Python simulations now stop and capture the decisive physics step instead
  of waiting for a video-frame boundary. This prevents FPS-dependent extra
  finishes and terminal movement. Nonfinite durations and durations shorter
  than one physics step are rejected before producing an empty recording.
- Validation: 703 Python tests and 23 Node tests passed. All four video modes
  encoded and decoded offline with finite, audible, unclipped audio. New
  regressions cover FPS-independent terminal states, camera visibility,
  cross-tab progress, share/navigation lifecycle and failed storage retries.
  Browser scenarios passed at 1440x1000, 390x844, 360x640 and 844x390 with no
  page errors, including the new lifecycle and transient-storage cases.

## Cup play, race links and finish accuracy (2026-10-18)

- Added Quick play, a three-round Cup across distinct arenas, recent-result
  replays and validated versioned race links. Cup rosters remain the same
  while starting slots rotate. Only actual finishers score 5/3/1; unfinished
  racers score zero and equal totals share the Cup. Replay cannot rescore a
  round. Shared links reproduce the heat inputs without a server.
- Added playback speed controls that retain fixed 120Hz simulation steps,
  course progress, leader/finish events, collision cues and camera framing
  that adapts to short or wide screens. Offscreen selected racers receive
  an edge indicator. Finished standings now say FINAL and explain that
  nonfinishers are ordered by their progress at the stop.
- Timeout leaders no longer count as wins. Recent successful results and
  counted race keys persist locally, with bounded history and validated
  inputs. Results and history use the winner's actual crossing time; tied
  Cup champions each appear in the result portrait. Muting or pausing
  cancels scheduled tones.
- Corrected same-step finish ordering in JavaScript and Python. Winners
  and podiums use the interpolated crossing time rather than roster order
  or Pymunk callback order. Browser seed multiplication now preserves exact
  unsigned 32-bit arithmetic for high random seeds.
- Python Drop starts accommodate larger explicit rosters without overlap;
  terminal partial-frame captures keep the recorded result visible when a
  time boundary falls between video frames.
- Shared `audio_mix.py` decodes music into an owned buffer and closes the
  FFmpeg source reader before rendering. Looping, ducking and short fades
  operate on that buffer; a decode error leaves the SFX track available.
- Playability sweep: 960 browser runs across ten arenas, varied rosters and
  low/high 32-bit seeds all finished with finite positions. The audit found
  no obstacle-free Drop winner; all requested Cup podiums filled.
- Final validation: 679 Python tests and 19 Node tests passed. Browser
  scenarios passed at 1440x1000, 390x844, 360x640 and 844x390 with no browser
  errors, horizontal overflow or undersized touch buttons. These cover
  real podium scoring, replay/share, finish times, tied portraits, camera
  fallback, saved-stat validation, timeout handling and playback speed.
- Offline Race, Battle, Drop and 48-second Tournament videos encoded and
  decoded successfully with finite, audible, unclipped audio; no publishing
  service was contacted. Final desktop/phone results were visually reviewed.

## Character identities and offline music (2026-10-18)

- Completed the character redesign deferred during the arena update. All
  16 racers now have original object silhouettes and readable expressions:
  banana, boba, matcha, donut, gummy bear, robot, cat, fox, ghost, cloud,
  cherries, jelly UFO, peach, frog, bee and dragon.
- `racer_art.py` is the shared artwork and identity source. The export
  script regenerates all 16 PNGs plus a browser catalog and JSON manifest.
  Existing names remain stable IDs for selections, replay and statistics.
  Setup cards, selected-character details, standings and results now show
  the object identity as well as the racer name.
- Canonical colours also survive random video roster selection; the
  legacy palette pass runs on copies to preserve seeded RNG consumption.
  Channel avatar/banner generators now pass named identities and their
  local image outputs have been regenerated with the new artwork.
- Video sprite rotation expands the temporary image, preserving ears,
  straws, wings and Battle badges at every angle. Regression checks compare
  browser PNGs with canonical Python artwork and check unique silhouettes
  at 32, 64 and 256 pixels.
- Completed the local music backlog with three original, reproducible WAV
  loops and attribution metadata. All four `skip_upload=True` pipelines
  use local music without requesting Openverse. Normal publication still
  tries Openverse and falls back to the bundled library.
- Offline audio validation encoded and decoded Race, Battle, Drop and a
  48-second Tournament; the latter exercises music looping. Audio was
  finite, audible and unclipped. No publishing service was contacted.
- Final validation: all 554 Python tests, eight browser-engine test groups
  and four browser viewport runs passed. Desktop/phone crew selection,
  live races, results, dark/light surfaces and actual 32px portraits were
  visually reviewed. Music tests also cover unexpected download exceptions
  falling back locally. `git diff --check` is clean.

## Game interface and arena update (2026-10-18)

- Rebuilt the browser experience around a home screen, a single race setup
  screen and a live track with standings. The existing character artwork is
  retained for this stage; the user wants character redesign after arenas.
- Extracted the browser engine, interface state and styles to
  `web/game-core.js`, `web/game.js` and `web/game.css`. Deploy those files
  together with `index.html` and `assets/racers/`; there is no build step.
- Added four selectable Maze layouts and two new Drop layouts, Split Cascade
  and Orbit Run. Browser cards render the actual layouts. Python uses the
  same six Drop layout IDs and supports explicit `arena_kind` selection.
- Added pause/resume (including countdown), automatic pause when hidden,
  leader/selected-racer cameras, live positions, optional synthesized
  countdown/result sounds, setup persistence and local race/win counts.
  Restart and replay preserve the seed and roster; each race contributes
  to statistics only once, including an unfinished race that is restarted.
- Updated arena palettes, wall depth, starting-grid markers and finish
  stripes. Python Drop backgrounds are baked once per clip, keeping static
  decoration out of the per-frame rendering path.
- A motion review found near-free-fall winners in sparse Drop layouts:
  retained peg rows aligned vertically and left uninterrupted side routes.
  Staggering retained rows and adding paired gate rows between rotor
  chambers now makes the obstacles part of the race. Outer pegs attach to
  the rails so they deflect inward without creating small trapping pockets.
  Gravity and result timing are unchanged; no minimum-duration hold was added.
  Actual peg/blade contact counters and continuous vertical-path checks
  guard this behavior. The final matched audit (six arenas, seeds 0–20,
  4/6/8 racers) completed all 378 runs per engine with no obstacle-free
  winners or straight vertical bypasses; Python reported no quality failures.
- Made local scheduling explicitly UTC, aligned the Tournament default to
  06:15 UTC, and guarded scheduler startup so inspection/import cannot send
  notifications. The physics audit distinguishes valid Battle last-standing
  wins from timeouts.
- Added portable browser integration checks, a scoped local test server,
  deterministic test seeds and screenshot artifacts. CI now runs the UI
  checks in Chromium alongside Python and browser physics tests.
- Final validation: 509 Python tests and eight Node test groups passed.
  Browser checks passed at 1440x1000, 390x844, 360x640 and 844x390,
  including touch targets, pause, replay, statistics and saved preferences.
  There were no browser page errors or horizontal overflow. Updated arena
  and interface screenshots are in `.audit-work/`; browser results and
  viewport captures are in `.audit-work/ui-v2/`.

## Following racers and tournament qualification (2026-10-07)

- Live tournament HUDs now identify the round and heat, show the remaining
  qualification spots, and mark finishers in their actual arrival order.
  Placement badges are built from events already recorded at that frame;
  simultaneous finishers beyond the qualifying quota are not called qualifiers.
- The camera waits for the required number of finishers before holding the
  finish. A 50-heat audit found two former empty-camera cases: spine_branches
  seed 41 (0.25 s) and scatter_pillars seed 997 (1.5 s). Both are regression
  tests, and the same audit now has no empty live camera frames while a
  qualification spot remains.
- Portrait/landscape roster arrows show whether an active racer is above or
  below the camera. Finished and eliminated racers never get these arrows.
- Shared finish/elimination notices stay inside the play area, avoid nearby
  notices and fade over 0.85 seconds at every output FPS. They are composited
  after racer sprites so sprites cannot cover the notice text.
- Explicit rosters retain their colours in every heat. Previously the
  contrast adjustment could recolour a tournament racer differently from
  its title card, bracket and subsequent heats.
- Validation: 239 Python tests, all 50 tournament camera cases, four offline
  video pipeline encode/decode checks with audio, plus a 960x540 qualification
  clip and full-size visual review of live/qualified/offscreen states.
  No publishing services were contacted by the previews.

## YouTube video logic and interface (2026-10-07)

- Battle now routes toward the nearest safe maze cell with a small allowance
  for the moving storm, rather than always following the finish route.
  NetworkX checks the escape distances independently across all maze styles.
  Safe dead ends no longer immediately send racers back into danger.
- The broader arena audit caught two crowded Battle regressions (radial 41
  and terraces 103). Repeated collision hesitation was suppressing the
  movement watchdog's escape steering. Active recovery now keeps steering
  authority; both cases have regression tests.
- Video HUDs show race rules, named character portraits, current participant
  states and elapsed time. Battle adds storm countdown, exposed-racer count
  and individual exposure timers in the roster. Rings on the arena replace
  overlapping warning text. Eliminations explain storm versus impact.
  Tournament heats explicitly show that the top two advance.
- Battle cameras follow a visible group instead of the empty space between
  distant packs, and reframe if the followed group is eliminated. Finish
  framing remains locked after the winning body disappears.
- All four video metadata builders keep the result out of descriptions and
  tags. Battle descriptions explain both valid win conditions. Tests verify
  that changing the eventual winner cannot change the public metadata or
  the live HUD. Small labels now shrink to fit; fonts and roster portraits
  are cached to avoid rebuilding them every frame.
- Validation: 227 Python tests; 290 forced-arena simulations and another 280
  Battle runs covering seeds 0-39 with 2-8 racers. No confined 3-second stalls,
  invalid rankings or invalid coordinates in these runs. Portrait/landscape
  frames were visually reviewed and all four video pipelines encoded and
  decoded offline with audio. No YouTube upload or Telegram message was sent.

## Arena audit, character identity and viewing pace (2026-10-07)

- Forced all ten maze styles and four Drop styles through 290 new races,
  battles, drops and landscape tournament heats (seeds 41, 57, 103, 211,
  997). Found one connected but impractically long sparse tournament maze:
  seed 103 required 136-151 cell crossings from the original starting grid
  and timed out at 55 seconds without a finisher. Arena preparation now
  opens real shortcuts to bound starting routes; rendering, collision walls
  and navigation all use the same repaired grid.
- Starting positions are selected from a band of similar route lengths and
  assigned by a seeded draw, rather than reserving lanes by roster index.
  Applied to Python Race/Battle and browser Race. Regression checks confirm
  that the starting-distance spread does not increase.
- Added NetworkX 3.4.2 as a test-only dependency to independently verify
  shortest paths. Pymunk queries verify body clearance, wall openings, finish
  access and weapon pickup placement across portrait and landscape arenas.
- Original Pillow-drawn portraits give all 16 racers distinct faces and
  emblems, including readable eyes on dark bodies. Browser PNGs are generated
  from the same source with `python scripts/build_racer_assets.py`. Drop keeps
  signature character colours. Portraits remain distinct with colour removed.
- Moving 0.8-second previews show early action without selecting the winner;
  no opening white flash or black fade. Countdown reduced from 2.0 to 0.9
  seconds, with audio/frame timing aligned. Race and Drop stop once the result
  is settled. Tournament cards are shorter and show both advancing racers.
  The tournament thumbnail shows entrants, and its opening previews the first
  heat rather than revealing finalists. Winner-specific question titles removed.
- A pre-render publication gate rejects timeouts, incomplete rankings,
  non-finite coordinates, insufficient qualifiers and confined 3-second
  stalls. Up to eight simulations are tried; failure stops before rendering
  or upload. Duplicate matchups are still avoided. Offline preview mode can
  render deliberately short simulations without passing the publication gate.
- Validation: 194 Python tests, 290 forced-arena simulations (no stalls,
  invalid positions, incomplete rankings or timeouts after the fixes), 168
  seeded browser races/drops, responsive browser navigation and all four
  audio/video encode-decode previews. No YouTube uploads or Telegram messages
  were sent. These are content/pacing improvements; retention impact still
  needs to be measured against real YouTube Analytics.

References reviewed: [Pymunk collision/query examples](https://www.pymunk.org/en/latest/examples.html),
[NetworkX shortest paths](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.generic.shortest_path.html),
[Matter.js examples](https://github.com/liabru/matter-js/tree/master/examples),
and [YouTube audience retention](https://support.google.com/youtube/answer/9314415).
The existing Pymunk engine was retained; no external game artwork was copied.

## Physics, storm, arenas and presentation fixes (2026-10-07)

The user confirmed the YouTube bot is already running and uploading, and
requested fixes for racers stopping, storm entrapment, game logic and arena
design, followed by a commit and push.

- Navigation now checks body clearance before cutting a maze corner.
  Racer separation forces no longer act through intervening walls. A
  movement-envelope watchdog detects confined bouncing and yields into a
  real neighbouring passage using impulses, without teleporting racers.
- Battle pickups and opponents use cached maze-distance fields instead of
  greedy straight-line distance. Racers pursue a pickup inside their own
  cell rather than immediately walking away from it.
- **Storm mechanic updated:** removed the solid moving zone colliders.
  Racers can cross back into safety; 2.5 seconds of continuous exposure
  still eliminates them. Escape targeting starts as the boundary approaches.
  The video shows the exact danger boundary and each exposed racer's timer.
  This supersedes the earlier solid-wall design described below.
- Battle resolves as soon as a racer finishes or one survivor remains.
  The last survivor cannot be eliminated while waiting for minimum video
  duration. Rankings include every finisher, survivor and eliminated racer.
  Race/Drop also stop when nobody remains active instead of filming an empty
  board. Finished bodies are removed on physics steps, independently of FPS.
- Odd-width symmetric mazes now connect both halves through a middle spine
  (important for 11-column tournament heats). All 10 arena kinds are checked
  for reachability at even/odd widths. Finish sensors match the visible
  checker stripe. Drop pegs leave clearance around the full blade sweep;
  blade rendering now matches collider thickness.
- Shared readable video HUD/result cards, fixed HUD occlusion by racers,
  corrected Race sprite rotation, stable finish camera, synchronized countdown
  audio, and a frozen storm during the result hold. Timeout results are
  labelled accurately both on screen and in upload descriptions. Tournament
  cards have a dark background, named entrants and accurate round labels.
- Browser Race shares wall-aware navigation and confinement recovery. Drop
  uses per-second damping and rotating-blade contact velocity. Countdown and
  delayed-winner callbacks are cancelled on navigation; resize redraws frozen
  scenes; the support link no longer covers game controls. Improved mobile
  layout, keyboard selection and consistent finish-line graphics.
- Upload retries now remain within the same resumable upload request in all
  four modes. CLI errors exit nonzero. Preview mode skips YouTube history and
  error notifications; rendering tests stub music and all publishing helpers.
- Validation: **840 simulations** (40 seeds x every racer count 2–8 x three
  modes), with zero non-finite positions, incomplete rankings, confined 3s
  stalls or no-event timeouts. The original matched 100-run Battle sample
  had 45 confined-stall cases and 19 incomplete rankings. A separate final
  240-run Battle audit and a storm-escape regression also passed.
- Encoded and decoded small local previews of all four video modes with
  audio. Checked actual landscape tournament heats, storm/portrait/landscape
  frames, and browser navigation at 390x844, 360x640 and 1440x900. Added Python
  regressions, 168 seeded browser simulations, a reusable physics audit and
  a push/PR test workflow. No real video was published during this audit.

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

## Drop mode: 4 randomized arena layouts (2026-09-02)

User asked for Drop mode to have 4 different board layouts, randomly
selected per video, instead of always the same fixed Plinko field.

- [x] Added `DROP_ARENA_KINDS` (`classic_plinko`, `chevron_funnel`,
      `blade_storm`, `narrows_chute`), picked per-seed via the existing
      `peg_rng` so it's fully deterministic from the video seed like
      everything else. New helper functions `_build_drop_pegs`/
      `_drop_peg_keep` in `race_sim.py`.
      - `classic_plinko`: the original dense staggered field + 2 blades
        (unchanged from before this change).
      - `chevron_funnel`: a repeating hourglass/pinch gap down the
        track + 1 slower blade at the midpoint.
      - `blade_storm`: half-density peg field (every other row) + 4 fast
        blades spread down the track.
      - `narrows_chute`: two peg "walls" converge from the side walls
        toward center as the track descends (funnels racers into a
        single lane), opening back up for the last 15% before the
        finish + 1 blade near the throat.
      All four arenas **reuse the exact same underlying peg grid**
      (identical row/column spacing, identical jitter, identical
      peg_radius) that the original safety-margin comment already
      established keeps gaps at a safe ~2x racer diameter — each arena
      only masks out *which* grid positions get a peg, never changes the
      spacing itself, so none of them can introduce a tighter-than-tested
      gap. `narrows_chute`'s chute floor width is capped at >=
      0.40*track_w (~4.75 racer diameters), far above the safety margin.
- [x] Batch-audited all 4 arenas (60 seeds x 3 `n_racers` = ~180 sims,
      arenas split ~evenly by the random pick): 0% racers stuck/stalled
      3+ seconds in any arena (max observed stall 1.8s, well under the
      real-jam threshold), 0 non-finite-position errors, roughly even
      arena distribution confirming the random pick works. `classic_plinko`
      shows the same pre-existing ~4.8% "didn't finish within
      `max_seconds`" rate as before this change (not a regression — same
      board as always).
- [x] `simulate_drop`'s return dict now includes `arena_kind` (unused by
      `build_drop_clip`/`drop_gen.py` so far, kept for future
      title/description/debugging use).

## Battle mode: fixed zone racers getting permanently stuck (2026-09-10)

User asked to review how `weapon-ball-arena` (a sibling repo) implements
its shrinking-arena "zone", to understand it and check ours for bugs.
That repo's zone is a concentric circle that shrinks uniformly, backed
by continuous "storm" chip damage (`f.hp -= 9*dt`) for anyone outside
it — being outside is never a stable state, it either forces escape or
death, guaranteeing every fight resolves.

- [x] Batch-audited 120 then 300 `simulate_battle` seeds and found ~9%
      ended with **everyone alive**, no finish, no elimination — a
      "nothing happened" timeout. Traced the trajectory of a failing
      seed frame-by-frame: racers track closely just behind the closing
      top wall the whole match (correctly carried along by its motion),
      but once the wall reaches `BATTLE_ZONE_SHRINK_END_FRAC` and stops
      moving, any racer still on the wrong side is frozen there for the
      rest of the match — the wall is a full-width solid segment with
      no gap, so there is nothing left to carry a straggler through and
      no way to walk around it.
- [x] Fix (`race_sim.py`, `simulate_battle`): ported the weapon-ball-arena
      "storm" concept — track `outside_zone_steps` per racer, and once a
      racer has spent `BATTLE_STORM_KILL_SECONDS` (2.5s) continuously
      outside the safe funnel, eliminate them outright via the existing
      `_eliminate()` path. Guarantees resolution regardless of maze
      layout or AI edge cases, instead of depending solely on the wall's
      own sweep to always catch everyone in time.
- [x] Re-audited: "nothing happened" 9.2% -> 0.0% (300 seeds, 0 errors),
      avg finishes per sim unchanged (~1.6-1.7) — the fix only resolves
      the previously-stuck cases, doesn't change normal outcomes.

## Still to do

- [x] User confirmed on 2026-10-07 that the bot is running and uploading to
      YouTube. A fresh public upload was not needed for this local audit.
- [x] Added three original fallback tracks and `fallback_attribution.json`
      to `music/`, with `scripts/generate_fallback_music.py` for rebuilding.
      Local previews use these tracks without network access.
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

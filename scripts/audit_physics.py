import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import race_sim as sim

parser = argparse.ArgumentParser()
parser.add_argument('--seeds', type=int, default=20)
parser.add_argument('--output', required=True)
parser.add_argument('--mode', default='all')
args = parser.parse_args()
results = []
for name, run, minimum, maximum in [
    ('race', sim.simulate_race, 13, 28),
    ('battle', sim.simulate_battle, 14, 32),
    ('drop', sim.simulate_drop, 8, 22),
]:
    if args.mode not in ('all', name):
        continue
    for seed in range(args.seeds):
        for n in range(2, 9):
            race = run(1080, 1920, seed, fps=24, n_racers=n,
                       min_seconds=minimum, max_seconds=maximum)
            geo = race.get('geo')
            radius = geo.racer_radius if geo else race['racer_radius']
            frames = race['frames'][:race['finale_start']]
            stuck = []
            max_dwell = 0
            invalid = False
            for i in range(n):
                history = []
                prev_cell = None
                dwell = 0
                for fi, frame in enumerate(frames):
                    p = frame['pos'][i]
                    if p is None:
                        history = []
                        continue
                    invalid |= not all(math.isfinite(v) for v in p)
                    x, y = p[:2]
                    if geo:
                        cell = (int((x-geo.border_w)/geo.cell), int((y-geo.top_border)/geo.cell))
                        dwell = dwell + 1 if cell == prev_cell else 1
                        prev_cell = cell
                        max_dwell = max(max_dwell, dwell / 24)
                    history.append((x, y))
                    if len(history) > 72:
                        history.pop(0)
                    if len(history) == 72 and fi % 12 == 0:
                        span_x = max(p[0] for p in history) - min(p[0] for p in history)
                        span_y = max(p[1] for p in history) - min(p[1] for p in history)
                        if max(span_x, span_y) < radius * 1.5:
                            stuck.append((i, round(fi/24, 2)))
                            break
            ranking = race['full_ranking']
            results.append(dict(mode=name, seed=seed, n=n, stuck=stuck,
                max_dwell=round(max_dwell, 2), timeout=not race['winner_finished'],
                no_event=not race['finish_frame_flags'] and not race.get('elim_frame_flags'),
                invalid=invalid, bad_rank=sorted(ranking)!=list(range(n)),
                all_inactive=not any(frames[-1]['active']),
                duration=len(frames)/24, winner=race['winner_idx']))
    rows = [r for r in results if r['mode']==name]
    print(name, 'runs', len(rows), 'stuck', sum(bool(r['stuck']) for r in rows),
          'dwell3', sum(r['max_dwell']>=3 for r in rows),
          'no_event', sum(r['no_event'] for r in rows),
          'bad_rank', sum(r['bad_rank'] for r in rows), flush=True)
Path(args.output).write_text(json.dumps(results, indent=2))

if any(r["invalid"] or r["bad_rank"] or r["stuck"] for r in results):
    raise SystemExit(1)

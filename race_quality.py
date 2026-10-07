"""Bounded pre-render quality checks for automatically published races."""
import logging
import math
import random
from collections import deque

logger = logging.getLogger(__name__)


class SimulationQualityError(RuntimeError):
    pass


def quality_issues(race, required_finishers=1):
    issues = []
    n = race['n_racers']
    ranking = race['full_ranking']
    if sorted(ranking) != list(range(n)) or ranking[0] != race['winner_idx']:
        issues.append('invalid ranking')
    if race['result_reason'] == 'timeout':
        issues.append('time limit without a decisive result')
    if race['result_reason'] == 'finish' and race['n_finished_total'] < required_finishers:
        issues.append('not enough finishers to advance')
    frames = race['frames'][:race['finale_start']]
    if not frames:
        return issues + ['empty simulation']
    radius = race['geo'].racer_radius if 'geo' in race else race['racer_radius']
    window = max(2, round(race['fps'] * 3))
    for i in range(n):
        history = deque(maxlen=window)
        for fi, frame in enumerate(frames):
            point = frame['pos'][i]
            if point is None:
                history.clear()
                continue
            if not all(math.isfinite(v) for v in point):
                issues.append('non-finite coordinates')
                break
            history.append(point)
            if len(history) == window and fi % max(1,race['fps']//2) == 0:
                span = max(max(p[k] for p in history)-min(p[k] for p in history) for k in (0,1))
                if span < radius*1.5:
                    issues.append(f'racer {i} confined for 3 seconds')
                    break
    return issues


def generate_playable(simulate, *, seed, recent_matchups=(), max_attempts=8,
                      required_finishers=1, enforce_quality=True, **kwargs):
    """Retry simulations only; never retry publishing a whole video."""
    if max_attempts < 1:
        raise ValueError('max_attempts must be positive')
    rng = random.Random(f'{seed}:quality-retry')
    reasons = []
    for attempt in range(max_attempts):
        attempt_seed = seed if attempt == 0 else rng.randrange(1, 2**31)
        race = simulate(seed=attempt_seed, **kwargs)
        reasons = quality_issues(race, required_finishers) if enforce_quality else []
        if reasons:
            logger.warning('Arena seed %s rejected: %s', attempt_seed, '; '.join(reasons))
            continue
        duplicate = frozenset(r['name'] for r in race['racers']) in recent_matchups
        if duplicate and attempt+1 < max_attempts:
            continue
        race['generation_attempts'] = attempt+1
        return race
    raise SimulationQualityError(f'No publishable arena after {max_attempts} attempts: {"; ".join(reasons)}')

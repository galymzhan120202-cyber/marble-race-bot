import math
import random

import numpy as np
import pytest

import race_sim as sim


@pytest.mark.parametrize('kind', sim.MAZE_STRUCTURE_KINDS)
@pytest.mark.parametrize('cols', [4, 5, 6, 11])
def test_every_arena_cell_can_reach_finish(kind, cols):
    for seed in range(5):
        right, down = sim.generate_structured_maze(kind, cols, 16, random.Random(seed), n_racers=8)
        distances = sim.bfs_distance_field(right, down, cols, 16, (15, cols - 1))
        assert all(d is not None for row in distances for d in row)


@pytest.mark.parametrize('kind', sim.DROP_ARENA_KINDS)
def test_drop_obstacles_leave_clearance_around_spinning_blades(kind):
    left, right, top, finish, h = 64.8, 1015.2, 307.2, 6835.2, 1920
    radius = (right-left)*.042
    peg_radius = radius*.5
    pegs = sim._build_drop_pegs(kind, random.Random(17), left, right, top, finish, h, radius, peg_radius)
    assert pegs
    for x, y, _ in pegs:
        for fraction, length in sim.DROP_ARENA_SPINNERS[kind]:
            assert math.hypot(x-(left+right)/2, y-(top+(finish-top)*fraction)) >= (
                (right-left)*length/2 + peg_radius*1.8 + radius*2.5)


@pytest.mark.parametrize('run', [sim.simulate_race, sim.simulate_battle, sim.simulate_drop])
@pytest.mark.parametrize('seed,n', [(3,8),(17,6),(23,6),(25,8),(28,4),(31,8),(38,2),(56,8)])
def test_regression_seeds_have_valid_results_and_no_confined_stall(run, seed, n):
    race = run(1080, 1920, seed, fps=24, n_racers=n)
    assert sorted(race['full_ranking']) == list(range(n))
    assert race['full_ranking'][0] == race['winner_idx']
    assert len(race['finish_order']) == race['n_finished_total']
    if race['winner_finished']:
        assert race['winner_idx'] == race['finish_order'][0]
    else:
        assert race['result_reason'] in ('last_standing', 'timeout')
    frames = race['frames'][:race['finale_start']]
    assert frames
    if race['result_reason'] == 'last_standing':
        assert frames[-1]['active'][race['winner_idx']]
        assert sum(frames[-1]['active']) == 1
    for frame in frames:
        assert all(np.isfinite(p).all() for p in frame['pos'] if p is not None)
    # Only the last sampled physics frame may be empty, never seconds of
    # empty racing added to satisfy min_seconds after everyone has finished.
    assert all(any(f['active']) for f in frames[:-1])
    radius = race['geo'].racer_radius if 'geo' in race else race['racer_radius']
    for i in range(n):
        for end in range(72, len(frames), 12):
            points = [f['pos'][i] for f in frames[end-72:end]]
            if any(p is None for p in points):
                continue
            span = max(max(p[k] for p in points)-min(p[k] for p in points) for k in (0,1))
            assert span >= radius*1.5, (run.__name__, seed, n, i, end/24)


@pytest.mark.parametrize('run', [sim.simulate_race, sim.simulate_battle, sim.simulate_drop])
def test_render_fps_does_not_change_winner(run):
    races = [run(1080,1920,12,fps=fps,n_racers=4) for fps in (24,30,60)]
    assert len({r['winner_name'] for r in races}) == 1


@pytest.mark.parametrize('seed', [0, 1, 23, 28, 31, 38, 53])
def test_storm_exposure_is_bounded_and_resets_in_safety(seed):
    race=sim.simulate_battle(1080,1920,seed,n_racers=8,fps=24,max_seconds=12,min_seconds=1)
    assert any(max(f['storm_exposure'])>0 for f in race['frames'])
    for frame in race['frames'][:race['finale_start']]:
        for active,exposure in zip(frame['active'],frame['storm_exposure']):
            if active and sum(frame['active'])>1:
                assert exposure < sim.BATTLE_STORM_KILL_SECONDS
    assert race['result_reason'] in ('finish','last_standing','timeout')


def test_racers_can_cross_back_out_of_storm_and_reset_exposure():
    race=sim.simulate_battle(1080,1920,0,n_racers=8,fps=24,max_seconds=20,min_seconds=1)
    exposed=set()
    escaped=set()
    for frame in race['frames'][:race['finale_start']]:
        for i,exposure in enumerate(frame['storm_exposure']):
            if exposure>0:
                exposed.add(i)
            elif i in exposed and frame['active'][i]:
                escaped.add(i)
    assert escaped, 'The storm must not physically block a return to safety'


@pytest.mark.parametrize('kind,seed,racer', [('radial', 41, 2), ('terraces', 103, 3)])
def test_battle_recovery_can_back_out_despite_repeated_contacts(monkeypatch, kind, seed, racer):
    monkeypatch.setattr(sim, 'pick_maze_structure', lambda _: kind)
    race = sim.simulate_battle(1080, 1920, seed, n_racers=8)
    frames = race['frames'][:race['finale_start']]
    for end in range(72, len(frames), 12):
        points = [f['pos'][racer] for f in frames[end-72:end]]
        if any(p is None for p in points):
            continue
        span = max(max(p[k] for p in points)-min(p[k] for p in points) for k in (0, 1))
        assert span >= race['geo'].racer_radius * 1.5


@pytest.mark.parametrize('run,build', [
    (sim.simulate_race,sim.build_race_clip),
    (sim.simulate_battle,sim.build_battle_clip),
    (sim.simulate_drop,sim.build_drop_clip),
])
def test_video_frames_audio_and_frozen_finale(run, build):
    race = run(360,640,17,fps=24,n_racers=4,max_seconds=8,min_seconds=3)
    assert len({f['step'] for f in race['frames'][race['finale_start']:]}) == 1
    clip = build(race)
    try:
        for t in (0,sim.INTRO_SECONDS,clip.duration/2,clip.duration-.05):
            frame = clip.get_frame(t)
            assert frame.shape == (640,360,3)
            assert frame.dtype == np.uint8
        audio, sr = sim.build_sfx_array(race)
        assert sr == 44100 and audio.shape[1] == 2
        assert len(audio)/sr >= clip.duration
        assert np.isfinite(audio).all() and np.max(np.abs(audio)) <= 1
    finally:
        clip.close()


@pytest.mark.parametrize('run', [sim.simulate_race,sim.simulate_battle,sim.simulate_drop])
@pytest.mark.parametrize('kwargs', [{'fps':0},{'fps':25},{'n_racers':0},{'max_seconds':0},{'min_seconds':40}])
def test_invalid_parameters_fail_before_physics(run, kwargs):
    with pytest.raises(ValueError):
        run(360,640,1,**kwargs)

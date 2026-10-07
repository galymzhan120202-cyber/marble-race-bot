"""Rendering must describe the current frame without leaking future results."""
import numpy as np
import pytest
from PIL import Image

import race_sim as sim


def test_battle_camera_does_not_look_between_distant_packs_or_at_eliminated_pack():
    race = {'fps': 24, 'frames': [
        {'pos': [(100, 200, 0), (200, 240, 0), (100, 4200, 0)]},
        {'pos': [None, None, (100, 4200, 0)]},
    ]}
    tops = sim._camera_positions(race, 5000, 900, average=True)
    for top, frame in zip(tops, race['frames']):
        assert 0 <= top <= 4100
        assert any(top <= p[1] <= top+900 for p in frame['pos'] if p)
    assert tops[0] <= 200
    assert tops[1] <= 4200 <= tops[1]+900


def test_camera_keeps_finish_visible_after_the_finisher_disappears():
    race = {'fps': 24, 'frames': [{'pos': [(100, 4200, 0)]}] * 20 + [{'pos': [None]}] * 40,
            'finish_frame_flags': {20: [(0, 100, 4250)]}}
    tops = sim._camera_positions(race, 5000, 900)
    assert all(top <= 4250 <= top+900 for top in tops[20:])


@pytest.mark.parametrize('mode', ['MAZE RACE', 'BATTLE ROYALE', 'MARBLE DROP'])
@pytest.mark.parametrize('size', [(360, 640), (640, 360)])
def test_live_hud_is_independent_of_eventual_result(mode, size):
    race = {'n_racers': 8, 'racers': sim.RACER_POOL[:8], 'max_seconds': 40,
            'winner_idx': 0, 'winner_name': 'Blacky', 'full_ranking': list(range(8))}
    frame = {'active': [True]*8, 'finished': [False]*8, 'step': 720,
             'n_alive': 8, 'storm_exposure': [0]*8}
    first = Image.new('RGBA', size)
    sim._draw_video_hud(first, race, frame, mode, (100, 200, 255))
    race.update(winner_idx=7, winner_name='Rosy', full_ranking=list(reversed(range(8))))
    second = Image.new('RGBA', size)
    sim._draw_video_hud(second, race, frame, mode, (100, 200, 255))
    assert np.array_equal(np.array(first), np.array(second))


def test_small_preview_labels_fit_without_clipping():
    label = 'FARTHEST PROGRESS AT TIME-OUT'
    font = sim._fit_text_font(label, sim.get_font(24), 160)
    assert sim._TEXT_PROBE.textlength(label, font=font) <= 160


def test_elimination_cause_and_finished_status_match_recorded_events():
    race = sim.simulate_battle(1080, 1920, 0, n_racers=8, fps=24, max_seconds=20, min_seconds=1)
    eliminated = {idx for events in race['elim_frame_flags'].values() for idx, _, _ in events}
    assert set(race['elimination_reasons']) == eliminated
    for fi, events in race['elim_frame_flags'].items():
        for i, _, _ in events:
            assert not race['frames'][fi]['active'][i]
            assert not race['frames'][fi]['finished'][i]
            if race['elimination_reasons'][i] == 'storm':
                assert race['frames'][fi]['storm_exposure'][i] >= sim.BATTLE_STORM_KILL_SECONDS
    for fi, events in race['finish_frame_flags'].items():
        for i, _, _ in events:
            assert race['frames'][fi]['finished'][i]

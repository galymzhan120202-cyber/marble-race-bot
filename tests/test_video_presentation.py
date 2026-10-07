"""Rendering must describe the current frame without leaking future results."""
import numpy as np
import pytest
from PIL import Image, ImageDraw
from copy import deepcopy

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


def test_tournament_camera_tracks_remaining_qualifier_before_holding_finish():
    race = {'fps': 24, 'qualifier_count': 2, 'frames': [
        {'pos': [(100, 4200, 0), (200, 2100, 0)]},
        {'pos': [None, (200, 2100, 0)]},
        {'pos': [None, (200, 2300, 0)]},
        {'pos': [None, None]},
    ], 'finish_frame_flags': {1: [(0, 100, 4250)], 3: [(1, 200, 4250)]}}
    tops = sim._camera_positions(race, 5000, 900)
    assert tops[1] <= 2100 <= tops[1]+900
    assert tops[2] <= 2300 <= tops[2]+900
    assert tops[3] <= 4250 <= tops[3]+900


@pytest.mark.parametrize('kind,seed', [('spine_branches', 41), ('scatter_pillars', 997)])
def test_tournament_camera_regressions_never_show_empty_track_while_spot_remains(monkeypatch, kind, seed):
    monkeypatch.setattr(sim, 'pick_maze_structure', lambda _: kind)
    race = sim.simulate_race(1920,1080,seed,n_racers=4,rows=32,fps=12,
                             max_seconds=55,min_seconds=18,required_finishers=2)
    race['qualifier_count'] = 2
    viewport = 1080-sim._video_hud_height(1920,1080)
    tops = sim._camera_positions(race,race['maze_img'].height,viewport)
    for frame, top in zip(race['frames'][:race['finale_start']], tops):
        if frame['n_finished'] < 2:
            assert any(p and top <= p[1] <= top+viewport for p in frame['pos'])


def test_places_and_offscreen_directions_use_only_current_and_past_events():
    frames = [
        {'pos': [(10,100,0),(20,500,0),(30,1000,0)], 'active': [True]*3},
        {'pos': [None,(20,550,0),(30,1000,0)], 'active': [False,True,True]},
        {'pos': [None,None,(30,1000,0)], 'active': [False,False,True]},
    ]
    race = {'n_racers': 3, 'frames': frames, 'racer_radius': 20,
             'finish_frame_flags': {1: [(0,10,1200)], 2: [(1,20,1200)]}}
    states = sim._presentation_states(race,[300]*3,600)
    assert states[0]['places'] == (None,None,None)
    assert states[0]['directions'] == ('above',None,'below')
    assert states[1]['places'] == (1,None,None)
    assert states[1]['directions'] == (None,None,'below')
    assert states[2]['places'] == (1,2,None)
    changed = deepcopy(race)
    changed['finish_frame_flags'][2] = [(2,30,1200)]
    assert sim._presentation_states(changed,[300]*3,600)[:2] == states[:2]


def test_finish_labels_have_consistent_real_time_fades_at_different_fps():
    def render(fps, seconds):
        race = {'fps': fps, 'racers': [{'name': 'Ghost'}],
                'finish_frame_flags': {0: [(0,180,350)]}}
        image = Image.new('RGBA',(360,640),(25,40,60,255))
        sim._draw_race_events(image,race,round(seconds*fps),0,100,{'places': [1]})
        return np.array(image)
    assert np.array_equal(render(24,.5),render(60,.5))
    assert not np.array_equal(render(24,.5),render(24,0))
    assert np.all(render(60,1) == np.array([25,40,60,255]))


@pytest.mark.parametrize('x,y',[(-100,100),(500,100),(180,2000)])
def test_event_labels_stay_inside_the_play_area(x,y):
    race = {'fps': 24, 'racers': [{'name':'Blacky'}], 'qualifier_count':2,
            'finish_frame_flags': {0: [(0,x,y)]}}
    img = Image.new('RGBA',(360,640))
    sim._draw_race_events(img,race,0,0,100,{'places':[1]})
    x0,y0,x1,y1 = img.getbbox()
    assert 0 < x0 < x1 < 360
    assert 100 < y0 < y1 < 640


def test_simultaneous_extra_finishers_are_not_announced_as_qualifiers(monkeypatch):
    labels = []
    original = ImageDraw.ImageDraw.text
    def capture(draw, xy, text, *args, **kwargs):
        labels.append(text)
        return original(draw, xy, text, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', capture)
    race = {'fps': 24, 'racers': sim.RACER_POOL[:3], 'qualifier_count': 2,
            'finish_frame_flags': {0: [(0,50,400),(1,180,400),(2,300,400)]}}
    sim._draw_race_events(Image.new('RGBA',(360,640)),race,0,0,100,{'places':[1,2,3]})
    assert labels == ['Blacky QUALIFIED / #1', 'Sunny QUALIFIED / #2', 'Cocoa FINISHED / #3']


@pytest.mark.parametrize('run', [sim.simulate_race, sim.simulate_battle, sim.simulate_drop])
def test_explicit_roster_preserves_character_colours_across_heats(run):
    # Similar orange/gold entrants used to change colour when paired up.
    roster = [dict(sim.RACER_POOL[i]) for i in (14,4,1,2)]
    expected = {r['name']:r['color'] for r in roster}
    for seed, entrants in ((41,roster),(997,list(reversed(roster)))):
        race = run(360,640,seed,fps=12,forced_racers=entrants,max_seconds=2,min_seconds=1)
        assert {r['name']:r['color'] for r in race['racers']} == expected
    assert {r['name']:r['color'] for r in roster} == expected


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

"""Recorded motion must be causal, bounded, and independent of frame order."""
import copy
import math

import numpy as np
import pytest
from PIL import Image

import race_sim as sim
from race_quality import quality_issues
from video_motion import VideoMotion, VICTORY_STYLES, impact_scale, victory_pose, victory_tile


@pytest.mark.parametrize("run,build", [(sim.simulate_race, sim.build_race_clip),
                                      (sim.simulate_battle, sim.build_battle_clip),
                                      (sim.simulate_drop, sim.build_drop_clip)])
def test_rendering_out_of_order_preserves_pixels_physics_and_audio_length(run, build):
    race = run(360, 640, 41, fps=60, n_racers=4, min_seconds=0, max_seconds=4)
    original = copy.deepcopy(race["frames"])
    assert race["motion_impacts"]
    assert all(math.hypot(event.nx, event.ny) == pytest.approx(1) for event in race["motion_impacts"])
    clip = build(race)
    try:
        times = [0, 1.4, 2.7, sim.INTRO_SECONDS+race["finale_start"]/60+.6, clip.duration-.03]
        expected = [clip.get_frame(t).copy() for t in times]
        for i in (4, 1, 3, 0, 2, 1):
            np.testing.assert_array_equal(clip.get_frame(times[i]), expected[i])
        assert race["frames"] == original
        audio, sr = sim.build_sfx_array(race)
        assert len(audio)/sr >= clip.duration
        assert np.isfinite(audio).all()
    finally:
        clip.close()


def test_impacts_compress_rebound_and_settle_without_changing_area():
    assert impact_scale(0, 1)[0] < 1
    assert impact_scale(.12, 1)[0] > 1
    for age in np.linspace(0, .45, 100):
        x, y = impact_scale(age, 1)
        assert .77 < x < 1.08
        assert x*y == pytest.approx(1)
    assert impact_scale(.45, 1) == (1, 1)
    assert impact_scale(-.01, 1) == (1, 1)


@pytest.mark.parametrize("name", VICTORY_STYLES)
def test_victory_motion_is_finite_and_stays_inside_its_tile(name):
    icon = Image.new("RGBA", (100, 100), (240, 180, 80, 255))
    for time in (0, .1, .5, 1, 1.7, 2.8, 3.199, 3.2, 5):
        pose = victory_pose(name, time)
        assert all(math.isfinite(v) for v in pose)
        tile = victory_tile(icon, name, time, 96)
        alpha = np.array(tile)[:, :, 3]
        assert not alpha[0].any() and not alpha[-1].any()
        assert not alpha[:, 0].any() and not alpha[:, -1].any()
    assert victory_pose(name, 0) == victory_pose(name, 3.2) == (0, 0, 0, 1, 1)


def test_camera_uses_only_past_events_and_retains_the_deciding_finish():
    race = sim.simulate_drop(360, 640, 41, fps=60, n_racers=4)
    hud = sim._video_hud_height(360, 640)
    tops = sim._camera_positions(race, int(race["finish_y"]+640), 640-hud)
    motion = VideoMotion(race, tops, 640-hud)
    prefix = dict(race, frames=race["frames"][:100], winner_idx=999, winner_name="UNKNOWN")
    prefix["motion_impacts"] = [event for event in race["motion_impacts"] if event.time <= 100/60]
    prefix["finish_frame_flags"] = {i:v for i,v in race["finish_frame_flags"].items() if i < 100}
    earlier = VideoMotion(prefix, tops[:100], 640-hud)
    assert motion.cameras[:100] == earlier.cameras
    for i, (x, y, width, height) in enumerate(motion.cameras):
        assert 1 <= 360/width <= 1.120001
        assert 0 <= x <= 360-width+1e-8
        assert tops[i] <= y <= tops[i]+640-hud-height+1e-8
        for _, fx, fy in race["finish_frame_flags"].get(i, ()):
            assert x <= fx <= x+width and y <= fy <= y+height


@pytest.mark.parametrize("kind", ["aurora_loops", "pulse_grid"])
@pytest.mark.parametrize("seed", [17, 41, 103])
@pytest.mark.parametrize("count", [2, 4, 8])
def test_new_maze_arenas_finish_and_replay_by_recorded_id(kind, seed, count):
    race = sim.simulate_race(1080, 1920, seed, n_racers=count, arena_kind=kind)
    assert race["arena_kind"] == kind
    assert race["winner_finished"]
    assert not quality_issues(race)
    replay = sim.simulate_race(1080, 1920, seed, n_racers=count, arena_kind=kind, fps=60)
    assert race["full_ranking"] == replay["full_ranking"]
    assert race["frames"][race["finale_start"]-1] == replay["frames"][replay["finale_start"]-1]


def test_unknown_maze_arena_is_rejected():
    with pytest.raises(ValueError, match="Unknown maze arena"):
        sim.simulate_race(360, 640, 1, arena_kind="missing")

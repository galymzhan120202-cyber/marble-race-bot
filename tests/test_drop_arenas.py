"""Selectable Drop tracks must remain playable and reproducible."""
import numpy as np
import pytest

import race_sim as sim
from race_quality import quality_issues


@pytest.mark.parametrize("kind", sim.DROP_ARENA_KINDS)
@pytest.mark.parametrize("count", range(2, 9))
@pytest.mark.parametrize("seed", [17, 41, 103])
def test_selected_drop_arenas_finish_without_confined_stalls(kind, count, seed):
    race = sim.simulate_drop(1080, 1920, seed, n_racers=count, arena_kind=kind)
    assert race["arena_kind"] == kind
    assert race["winner_finished"]
    assert not quality_issues(race)
    assert sorted(race["full_ranking"]) == list(range(count))
    assert race["obstacle_contacts"][race["winner_idx"]] >= 2


@pytest.mark.parametrize("kind", sim.DROP_ARENA_KINDS)
@pytest.mark.parametrize("seed", range(21))
def test_peg_gates_cover_straight_side_routes_without_trapping_wall_slots(kind, seed):
    race = sim.simulate_drop(1080, 1920, seed, n_racers=4, arena_kind=kind)
    radius, peg_radius = race["racer_radius"], race["peg_radius"]
    # A square contains a circle of radius .85r at every rotation. Every
    # vertical route across the course must meet a real peg, even when
    # the rotating blades happen to be aligned with the falling racer.
    reach = radius*.85+peg_radius
    intervals = sorted((x-reach,x+reach) for x,_,_ in race["pegs"])
    covered = race["left"]+radius*.85
    for start,end in intervals:
        if end < covered:
            continue
        assert start <= covered, f"{kind}/{seed}: clear vertical side route"
        covered = max(covered,end)
    assert covered >= race["right"]-radius*.85
    for x,_,_ in race["pegs"]:
        wall_distance = min(x-race["left"],race["right"]-x)
        # A peg close to a wall must form an attached inward deflector,
        # not the narrow pocket introduced by centring the old lattice.
        assert wall_distance <= radius*.6 or wall_distance >= radius*2.4


@pytest.mark.parametrize("kind", ["split_cascade", "orbit_run"])
def test_selected_new_drop_arenas_replay_exactly_across_render_rates(kind):
    first = sim.simulate_drop(1080, 1920, 41, n_racers=6, arena_kind=kind, fps=24)
    replay = sim.simulate_drop(1080, 1920, 41, n_racers=6, arena_kind=kind, fps=24)
    high_fps = sim.simulate_drop(1080, 1920, 41, n_racers=6, arena_kind=kind, fps=60)
    assert first["frames"] == replay["frames"]
    assert first["pegs"] == replay["pegs"] == high_fps["pegs"]
    assert first["winner_idx"] == replay["winner_idx"] == high_fps["winner_idx"]
    assert first["arena_name"] == sim.DROP_ARENA_STYLES[kind]["name"]
    assert not quality_issues(first)


def test_automatic_drop_arena_can_be_replayed_with_its_recorded_id():
    first = sim.simulate_drop(360, 640, 31, n_racers=4)
    replay = sim.simulate_drop(360, 640, 31, n_racers=4, arena_kind=first["arena_kind"])
    assert first["frames"] == replay["frames"]
    assert first["pegs"] == replay["pegs"]


def test_unknown_drop_arena_is_rejected_before_physics():
    with pytest.raises(ValueError, match="Unknown drop arena"):
        sim.simulate_drop(360, 640, 31, arena_kind="missing_track")


@pytest.mark.parametrize("kind", sim.DROP_ARENA_KINDS)
def test_drop_static_art_is_baked_once_and_sample_frames_stay_valid(monkeypatch, kind):
    race = sim.simulate_drop(360, 640, 17, n_racers=4, arena_kind=kind)
    original = sim.draw_drop_background
    calls = []
    def draw(track):
        calls.append(track["arena_kind"])
        return original(track)
    monkeypatch.setattr(sim, "draw_drop_background", draw)
    clip = sim.build_drop_clip(race)
    try:
        for t in (0, sim.INTRO_SECONDS+.2, clip.duration/2, clip.duration-.05):
            frame = clip.get_frame(t)
            assert frame.shape == (640, 360, 3)
            assert frame.dtype == np.uint8
        assert calls == [kind]
    finally:
        clip.close()

"""Physics starts and final partial video frames must describe real states."""
from types import SimpleNamespace

import numpy as np
import pymunk
import pytest

import race_sim as sim
from race_quality import quality_issues


RUNS = [sim.simulate_race, sim.simulate_battle, sim.simulate_drop]


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("max_seconds", [0.001, float("inf"), float("nan")])
def test_unrenderable_duration_is_rejected_before_physics(monkeypatch, run, max_seconds):
    def unexpected_space(*args, **kwargs):
        pytest.fail("Invalid simulation duration reached physics setup")

    monkeypatch.setattr(pymunk, "Space", unexpected_space)
    with pytest.raises(ValueError, match="duration"):
        run(360, 640, 17, min_seconds=0, max_seconds=max_seconds, n_racers=2)


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("fps", [1, 24, 60, 120])
def test_decisive_finish_stops_before_a_later_physics_step(monkeypatch, run, fps):
    original = pymunk.Space.step
    steps = 0

    def successive_finishes(space, dt):
        nonlocal steps
        steps += 1
        if steps in (7, 8):
            sensor = next(s for s in space.shapes if s.collision_type == sim.FINISH_TYPE)
            racer = next(s for s in space.shapes
                         if s.collision_type == sim.RACER_TYPE_BASE + steps - 7)
            racer.body.position = sensor.body.local_to_world((sensor.a + sensor.b) / 2)
            racer.body.velocity = (0, 0)
            racer.body.force = (0, 0)
            space.reindex_shapes_for_body(racer.body)
        return original(space, dt)

    monkeypatch.setattr(pymunk.Space, "step", successive_finishes)
    race = run(360, 640, 17, n_racers=2, fps=fps, min_seconds=0, max_seconds=1)
    assert steps == 7
    assert race["frames"][race["finale_start"] - 1]["step"] == 7
    assert race["finish_order"] == [0]
    assert race["frames"][-1]["active"] == [False, True]
    assert [event[0] for events in race["finish_frame_flags"].values()
            for event in events] == [0]


@pytest.mark.parametrize("run", RUNS)
def test_real_terminal_state_is_identical_across_video_frame_rates(run):
    races = [run(360, 640, 17, n_racers=4, fps=fps) for fps in (1, 24, 60, 120)]
    expected = races[0]
    for race in races[1:]:
        for key in ("winner_idx", "result_reason", "finish_order", "full_ranking"):
            assert race[key] == expected[key]
        assert race["frames"][-1] == expected["frames"][-1]


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("max_steps", [1, 7, 12])
def test_partial_last_frame_records_the_final_physics_step(run, max_steps):
    race = run(360, 640, 17, n_racers=2, fps=24,
               min_seconds=0, max_seconds=(max_steps + 0.1) / sim.PHYSICS_HZ)
    frames = race["frames"][:race["finale_start"]]
    assert frames[-1]["step"] == max_steps
    assert len(frames) == (max_steps + 4) // 5
    assert race["frames"][-1] == frames[-1]


@pytest.mark.parametrize("run", RUNS)
def test_finish_in_partial_last_frame_is_visible_and_emitted_once(monkeypatch, run):
    original = pymunk.Space.step
    steps = 0

    def finish_on_last_step(space, dt):
        nonlocal steps
        steps += 1
        if steps == 12:
            sensor = next(s for s in space.shapes if s.collision_type == sim.FINISH_TYPE)
            racer = next(s for s in space.shapes if s.collision_type == sim.RACER_TYPE_BASE)
            racer.body.position = sensor.body.local_to_world((sensor.a + sensor.b) / 2)
            racer.body.velocity = (0, 0)
            racer.body.force = (0, 0)
            space.reindex_shapes_for_body(racer.body)
        return original(space, dt)

    monkeypatch.setattr(pymunk.Space, "step", finish_on_last_step)
    race = run(360, 640, 17, n_racers=2, fps=24,
               min_seconds=0, max_seconds=12.1 / sim.PHYSICS_HZ)
    assert race["winner_idx"] == 0 and race["winner_finished"]
    assert not race["frames"][-1]["active"][0]
    assert race["frames"][-1]["pos"][0] is None
    assert list(race["finish_frame_flags"]) == [2]
    assert [event[0] for event in race["finish_frame_flags"][2]] == [0]


@pytest.mark.parametrize("run", RUNS)
def test_partial_frame_does_not_reemit_previous_interval_bumps(monkeypatch, run):
    original_collision = pymunk.Space.on_collision
    original_step = pymunk.Space.step
    callbacks = {}
    steps = 0

    def register(space, *args, **kwargs):
        callbacks[id(space)] = kwargs["post_solve"]
        return original_collision(space, *args, **kwargs)

    def single_bump(space, dt):
        nonlocal steps
        result = original_step(space, dt)
        steps += 1
        if steps == 9:
            wall = next(s for s in space.shapes if s.collision_type == sim.WALL_TYPE)
            racer = next(s for s in space.shapes if s.collision_type == sim.RACER_TYPE_BASE)
            arbiter = SimpleNamespace(
                shapes=(wall, racer), total_impulse=pymunk.Vec2d(1, 0),
                contact_point_set=SimpleNamespace(points=[
                    SimpleNamespace(point_a=pymunk.Vec2d(-9876, -5432))]))
            callbacks[id(space)](arbiter, space, None)
        return result

    monkeypatch.setattr(pymunk.Space, "on_collision", register)
    monkeypatch.setattr(pymunk.Space, "step", single_bump)
    race = run(360, 640, 17, n_racers=2, fps=24,
               min_seconds=0, max_seconds=12.1 / sim.PHYSICS_HZ)
    injected = [fi for fi, event in race["bump_frame_flags"].items()
                if event[:2] == (-9876, -5432)]
    assert injected == [1]


def test_real_finish_before_fractional_time_limit_is_not_lost():
    race = sim.simulate_race(1080, 1920, 0, n_racers=4,
                            min_seconds=0, max_seconds=1951.1 / sim.PHYSICS_HZ)
    assert race["winner_finished"]
    assert race["frames"][-1]["step"] == 1951
    assert not race["frames"][-1]["active"][race["winner_idx"]]
    assert race["finish_frame_flags"]


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("fps", [24, 60, 120])
@pytest.mark.parametrize("gaps,expected", [((1, 5), [0, 1]),
                                          ((5, 1), [1, 0]),
                                          ((2, 2), [0, 1])])
def test_same_step_finish_order_follows_crossing_time(monkeypatch, run, fps, gaps, expected):
    original = pymunk.Space.on_collision

    def arrange_crossings(space, *args, **kwargs):
        result = original(space, *args, **kwargs)
        sensor = next(s for s in space.shapes if s.collision_type == sim.FINISH_TYPE)
        for i, gap in enumerate(gaps):
            racer = next(s for s in space.shapes if s.collision_type == sim.RACER_TYPE_BASE + i)
            racer.body.angle = 0
            reach = (racer.radius if isinstance(racer, pymunk.Circle)
                     else max(v.y for v in racer.get_vertices()) + racer.radius)
            racer.body.position = (sensor.a.x + (sensor.b.x - sensor.a.x) * (i + 1) / 3,
                                   sensor.a.y - sensor.radius - reach - gap)
            racer.body.velocity = (0, 1200)
            space.reindex_shapes_for_body(racer.body)
        return result

    # Arrange actual bodies before the simulator snapshots its first step.
    # Both cross within that step, at different fractions of its duration.
    monkeypatch.setattr(pymunk.Space, "on_collision", arrange_crossings)
    race = run(1080, 1920, 17, n_racers=2, fps=fps,
               min_seconds=0, max_seconds=0.1)
    assert race["finish_order"] == expected
    assert race["full_ranking"] == expected
    assert race["winner_idx"] == expected[0]
    assert race["winner_name"] == race["racers"][expected[0]]["name"]
    assert [event[0] for events in race["finish_frame_flags"].values()
            for event in events] == expected


@pytest.mark.parametrize("count", range(2, 17))
@pytest.mark.parametrize("width,height", [(360, 640), (1080, 1920)])
@pytest.mark.parametrize("seed", [0, 17])
def test_drop_rosters_start_without_interpenetration(monkeypatch, count, width, height, seed):
    original = pymunk.Space.step
    starts = []

    def inspect_start(space, dt):
        if not starts:
            racers = [s for s in space.shapes
                      if sim.RACER_TYPE_BASE <= s.collision_type < sim.RACER_TYPE_BASE + count]
            for racer in racers:
                assert not space.shape_query(racer), (count, width, seed, racer.collision_type)
            starts.extend(tuple(r.body.position) for r in racers)
        return original(space, dt)

    monkeypatch.setattr(pymunk.Space, "step", inspect_start)
    sim.simulate_drop(width, height, seed, n_racers=count, fps=120,
                      min_seconds=0, max_seconds=1 / sim.PHYSICS_HZ)
    assert len(starts) == count


@pytest.mark.parametrize("count,expected", [
    (2, [(378.4547760201091, 305.5874817153476, 11.18339270969066),
         (701.6822806482577, 307.6822246725604, 7.622292070881256)]),
    (8, [(164.1625927826754, 301.5232413454863, 3.9819041131642763),
         (279.9423231386622, 304.22860521015866, -0.05509575569890184),
         (378.678961448732, 311.3559337095411, -15.304639419622896),
         (485.62545499057074, 313.18136406104423, 15.050703180982692),
         (597.8017440070658, 311.70379802553936, 12.00064180408823),
         (701.6890978494712, 307.9067024232561, -15.648206035878014),
         (799.3601601518435, 307.67956020744145, -13.14787246148589),
         (911.8203708969568, 304.9103943594999, 14.374461851967489)]),
])
def test_established_small_drop_rosters_keep_their_seeded_starts(count, expected):
    race = sim.simulate_drop(1080, 1920, 17, n_racers=count, fps=120,
                             min_seconds=0, max_seconds=1 / sim.PHYSICS_HZ)
    np.testing.assert_allclose(race["frames"][0]["pos"], expected, rtol=0, atol=1e-10)


@pytest.mark.parametrize("kind", sim.DROP_ARENA_KINDS)
@pytest.mark.parametrize("count", [9, 12, 16])
def test_large_drop_grid_still_finishes_and_replays_across_fps(kind, count):
    first = sim.simulate_drop(1080, 1920, 17, n_racers=count, arena_kind=kind, fps=24)
    replay = sim.simulate_drop(1080, 1920, 17, n_racers=count, arena_kind=kind, fps=60)
    assert not quality_issues(first)
    assert first["winner_finished"]
    assert first["winner_idx"] == replay["winner_idx"]

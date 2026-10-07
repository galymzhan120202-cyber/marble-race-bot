"""Check arena topology against the actual collision shapes, not just BFS."""
import random
import math

import pymunk
import pytest
import networkx as nx

import race_sim as sim


@pytest.mark.parametrize('kind', sim.MAZE_STRUCTURE_KINDS)
def test_storm_escape_uses_nearest_safe_passage_across_advancing_boundary(kind):
    cols, rows = 6, 20
    geo = sim.MazeGeometry(1080, cols, rows)
    right, down = sim.generate_structured_maze(kind, cols, rows, random.Random(41), 8)
    finish = sim.finish_routes(right, down, cols, rows, (rows-1, 3), 8)
    graph = nx.Graph()
    graph.add_nodes_from((r, c) for r in range(rows) for c in range(cols))
    graph.add_edges_from(((r,c),(r,c+1)) for r in range(rows) for c in range(cols-1) if right[r][c])
    graph.add_edges_from(((r,c),(r+1,c)) for r in range(rows-1) for c in range(cols) if down[r][c])
    routes = sim.StormEscapeRoutes(geo, right, down)
    for row in (2, 5, 10, 15, 18):
        top = geo.top_border + geo.cell * row
        velocity = geo.cell * .6
        safe_y = top + geo.racer_radius + velocity * .35
        sources = [p for p in graph if geo.cell_center(*p)[1] >= safe_y]
        expected = nx.multi_source_dijkstra_path_length(graph, sources)
        distances = routes.distances(safe_y)
        assert all(distances[r][c] == length for (r,c),length in expected.items())
        for cell, length in expected.items():
            if not length:
                continue
            target = routes.waypoint(cell, geo.cell_center(*cell), top, velocity, finish)
            target_cell = (math.floor((target[1]-geo.top_border)/geo.cell),
                           math.floor((target[0]-geo.border_w)/geo.cell))
            assert graph.has_edge(cell, target_cell)
            assert expected[target_cell] == length-1


def test_storm_escape_can_disagree_with_finish_route():
    # Safe dead end below (1,1); the shorter finish route first goes left.
    geo = sim.MazeGeometry(360, 3, 4)
    right = [[True,True], [True,True], [False,False], [True,True]]
    down = [[True,True,True], [True,True,True], [True,False,True]]
    finish = sim.bfs_distance_field(right, down, 3, 4, (3,0))
    assert finish[1][0] < finish[2][1]
    routes = sim.StormEscapeRoutes(geo, right, down)
    top = geo.top_border + 2*geo.cell
    assert routes.waypoint((1,1), geo.cell_center(1,1), top, 0, finish) == geo.cell_center(2,1)
    # Once safe, do not immediately turn back into the storm.
    assert routes.waypoint((2,1), geo.cell_center(2,1), top, 0, finish) == geo.cell_center(2,1)


@pytest.mark.parametrize('kind', sim.MAZE_STRUCTURE_KINDS)
@pytest.mark.parametrize('cols,rows,width', [(4,14,360), (5,20,1080), (11,32,1920)])
def test_maze_paths_and_finish_opening_match_physical_walls(kind, cols, rows, width):
    geo = sim.MazeGeometry(width, cols, rows)
    # Include the square racer's rounded corners at any rotation.
    body_radius = geo.racer_radius * (1 + 2**0.5 * .08)
    for seed in (41, 103, 997):
        rng = random.Random(seed)
        right, down = sim.generate_structured_maze(kind, cols, rows, rng, n_racers=8)
        finish_col = rng.randrange(cols)
        distances = sim.finish_routes(right, down, cols, rows, (rows-1, finish_col), 8)
        graph = nx.Graph()
        graph.add_nodes_from((r,c) for r in range(rows) for c in range(cols))
        graph.add_edges_from(((r,c),(r,c+1)) for r in range(rows) for c in range(cols-1) if right[r][c])
        graph.add_edges_from(((r,c),(r+1,c)) for r in range(rows-1) for c in range(cols) if down[r][c])
        expected = nx.single_source_shortest_path_length(graph,(rows-1,finish_col))
        assert len(expected) == rows*cols
        assert all(distances[r][c] == length for (r,c),length in expected.items())
        assert max(distances[i//cols][i%cols] for i in range(8)) <= max(rows*2, rows+cols)
        space = pymunk.Space()
        for a, b in sim.build_wall_segments(geo, right, down, finish_col):
            space.add(pymunk.Segment(space.static_body, a, b, geo.wall_thickness/2))

        def blocked(a, b):
            return bool(space.segment_query(a, b, body_radius, pymunk.ShapeFilter()))

        for r in range(rows):
            for c in range(cols):
                assert distances[r][c] is not None
                center = geo.cell_center(r,c)
                # Spawn/target centers must fit a complete body.
                assert not space.point_query(center, body_radius, pymunk.ShapeFilter())
                if c+1 < cols:
                    assert blocked(center, geo.cell_center(r,c+1)) == (not right[r][c])
                if r+1 < rows:
                    assert blocked(center, geo.cell_center(r+1,c)) == (not down[r][c])
        for c in range(cols):
            center = geo.cell_center(rows-1,c)
            finish = (center[0], geo.finish_line_y)
            assert blocked(center, finish) == (c != finish_col)


@pytest.mark.parametrize('kind', sim.MAZE_STRUCTURE_KINDS)
def test_weapon_pickups_are_distinct_reachable_and_clear_of_walls(kind):
    cols, rows = 6, 20
    geo = sim.MazeGeometry(1080, cols, rows)
    for seed in (41, 103, 997):
        rng = random.Random(seed)
        right, down = sim.generate_structured_maze(kind, cols, rows, rng, n_racers=8)
        cells = sim._place_pickups(right, down, cols, rows, rng, 4)
        assert len(cells) == len(set(cells)) == 4
        distances = sim.bfs_distance_field(right, down, cols, rows, (0,0))
        space = pymunk.Space()
        for a, b in sim.build_wall_segments(geo, right, down, 0):
            space.add(pymunk.Segment(space.static_body, a, b, geo.wall_thickness/2))
        for r, c in cells:
            assert distances[r][c] is not None
            assert len(sim.open_neighbors(r,c,right,down,cols,rows)) >= 2
            assert not space.point_query(geo.cell_center(r,c), geo.racer_radius*1.3, pymunk.ShapeFilter())


def test_long_tournament_labyrinth_finishes_within_the_heat(monkeypatch):
    monkeypatch.setattr(sim, 'pick_maze_structure', lambda seed: 'sparse_labyrinth')
    race = sim.simulate_race(1920,1080,103,n_racers=4,rows=32,
                             max_seconds=55,min_seconds=18,required_finishers=2)
    assert race['n_finished_total'] >= 2
    assert race['result_reason'] == 'finish'


@pytest.mark.parametrize('kind', sim.MAZE_STRUCTURE_KINDS)
@pytest.mark.parametrize('n',[2,4,8,16])
def test_starting_grid_reduces_route_disadvantage_and_is_repeatable(kind,n):
    cols,rows = 6,20
    right,down = sim.generate_structured_maze(kind,cols,rows,random.Random(211),n)
    distances = sim.finish_routes(right,down,cols,rows,(rows-1,3),n)
    cells = sim.balanced_spawn_cells(distances,cols,rows,n,211)
    assert len(set(cells)) == n
    assert cells == sim.balanced_spawn_cells(distances,cols,rows,n,211)
    old = [distances[i//cols][i%cols] for i in range(n)]
    new = [distances[r][c] for r,c in cells]
    assert max(new)-min(new) <= max(old)-min(old)

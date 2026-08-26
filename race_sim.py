"""
Fully generated (code-only) maze race — no stock footage, no real photos, no
LLM script. 6-9 square "racer" icons with faces are dropped into a
procedurally generated top-down labyrinth and steer themselves toward the
finish using a baked flood-fill distance field, bumping off walls and each
other under real pymunk physics (no gravity — motion comes from a continuous
steering force toward the next waypoint, plus small per-racer jitter/mistake
chance so identical mazes never play out the same way twice). First racer to
reach the finish zone wins. Video frames, the live "K/N finished" counter,
bump flashes and impact sound effects are all synthesized from the physics
log, so a race is fully reproducible from its `seed`.
"""
import colorsys
import hashlib
import math
import os
import random
from collections import deque

import numpy as np
import pymunk
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Racer roster -----------------------------------------------------
# "weight" is a mild mass/pushiness trait (heavier racers shrug off bumps and
# shove lighter ones around a bit more) and "confusion" is the per-decision
# chance a racer ignores the shortest-path signal and takes a different open
# passage anyway — together they give otherwise-identical maze runs some
# personality without any combat/attack mechanic.
RACER_POOL = [
    {"name": "Blacky", "color": (40, 40, 46), "weight": 1.05, "confusion": 0.08},
    {"name": "Sunny", "color": (250, 205, 45), "weight": 0.92, "confusion": 0.10},
    {"name": "Cocoa", "color": (122, 82, 48), "weight": 1.10, "confusion": 0.07},
    {"name": "Pine", "color": (35, 112, 72), "weight": 1.00, "confusion": 0.09},
    {"name": "Tango", "color": (235, 120, 35), "weight": 0.95, "confusion": 0.12},
    {"name": "Ghost", "color": (218, 218, 224), "weight": 0.88, "confusion": 0.11},
    {"name": "Sky", "color": (55, 140, 225), "weight": 1.00, "confusion": 0.09},
    {"name": "Rosy", "color": (232, 72, 150), "weight": 0.90, "confusion": 0.13},
    {"name": "Cherry", "color": (216, 46, 56), "weight": 1.02, "confusion": 0.08},
    {"name": "Minty", "color": (70, 210, 172), "weight": 0.94, "confusion": 0.10},
    {"name": "Grape", "color": (142, 82, 202), "weight": 0.98, "confusion": 0.11},
    {"name": "Coral", "color": (255, 132, 112), "weight": 0.90, "confusion": 0.14},
    {"name": "Lime", "color": (172, 220, 52), "weight": 0.93, "confusion": 0.12},
    {"name": "Slate", "color": (102, 112, 132), "weight": 1.12, "confusion": 0.06},
    {"name": "Amber", "color": (236, 166, 42), "weight": 0.96, "confusion": 0.10},
    {"name": "Ruby", "color": (190, 32, 72), "weight": 1.08, "confusion": 0.07},
]

# Full 2-8 range (was a narrow 6-9 window) — smaller races are punchier/
# easier to follow, larger ones are more chaotic; weights skew toward the
# middle so most uploads land in the readable 4-6 range with 2/3 and 7/8 as
# real but less frequent variety, mirroring weapon-ball-bot's
# N_FIGHTERS_WEIGHTS skew pattern.
N_RACERS_WEIGHTS = {2: 6, 3: 10, 4: 16, 5: 20, 6: 20, 7: 16, 8: 12}


def _det_jitter(n):
    """Deterministic pseudo-random float in [0, 1) from an integer — cheap
    per-frame shake-direction jitter with no RNG object to thread through."""
    x = math.sin(n * 12.9898) * 43758.5453
    return x - math.floor(x)


def _color_dist(c1, c2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _boost_color_contrast(racers, rng):
    """Nudge any racer's color that's too close to an already-placed one in
    this race so every racer stays visually distinguishable at a glance,
    same idea as weapon-ball's fighter-color spacing pass."""
    used = []
    for r in racers:
        color = r["color"]
        tries = 0
        while any(_color_dist(color, u) < 55 for u in used) and tries < 6:
            h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in color))
            h = (h + 0.15 + tries * 0.06) % 1.0
            s = max(s, 0.45)
            rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
            color = (int(rr * 255), int(gg * 255), int(bb * 255))
            tries += 1
        r["color"] = color
        used.append(color)


# --- Fonts ---------------------------------------------------------------

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONT_CANDIDATES = [
    os.path.join(_FONTS_DIR, "Anton-Regular.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def get_font(size):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# --- Maze generation -------------------------------------------------------

def generate_maze(cols, rows, rng):
    """Randomized DFS (recursive backtracker), iterative to avoid recursion
    limits on tall mazes. Returns two boolean grids: open_right[r][c] (True =
    passage between cell (r,c) and (r,c+1)) and open_down[r][c] (True =
    passage between (r,c) and (r+1,c))."""
    open_right = [[False] * (cols - 1) for _ in range(rows)]
    open_down = [[False] * cols for _ in range(rows - 1)]
    visited = [[False] * cols for _ in range(rows)]
    start = (0, rng.randrange(cols))
    stack = [start]
    visited[start[0]][start[1]] = True
    while stack:
        r, c = stack[-1]
        neighbors = []
        if c > 0 and not visited[r][c - 1]:
            neighbors.append(("L", r, c - 1))
        if c < cols - 1 and not visited[r][c + 1]:
            neighbors.append(("R", r, c + 1))
        if r > 0 and not visited[r - 1][c]:
            neighbors.append(("U", r - 1, c))
        if r < rows - 1 and not visited[r + 1][c]:
            neighbors.append(("D", r + 1, c))
        if not neighbors:
            stack.pop()
            continue
        direction, nr, nc = neighbors[rng.randrange(len(neighbors))]
        visited[nr][nc] = True
        if direction == "L":
            open_right[r][c - 1] = True
        elif direction == "R":
            open_right[r][c] = True
        elif direction == "U":
            open_down[r - 1][c] = True
        else:
            open_down[r][c] = True
        stack.append((nr, nc))
    return open_right, open_down


def add_loops(open_right, open_down, cols, rows, rng, p=0.12):
    """Opens a few extra passages on top of the spanning tree so the maze has
    genuine alternate routes/loops — a single-path maze has no suspense
    about who finds the way first."""
    for r in range(rows):
        for c in range(cols - 1):
            if not open_right[r][c] and rng.random() < p:
                open_right[r][c] = True
    for r in range(rows - 1):
        for c in range(cols):
            if not open_down[r][c] and rng.random() < p:
                open_down[r][c] = True


def carve_rooms(open_right, open_down, cols, rows, rng, room_count=None, min_size=2, max_size=3):
    """Merges a handful of small cell clusters into fully-open 'rooms' on top
    of the corridor maze — real maze-race videos aren't uniformly one-wide
    corridors everywhere, they alternate tight passages with open areas
    where the pack can spread out, jostle, and bump past each other (which
    also gives the racer-vs-racer collision physics actual room to read on
    screen). Mutates open_right/open_down in place; every other function
    that follows (BFS, wall-segment building, drawing, pathfinding) just
    sees a maze with a few extra open passages, no special-casing needed."""
    if room_count is None:
        room_count = max(2, (cols * rows) // 45)
    for _ in range(room_count):
        rw = rng.randint(min_size, max_size)
        rh = rng.randint(min_size, max_size)
        if cols <= rw or rows <= rh:
            continue
        c0 = rng.randint(0, cols - rw - 1) if cols - rw - 1 > 0 else 0
        r0 = rng.randint(0, rows - rh - 1) if rows - rh - 1 > 0 else 0
        for r in range(r0, r0 + rh):
            for c in range(c0, c0 + rw - 1):
                open_right[r][c] = True
        for r in range(r0, r0 + rh - 1):
            for c in range(c0, c0 + rw):
                open_down[r][c] = True


def bfs_distance_field(open_right, open_down, cols, rows, finish_cell):
    dist = [[None] * cols for _ in range(rows)]
    fr, fc = finish_cell
    dist[fr][fc] = 0
    q = deque([finish_cell])
    while q:
        r, c = q.popleft()
        d = dist[r][c]
        if c > 0 and open_right[r][c - 1] and dist[r][c - 1] is None:
            dist[r][c - 1] = d + 1
            q.append((r, c - 1))
        if c < cols - 1 and open_right[r][c] and dist[r][c + 1] is None:
            dist[r][c + 1] = d + 1
            q.append((r, c + 1))
        if r > 0 and open_down[r - 1][c] and dist[r - 1][c] is None:
            dist[r - 1][c] = d + 1
            q.append((r - 1, c))
        if r < rows - 1 and open_down[r][c] and dist[r + 1][c] is None:
            dist[r + 1][c] = d + 1
            q.append((r + 1, c))
    return dist


SPAWN_ROWS = 2  # how many top rows racers can spawn across for larger n_racers


def _maze_symmetric(cols, rows, rng):
    """Independently generates a spanning tree on the LEFT half, mirrors it
    onto the right half, then stitches the two halves together with a
    handful of explicit seam connectors down the middle — provably fully
    connected (each half is its own spanning tree; any single seam
    connector bridges the two), and reads as a genuinely left-right
    symmetric layout rather than just a recolor of the classic maze."""
    half = max(2, cols // 2)
    l_right, l_down = generate_maze(half, rows, rng)
    open_right = [[False] * (cols - 1) for _ in range(rows)]
    open_down = [[False] * cols for _ in range(rows - 1)]
    for r in range(rows):
        for c in range(half - 1):
            open_right[r][c] = l_right[r][c]
            mc = cols - 1 - c
            if mc - 1 >= 0:
                open_right[r][mc - 1] = l_right[r][c]
    for r in range(rows - 1):
        for c in range(half):
            open_down[r][c] = l_down[r][c]
            mc = cols - 1 - c
            if 0 <= mc < cols:
                open_down[r][mc] = l_down[r][c]
    seam_c = half - 1
    if seam_c < cols - 1:
        for r in range(0, rows, max(2, rows // 5)):
            open_right[r][seam_c] = True
    return open_right, open_down


def _bias_spiral(open_right, open_down, cols, rows, rng):
    cx, cy = (cols - 1) / 2.0, (rows - 1) / 2.0
    max_r = math.hypot(cx, cy) or 1.0
    turns = rng.uniform(2.0, 3.0)
    band = 0.07

    def _on_band(x, y):
        dx, dy = x - cx, y - cy
        ang = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
        rad = math.hypot(dx, dy) / max_r
        spiral = (ang + rad * turns) % 1.0
        return min(spiral, 1.0 - spiral) < band

    for r in range(rows):
        for c in range(cols - 1):
            if _on_band(c + 1.0, r + 0.5):
                open_right[r][c] = True
    for r in range(rows - 1):
        for c in range(cols):
            if _on_band(c + 0.5, r + 1.0):
                open_down[r][c] = True


def _bias_radial(open_right, open_down, cols, rows, rng):
    cx, cy = (cols - 1) / 2.0, (rows - 1) / 2.0
    n_spokes = rng.randint(6, 9)
    spoke_offset = rng.uniform(0, math.pi)
    ring_gaps = sorted(rng.uniform(0.25, 0.9) for _ in range(2))
    max_r = math.hypot(cx, cy) or 1.0

    def _near_spoke(x, y):
        ang = math.atan2(y - cy, x - cx) + spoke_offset
        frac = (ang / (2 * math.pi / n_spokes)) % 1.0
        return min(frac, 1.0 - frac) < 0.12

    def _near_ring(x, y):
        rad = math.hypot(x - cx, y - cy) / max_r
        return any(abs(rad - g) < 0.05 for g in ring_gaps)

    for r in range(rows):
        for c in range(cols - 1):
            x, y = c + 1.0, r + 0.5
            if _near_spoke(x, y) or _near_ring(x, y):
                open_right[r][c] = True
    for r in range(rows - 1):
        for c in range(cols):
            x, y = c + 0.5, r + 1.0
            if _near_spoke(x, y) or _near_ring(x, y):
                open_down[r][c] = True


def _bias_double_helix(open_right, open_down, cols, rows, rng):
    amp = cols * 0.28
    period = rows / rng.uniform(2.2, 3.4)
    phase2 = math.pi
    width = 0.85

    def _near(x, r, phase):
        center = cols / 2.0 + amp * math.sin(2 * math.pi * r / period + phase)
        return abs(x - center) < width

    for r in range(rows):
        for c in range(cols - 1):
            x = c + 1.0
            if _near(x, r, 0.0) or _near(x, r, phase2):
                open_right[r][c] = True
    for r in range(rows - 1):
        for c in range(cols):
            x = c + 0.5
            if _near(x, r, 0.0) or _near(x, r, phase2):
                open_down[r][c] = True


def _bias_spine_branches(open_right, open_down, cols, rows, rng):
    spine_c = rng.randrange(cols)
    for r in range(rows - 1):
        open_down[r][spine_c] = True
    r = 0
    while r < rows:
        side = rng.choice([-1, 1])
        length = rng.randint(1, min(3, max(1, cols - 1)))
        c = spine_c
        for _ in range(length):
            nc = c + side
            if not (0 <= nc < cols):
                break
            if side > 0:
                open_right[r][c] = True
            else:
                open_right[r][nc] = True
            c = nc
        r += rng.randint(1, 3)


def _bias_terraces(open_right, open_down, cols, rows, rng):
    for r in range(rows):
        for c in range(cols - 1):
            if rng.random() < 0.65:
                open_right[r][c] = True
    for r in range(rows - 1):
        for c in range(cols):
            if rng.random() < 0.16:
                open_down[r][c] = True


def _bias_scatter_pillars(open_right, open_down, cols, rows, rng):
    for r in range(rows):
        for c in range(cols - 1):
            if rng.random() < 0.80:
                open_right[r][c] = True
    for r in range(rows - 1):
        for c in range(cols):
            if rng.random() < 0.80:
                open_down[r][c] = True


MAZE_STRUCTURE_KINDS = [
    "classic", "sparse_labyrinth", "open_rooms", "spiral", "radial",
    "double_helix", "spine_branches", "terraces", "scatter_pillars", "symmetric",
]


def pick_maze_structure(seed):
    struct_rng = random.Random(hashlib.sha256((str(seed) + "structure").encode()).hexdigest())
    return struct_rng.choice(MAZE_STRUCTURE_KINDS)


def generate_structured_maze(kind, cols, rows, rng, n_racers=6):
    """Returns (open_right, open_down) for the given MAZE_STRUCTURE_KINDS
    entry. Every kind except "symmetric" starts from the same guaranteed-
    connected spanning tree (generate_maze) and OR-merges in a kind-specific
    extra-opening pattern on top — OR-ing can only ever ADD passages, so
    full connectivity from any cell to the finish is preserved by
    construction no matter how aggressive the pattern is. "symmetric" builds
    its own provably-connected grid directly (see _maze_symmetric)."""
    if kind == "symmetric":
        return _maze_symmetric(cols, rows, rng)

    open_right, open_down = generate_maze(cols, rows, rng)
    room_scale = max(0, n_racers - 5)

    if kind == "classic":
        add_loops(open_right, open_down, cols, rows, rng, p=0.12)
        carve_rooms(open_right, open_down, cols, rows, rng,
                    room_count=max(2, (cols * rows) // 45) + room_scale)
    elif kind == "sparse_labyrinth":
        add_loops(open_right, open_down, cols, rows, rng, p=0.02)
    elif kind == "open_rooms":
        add_loops(open_right, open_down, cols, rows, rng, p=0.55)
        carve_rooms(open_right, open_down, cols, rows, rng,
                    room_count=max(4, (cols * rows) // 24) + room_scale, max_size=4)
    elif kind == "spiral":
        _bias_spiral(open_right, open_down, cols, rows, rng)
    elif kind == "radial":
        _bias_radial(open_right, open_down, cols, rows, rng)
    elif kind == "double_helix":
        _bias_double_helix(open_right, open_down, cols, rows, rng)
    elif kind == "spine_branches":
        _bias_spine_branches(open_right, open_down, cols, rows, rng)
        add_loops(open_right, open_down, cols, rows, rng, p=0.05)
    elif kind == "terraces":
        _bias_terraces(open_right, open_down, cols, rows, rng)
    elif kind == "scatter_pillars":
        _bias_scatter_pillars(open_right, open_down, cols, rows, rng)

    if room_scale > 0 and kind not in ("classic", "open_rooms"):
        # Larger races (more racers) get a little extra room-carving on ANY
        # structure so bunching near a chokepoint has somewhere to resolve
        # instead of turning into an unreadable pileup.
        carve_rooms(open_right, open_down, cols, rows, rng, room_count=room_scale)

    return open_right, open_down


def open_neighbors(r, c, open_right, open_down, cols, rows):
    out = []
    if c > 0 and open_right[r][c - 1]:
        out.append((r, c - 1))
    if c < cols - 1 and open_right[r][c]:
        out.append((r, c + 1))
    if r > 0 and open_down[r - 1][c]:
        out.append((r - 1, c))
    if r < rows - 1 and open_down[r][c]:
        out.append((r + 1, c))
    return out


# --- Themes ------------------------------------------------------------
# Purely code-generated (flat floor/wall colors + checkerboard border tint +
# drifting ambient particles), picked from a hash of the race seed.

def _brighten(rgb, val_floor=0.62, val_span=0.30, sat_target=0.42):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    v = min(0.95, val_floor + v * val_span)
    s = min(1.0, max(0.18, sat_target * (0.5 + s)))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


MAZE_THEMES = [
    {"name": "Mint Maze", "floor": (206, 240, 218), "wall": (28, 96, 92), "border_a": (24, 84, 80), "border_b": (206, 240, 218), "particle": (30, 140, 120), "accent": (255, 210, 60)},
    {"name": "Neon Grid", "floor": (24, 14, 40), "wall": (210, 60, 230), "border_a": (40, 20, 60), "border_b": (210, 60, 230), "particle": (255, 90, 220), "accent": (60, 255, 220)},
    {"name": "Candy Corridor", "floor": (255, 232, 240), "wall": (230, 90, 150), "border_a": (255, 210, 225), "border_b": (230, 90, 150), "particle": (255, 150, 190), "accent": (110, 200, 255)},
    {"name": "Ice Labyrinth", "floor": (224, 244, 255), "wall": (80, 160, 210), "border_a": (200, 232, 250), "border_b": (80, 160, 210), "particle": (190, 230, 255), "accent": (255, 210, 90)},
    {"name": "Desert Maze", "floor": (244, 224, 176), "wall": (150, 100, 55), "border_a": (230, 196, 140), "border_b": (150, 100, 55), "particle": (255, 220, 150), "accent": (60, 140, 210)},
    {"name": "Space Station", "floor": (18, 20, 30), "wall": (120, 140, 210), "border_a": (30, 32, 48), "border_b": (120, 140, 210), "particle": (200, 205, 255), "accent": (255, 190, 60)},
    {"name": "Toxic Sewer", "floor": (30, 42, 16), "wall": (150, 230, 40), "border_a": (24, 34, 12), "border_b": (150, 230, 40), "particle": (180, 255, 70), "accent": (255, 120, 60)},
    {"name": "Volcanic Tunnels", "floor": (48, 22, 16), "wall": (230, 100, 40), "border_a": (32, 14, 10), "border_b": (230, 100, 40), "particle": (255, 150, 60), "accent": (255, 230, 120)},
    {"name": "Coral Maze", "floor": (214, 246, 240), "wall": (60, 190, 178), "border_a": (180, 232, 224), "border_b": (60, 190, 178), "particle": (255, 140, 170), "accent": (255, 210, 90)},
    {"name": "Golden Vault", "floor": (60, 46, 16), "wall": (232, 188, 70), "border_a": (40, 30, 10), "border_b": (232, 188, 70), "particle": (255, 224, 140), "accent": (110, 200, 255)},
    {"name": "Storm Circuit", "floor": (206, 214, 226), "wall": (72, 88, 116), "border_a": (170, 182, 200), "border_b": (72, 88, 116), "particle": (220, 230, 255), "accent": (255, 210, 60)},
    {"name": "Cyber Maze", "floor": (10, 30, 20), "wall": (60, 230, 140), "border_a": (14, 40, 26), "border_b": (60, 230, 140), "particle": (110, 255, 180), "accent": (255, 80, 160)},
]


def pick_theme(seed):
    rng = random.Random(hashlib.sha256((str(seed) + "theme").encode()).hexdigest())
    return rng.choice(MAZE_THEMES)


# --- Geometry helper -------------------------------------------------------

class MazeGeometry:
    def __init__(self, w, cols, rows, has_finish=True):
        self.cols, self.rows = cols, rows
        self.border_w = w * 0.045
        self.cell = (w - 2 * self.border_w) / cols
        self.wall_thickness = self.cell * 0.30
        self.racer_radius = (self.cell - self.wall_thickness) * 0.30
        self.top_border = self.border_w
        self.has_finish = has_finish
        self.finish_depth = self.cell * 1.3 if has_finish else 0
        self.bottom_border = self.border_w
        self.w = w
        self.img_h = self.top_border + rows * self.cell + self.finish_depth + self.bottom_border

    def cell_left(self, c):
        return self.border_w + c * self.cell

    def cell_top(self, r):
        return self.top_border + r * self.cell

    def cell_center(self, r, c):
        return (self.cell_left(c) + self.cell / 2, self.cell_top(r) + self.cell / 2)

    def finish_zone_center(self, finish_col):
        x = self.cell_left(finish_col) + self.cell / 2
        y = self.top_border + self.rows * self.cell + self.finish_depth / 2
        return (x, y)


def build_wall_segments(geo, open_right, open_down, finish_col):
    """finish_col=None (battle mode's closed arena, no finish zone) closes the
    bottom off like a normal wall instead of leaving a finish-zone gap."""
    cols, rows, cell = geo.cols, geo.rows, geo.cell
    left = geo.border_w
    right = geo.w - geo.border_w
    top = geo.top_border
    bottom = geo.top_border + rows * cell
    zone_bottom = bottom + geo.finish_depth

    segments = [((left, top), (right, top))]

    if finish_col is not None:
        finish_x0 = geo.cell_left(finish_col)
        finish_x1 = finish_x0 + cell
        if finish_x0 > left:
            segments.append(((left, bottom), (finish_x0, bottom)))
        if finish_x1 < right:
            segments.append(((finish_x1, bottom), (right, bottom)))
        segments.append(((left, bottom), (left, zone_bottom)))
        segments.append(((right, bottom), (right, zone_bottom)))
        segments.append(((left, zone_bottom), (right, zone_bottom)))
    else:
        segments.append(((left, bottom), (right, bottom)))

    segments.append(((left, top), (left, bottom)))
    segments.append(((right, top), (right, bottom)))

    for r in range(rows):
        for c in range(cols - 1):
            if not open_right[r][c]:
                x = geo.cell_left(c + 1)
                segments.append(((x, geo.cell_top(r)), (x, geo.cell_top(r) + cell)))
    for r in range(rows - 1):
        for c in range(cols):
            if not open_down[r][c]:
                y = geo.cell_top(r + 1)
                segments.append(((geo.cell_left(c), y), (geo.cell_left(c) + cell, y)))

    return segments


def draw_maze_background(geo, open_right, open_down, finish_col, theme):
    w, h = int(geo.w), int(math.ceil(geo.img_h))
    # Flat solid floor fill — reference "board game" look (flat pastel floor,
    # chunky flat-color walls, no gradients/texture) reads cleaner and more
    # legible in a muted autoplay feed than a textured/shaded floor did.
    img = Image.new("RGBA", (w, h), (*theme["floor"], 255))
    d = ImageDraw.Draw(img, "RGBA")

    left = geo.border_w
    right = geo.w - geo.border_w
    top = geo.top_border
    bottom = geo.top_border + geo.rows * geo.cell
    zone_bottom = bottom + geo.finish_depth

    # checkerboard border frame (left/right run full height, top/bottom cap it)
    tile = geo.border_w
    for region in [(0, 0, left, h), (right, 0, w, h), (left, 0, right, top), (left, zone_bottom, right, h)]:
        rx0, ry0, rx1, ry1 = region
        yy = ry0
        row_i = 0
        while yy < ry1:
            xx = rx0
            col_i = 0
            while xx < rx1:
                color = theme["border_a"] if (row_i + col_i) % 2 == 0 else theme["border_b"]
                d.rectangle([xx, yy, min(xx + tile, rx1), min(yy + tile, ry1)], fill=(*color, 255))
                xx += tile
                col_i += 1
            yy += tile
            row_i += 1

    if finish_col is not None:
        # finish zone: green pad + checker stripe
        d.rectangle([left, bottom, right, zone_bottom], fill=(60, 180, 90, 255))
        stripe_h = geo.finish_depth * 0.30
        stripe_y = bottom + geo.finish_depth * 0.30
        tile2 = geo.cell / 6
        xx = left
        col_i = 0
        while xx < right:
            color = (250, 250, 250) if col_i % 2 == 0 else (30, 30, 34)
            d.rectangle([xx, stripe_y, min(xx + tile2, right), stripe_y + stripe_h], fill=(*color, 255))
            xx += tile2
            col_i += 1
        fin_font = get_font(int(geo.cell * 0.32))
        ftext = "FINISH"
        ftw = d.textlength(ftext, font=fin_font)
        d.text((left + (right - left) / 2 - ftw / 2, bottom + geo.finish_depth * 0.66), ftext,
               font=fin_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

        # start stripe
        start_font = get_font(int(geo.cell * 0.26))
        stext = "START"
        stw = d.textlength(stext, font=start_font)
        d.rectangle([left, top - geo.border_w * 0.55, right, top], fill=(*theme["accent"], 90))
        d.text((left + (right - left) / 2 - stw / 2, top - geo.border_w * 0.5), stext,
               font=start_font, fill=(20, 20, 24, 255))

    # Walls drawn as flat filled rectangles (axis-aligned, since every
    # segment from build_wall_segments is purely horizontal or vertical),
    # each extended half a thickness past its own endpoints so adjoining
    # segments' rectangles overlap and self-fill the corner between them —
    # gives the reference's crisp square-block wall look with no separate
    # corner-patching step, instead of the old centered-line-plus-round-cap
    # "tube" rendering.
    wt = geo.wall_thickness
    wall_color = theme["wall"]
    for (p1, p2) in build_wall_segments(geo, open_right, open_down, finish_col):
        x0, y0 = p1
        x1, y1 = p2
        if y0 == y1:
            d.rectangle([min(x0, x1) - wt / 2, y0 - wt / 2, max(x0, x1) + wt / 2, y0 + wt / 2],
                        fill=(*wall_color, 255))
        else:
            d.rectangle([x0 - wt / 2, min(y0, y1) - wt / 2, x0 + wt / 2, max(y0, y1) + wt / 2],
                        fill=(*wall_color, 255))

    return img


def _make_ambient_particles(seed, count, w, h):
    rng = random.Random(hashlib.sha256((str(seed) + "ambient").encode()).hexdigest())
    particles = []
    for _ in range(count):
        depth = rng.random()
        particles.append({
            "x": rng.uniform(0, w), "y": rng.uniform(0, h),
            "r": 1.5 + depth * 3.5, "phase": rng.uniform(0, 6.28318),
        })
    return particles


# --- Racer icon ------------------------------------------------------------

def _star_points(cx, cy, r_outer, r_inner, points=5, rotation=-90):
    """Vertex list for a regular N-point star, used for both the standalone
    weapon pickup icon and the smaller 'armed' badge — one shape, two sizes,
    so a battle-mode racer's weapon state reads instantly without borrowing
    any specific weapon silhouette (knife/shield/etc.) from a reference."""
    pts = []
    for i in range(points * 2):
        ang = math.radians(rotation + i * 180 / points)
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _make_weapon_icon(size=48, color=(255, 200, 40)):
    """Standalone weapon-pickup icon for battle mode: a flat gold star with
    a dark outline, matching make_racer_icon's flat-cel-shaded construction
    (solid fill + bold outline, no gradients) so it reads as part of the
    same visual system as the racers and maze."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    dark = tuple(max(0, c - 90) for c in color)
    cx = cy = size / 2
    d.polygon(_star_points(cx, cy, size * 0.46, size * 0.19), fill=(*color, 255),
              outline=(*dark, 255), width=max(2, int(size * 0.06)))
    return img


def make_racer_icon(color, size=90, armed=False):
    """A small flat-shaded rounded square with a bold Geometry-Dash-cube-
    style face (thick angled brows + plain dot eyes, no sheen/direction
    nub) — mirrors the reference mascot the user pointed to: one solid
    flat body color, a bold dark outline, and the brows/eyes alone reading
    as 'front' once the icon is rotated per-frame to face travel direction.
    `armed` (battle mode) adds a small star badge at the top-right corner so
    a racer's weapon state is readable at a glance without extra HUD text."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    cx = size / 2
    pad = size * 0.14
    body_top, body_bottom = pad * 1.4, size - pad
    body_left, body_right = pad, size - pad

    # drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([body_left, body_top, body_right, body_bottom], radius=size * 0.16, fill=(0, 0, 0, 130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.03))
    img.alpha_composite(Image.new("RGBA", (size, size), (0, 0, 0, 0)))
    img.paste(shadow, (int(size * 0.05), int(size * 0.06)), shadow)

    dark = tuple(max(0, c - 55) for c in color)

    d.rounded_rectangle([body_left, body_top, body_right, body_bottom], radius=size * 0.16, fill=(*color, 255),
                         outline=(*dark, 255), width=max(3, int(size * 0.05)))

    face_dark = (30, 26, 20, 255)
    eye_y = body_top + (body_bottom - body_top) * 0.42
    brow_w = max(2, int(size * 0.045))
    for dx in (-0.16, 0.16):
        ex = cx + size * dx
        side = 1 if dx > 0 else -1
        # thick angled brow, slanting down toward the center for a focused/
        # determined look instead of the old single arched unibrow
        d.line([(ex - side * size * 0.09, eye_y - size * 0.16), (ex + side * size * 0.07, eye_y - size * 0.08)],
               fill=face_dark, width=brow_w)
        d.ellipse([ex - size * 0.06, eye_y - size * 0.06, ex + size * 0.06, eye_y + size * 0.06], fill=face_dark)
    # small closed mouth line instead of a curved smile
    mouth_y = body_top + (body_bottom - body_top) * 0.68
    d.line([(cx - size * 0.08, mouth_y), (cx + size * 0.08, mouth_y)], fill=face_dark, width=max(2, int(size * 0.03)))

    if armed:
        bx, by = body_right - size * 0.08, body_top + size * 0.08
        d.polygon(_star_points(bx, by, size * 0.15, size * 0.06), fill=(255, 200, 40, 255),
                   outline=(90, 60, 0, 255), width=max(1, int(size * 0.02)))
    return img


# --- Physics simulation ---------------------------------------------------

PHYSICS_HZ = 120
INTRO_SECONDS = 2.0
# A quick punched-in, flash-cut freeze on a racer closing in on the finish
# line — prepended before the countdown even starts, same idea as weapon-
# ball-bot's COLD_OPEN_SECONDS. Deliberately shows no "FINISHED!"/winner
# text (see build_cold_open_clip's src-frame choice) so it teases the
# payoff without spoiling who wins — a first-impression hook for a viewer
# scrolling past in a muted autoplay feed.
COLD_OPEN_SECONDS = 0.8
COLS = 6
ROWS = 26
# Target on-screen corridor cell size in pixels, used to pick a column count
# that fits the requested video width — this is what lets simulate_race
# adapt to any aspect ratio (portrait Shorts vs. landscape Tournament video)
# instead of always carving the same fixed 6-wide maze into a wider frame.
TARGET_CELL_PX = 165

WALL_TYPE = 0
RACER_TYPE_BASE = 10
FINISH_TYPE = 500


def simulate_race(w, h, seed, fps=24, max_seconds=28, min_seconds=13, n_racers=None,
                   cols=None, rows=None, forced_racers=None, required_finishers=1):
    rng = random.Random(seed)
    theme = pick_theme(seed)

    if forced_racers is not None:
        racers = [dict(r) for r in forced_racers]
        n_racers = len(racers)
    else:
        if n_racers is None:
            options = list(N_RACERS_WEIGHTS.keys())
            weights = list(N_RACERS_WEIGHTS.values())
            n_racers = rng.choices(options, weights=weights, k=1)[0]
        racers = [dict(r) for r in rng.sample(RACER_POOL, n_racers)]
    _boost_color_contrast(racers, rng)

    border_w_est = w * 0.045
    cols = cols if cols is not None else max(4, round((w - 2 * border_w_est) / TARGET_CELL_PX))
    # Slightly shorter maze for a small pack (quicker to watch, less empty
    # travel time with few racers on screen), slightly taller for a big pack
    # (more room to spread out before things get chaotic near the finish).
    rows = rows if rows is not None else max(16, min(34, ROWS + (n_racers - 6) * 2))

    geo = MazeGeometry(w, cols, rows)
    maze_rng = random.Random(hashlib.sha256((str(seed) + "maze").encode()).hexdigest())
    structure_kind = pick_maze_structure(seed)
    open_right, open_down = generate_structured_maze(structure_kind, cols, rows, maze_rng, n_racers)
    finish_col = maze_rng.randrange(cols)
    finish_cell = (rows - 1, finish_col)
    dist_field = bfs_distance_field(open_right, open_down, cols, rows, finish_cell)
    maze_img = draw_maze_background(geo, open_right, open_down, finish_col, theme)

    space = pymunk.Space()
    space.gravity = (0, 0)
    space.damping = 0.996

    for (p1, p2) in build_wall_segments(geo, open_right, open_down, finish_col):
        seg = pymunk.Segment(space.static_body, p1, p2, geo.wall_thickness / 2)
        seg.elasticity = 0.35
        seg.friction = 0.5
        seg.collision_type = WALL_TYPE
        space.add(seg)

    fzx, fzy = geo.finish_zone_center(finish_col)
    finish_shape = pymunk.Circle(space.static_body, geo.cell * 0.55, offset=(fzx, fzy))
    finish_shape.sensor = True
    finish_shape.collision_type = FINISH_TYPE
    space.add(finish_shape)

    bodies, shapes = [], []
    for i in range(n_racers):
        start_r, start_c = i // cols, i % cols
        cx, cy = geo.cell_center(start_r, start_c)
        jx, jy = rng.uniform(-6, 6), rng.uniform(-6, 6)
        mass = racers[i]["weight"]
        body = pymunk.Body(mass=mass, moment=pymunk.moment_for_circle(mass, 0, geo.racer_radius))
        body.position = (cx + jx, cy + jy)
        shape = pymunk.Circle(body, geo.racer_radius)
        shape.elasticity = 0.5
        shape.friction = 0.35
        shape.collision_type = RACER_TYPE_BASE + i
        space.add(body, shape)
        bodies.append(body)
        shapes.append(shape)

    finished = [False] * n_racers
    active = [True] * n_racers  # mirrors weapon-ball's "alive" flag naming for rendering
    last_cell = [(i // cols, i % cols) for i in range(n_racers)]
    target = [geo.cell_center(*last_cell[i]) for i in range(n_racers)]
    winner_idx = [None]
    # populated below once _recompute_target exists — a racer's initial
    # target must be the NEXT waypoint toward the finish, not its own start
    # cell center (leaving it as the start cell makes the desired velocity
    # ~zero and the racer never actually sets off).
    finish_log = []  # (step, racer_idx, x, y)
    bump_log = []  # (step, x, y, intensity, kind)  kind in {"wall","racer"}
    step_counter = {"n": 0}
    per_racer_rng = [random.Random(hashlib.sha256((str(seed) + f"racer{i}").encode()).hexdigest()) for i in range(n_racers)]

    # Post-bump "recovery" window: right after a racer-vs-racer collision,
    # the flood-fill steering force is dialed way down for a short stretch
    # so the elastic bounce itself is what moves the racer on screen (full
    # instant steering would cancel the bounce out immediately and the
    # collision would read as nothing happening), then ramps back to full
    # strength. recovery_until[i] is the physics step at which racer i's
    # steering is back to 100%.
    RECOVERY_STEPS = int(0.30 * PHYSICS_HZ)
    RECOVERY_MIN_STEER_MULT = 0.12
    recovery_until = [0] * n_racers

    # Stuck-detection: a racer occasionally gets wedged in a dead-end/corner
    # (especially now that racer-racer bounces are more violent) and can
    # bounce in place indefinitely without the steering force ever winning.
    # Every STUCK_CHECK_STEPS, compare against where it was at the previous
    # check; too little net displacement for STUCK_LIMIT consecutive checks
    # triggers a one-off unstick impulse toward its current waypoint.
    STUCK_CHECK_STEPS = int(0.5 * PHYSICS_HZ)
    STUCK_LIMIT = 3
    stuck_dist_threshold = geo.racer_radius * 0.7
    stuck_check_pos = [None] * n_racers
    stuck_counters = [0] * n_racers

    def _recompute_target(i):
        """Returns True when this call landed on a real fork (more than one
        open neighbor) — the caller uses that to trigger a brief steering
        hesitation, so a racer visibly 'thinks' for an instant at a genuine
        decision point instead of snapping onto its new line immediately."""
        r, c = last_cell[i]
        if (r, c) == finish_cell:
            target[i] = (fzx, fzy)
            return False
        candidates = open_neighbors(r, c, open_right, open_down, cols, rows)
        if not candidates:
            return False
        best = min(dist_field[nr][nc] for (nr, nc) in candidates)
        best_candidates = [n for n in candidates if dist_field[n[0]][n[1]] == best]
        prng = per_racer_rng[i]
        if len(candidates) > 1 and prng.random() < racers[i]["confusion"]:
            choice = candidates[prng.randrange(len(candidates))]
        else:
            choice = best_candidates[prng.randrange(len(best_candidates))]
        target[i] = geo.cell_center(*choice)
        return len(candidates) > 1

    def on_begin(arbiter, space_, data):
        ct1, ct2 = arbiter.shapes[0].collision_type, arbiter.shapes[1].collision_type
        if FINISH_TYPE in (ct1, ct2):
            other = ct2 if ct1 == FINISH_TYPE else ct1
            idx = other - RACER_TYPE_BASE
            if 0 <= idx < n_racers and not finished[idx]:
                finished[idx] = True
                active[idx] = False
                finish_log.append((step_counter["n"], idx, bodies[idx].position.x, bodies[idx].position.y))
                if winner_idx[0] is None:
                    winner_idx[0] = idx
        return True

    # Racer-vs-racer restitution is forced explicitly here (rather than left
    # to shape.elasticity's default combine, which is a soft ~0.5x0.5 mix)
    # so two racers colliding always carom off each other like glass
    # marbles/billiard balls — a real, visible bounce/redirect — regardless
    # of each racer's own material elasticity. Wall bounces are untouched
    # (left at whatever the shapes' own elasticity combine already gives).
    RACER_VS_RACER_ELASTICITY = 0.92

    def on_pre_solve(arbiter, space_, data):
        ct1, ct2 = arbiter.shapes[0].collision_type, arbiter.shapes[1].collision_type
        if ct1 >= RACER_TYPE_BASE and ct2 >= RACER_TYPE_BASE:
            arbiter.elasticity = RACER_VS_RACER_ELASTICITY
        return True

    def on_post_solve(arbiter, space_, data):
        ct1, ct2 = arbiter.shapes[0].collision_type, arbiter.shapes[1].collision_type
        impulse = arbiter.total_impulse.length
        if impulse < 0.5:
            return
        cps = arbiter.contact_point_set.points
        if not cps:
            return
        cx_, cy_ = cps[0].point_a.x, cps[0].point_a.y
        intensity = min(1.0, impulse / 400.0)
        if ct1 == WALL_TYPE or ct2 == WALL_TYPE:
            if len(bump_log) < 4000:
                bump_log.append((step_counter["n"], cx_, cy_, intensity, "wall"))
        elif ct1 >= RACER_TYPE_BASE and ct2 >= RACER_TYPE_BASE:
            if len(bump_log) < 4000:
                bump_log.append((step_counter["n"], cx_, cy_, intensity, "racer"))
            # A real collision (not just a graze) opens a brief recovery
            # window on BOTH racers involved — see RECOVERY_STEPS above for
            # why: without this the steering force cancels the bounce out
            # before it's ever visible on screen.
            if impulse > 15.0:
                i1, i2 = ct1 - RACER_TYPE_BASE, ct2 - RACER_TYPE_BASE
                until = step_counter["n"] + RECOVERY_STEPS
                if 0 <= i1 < n_racers:
                    recovery_until[i1] = max(recovery_until[i1], until)
                if 0 <= i2 < n_racers:
                    recovery_until[i2] = max(recovery_until[i2], until)

    space.on_collision(begin=on_begin, pre_solve=on_pre_solve, post_solve=on_post_solve)

    for i in range(n_racers):
        _recompute_target(i)

    dt = 1.0 / PHYSICS_HZ
    steps_per_frame = max(1, PHYSICS_HZ // fps)
    max_steps = int(max_seconds * PHYSICS_HZ)
    min_steps = int(min_seconds * PHYSICS_HZ)

    MAX_SPEED = geo.cell / 0.42
    STEER_GAIN = 7.5
    SLOWDOWN_RADIUS = geo.cell * 0.55
    JITTER_HZ_SCALE = 3.0

    # Per-racer handling texture from the roster's "weight" stat (0.88-1.12):
    # a lighter racer tops out faster but turns/redirects a touch more
    # eagerly (twitchier), a heavier one is a bit slower outright but holds
    # its line more (already shoves harder / gets shoved less via its real
    # pymunk mass in collisions) — without this every racer had IDENTICAL
    # top speed and steering response and "weight" only affected collision
    # physics, which read as one script with a random-detour dice roll
    # rather than genuinely independent racers.
    speed_mult = [1.0 + (1.0 - racers[i]["weight"]) * 0.6 for i in range(n_racers)]
    steer_mult = [1.0 - (racers[i]["weight"] - 1.0) * 0.5 for i in range(n_racers)]

    # Junction hesitation: reuses the same steering-dampening ramp as the
    # post-bump recovery window (recovery_until/RECOVERY_STEPS), just
    # triggered by a genuine fork-in-the-road decision instead of a
    # collision, and for a shorter stretch (JUNCTION_HESITATE_STEPS <
    # RECOVERY_STEPS means the ramp starts already partway recovered — a
    # brief waver, not a full stop) — a racer visibly "thinks" for an
    # instant at a real junction instead of snapping onto its new line
    # immediately, which is what made movement read as scripted.
    JUNCTION_HESITATE_STEPS = int(0.15 * PHYSICS_HZ)

    frames = []
    finish_frame_flags = {}  # frame_idx -> [(racer_idx, x, y), ...]
    bump_frame_flags = {}  # frame_idx -> (x, y, intensity, kind)
    frame_idx = 0

    while step_counter["n"] < max_steps:
        step_counter["n"] += 1
        t_now = step_counter["n"] * dt

        for i in range(n_racers):
            if not active[i]:
                continue
            x, y = bodies[i].position
            c = min(cols - 1, max(0, int((x - geo.border_w) / geo.cell)))
            r = min(rows - 1, max(0, int((y - geo.top_border) / geo.cell)))
            r = min(r, rows - 1)
            if (r, c) != last_cell[i] and y < geo.top_border + rows * geo.cell:
                last_cell[i] = (r, c)
                if _recompute_target(i):
                    until = step_counter["n"] + JUNCTION_HESITATE_STEPS
                    recovery_until[i] = max(recovery_until[i], until)
            elif last_cell[i] == finish_cell:
                target[i] = (fzx, fzy)

            tx, ty = target[i]
            dx, dy = tx - x, ty - y
            dist = math.hypot(dx, dy) or 1.0
            speed_scale = min(1.0, max(0.35, dist / SLOWDOWN_RADIUS))
            desired_vx = dx / dist * MAX_SPEED * speed_mult[i] * speed_scale
            desired_vy = dy / dist * MAX_SPEED * speed_mult[i] * speed_scale
            vx, vy = bodies[i].velocity
            steer_gain = STEER_GAIN * steer_mult[i]
            if step_counter["n"] < recovery_until[i]:
                # Ramp from RECOVERY_MIN_STEER_MULT back up to full strength
                # over the recovery window instead of snapping instantly, so
                # the bounce fades out of a racer's motion smoothly rather
                # than the steering force reasserting itself as a jolt.
                remaining = (recovery_until[i] - step_counter["n"]) / RECOVERY_STEPS
                steer_gain *= RECOVERY_MIN_STEER_MULT + (1 - RECOVERY_MIN_STEER_MULT) * (1 - remaining)
            steer_x = (desired_vx - vx) * steer_gain
            steer_y = (desired_vy - vy) * steer_gain
            mass = racers[i]["weight"]
            jr = per_racer_rng[i]
            jitter_ang = math.sin(t_now * JITTER_HZ_SCALE + i * 1.7) * jr.uniform(0.5, 1.0)
            jitter_mag = mass * 60
            fx = mass * steer_x + math.cos(jitter_ang) * jitter_mag
            fy = mass * steer_y + math.sin(jitter_ang) * jitter_mag
            bodies[i].apply_force_at_world_point((fx, fy), bodies[i].position)

        space.step(dt)

        if step_counter["n"] % STUCK_CHECK_STEPS == 0:
            for i in range(n_racers):
                if not active[i]:
                    continue
                pos_now = bodies[i].position
                prev = stuck_check_pos[i]
                stuck_check_pos[i] = (pos_now.x, pos_now.y)
                if prev is None:
                    continue
                moved = math.hypot(pos_now.x - prev[0], pos_now.y - prev[1])
                if moved < stuck_dist_threshold:
                    stuck_counters[i] += 1
                else:
                    stuck_counters[i] = 0
                if stuck_counters[i] >= STUCK_LIMIT:
                    tx, ty = target[i]
                    ddx, ddy = tx - pos_now.x, ty - pos_now.y
                    ddist = math.hypot(ddx, ddy) or 1.0
                    nudge = MAX_SPEED * racers[i]["weight"] * 1.4
                    bodies[i].apply_impulse_at_world_point(
                        (ddx / ddist * nudge, ddy / ddist * nudge), pos_now)
                    recovery_until[i] = 0  # let steering re-engage immediately, not fight the nudge
                    stuck_counters[i] = 0

        if step_counter["n"] % steps_per_frame == 0:
            pos = []
            for i in range(n_racers):
                if active[i]:
                    b = bodies[i]
                    vx, vy = b.velocity
                    ang = math.degrees(math.atan2(vy, vx)) + 90 if (vx or vy) else 0.0
                    pos.append((b.position.x, b.position.y, ang))
                else:
                    pos.append(None)
            n_finished_so_far = sum(1 for f in finished if f)
            frames.append({"pos": pos, "active": list(active), "n_finished": n_finished_so_far})
            frame_idx += 1

            if finish_log and finish_log[-1][0] > step_counter["n"] - steps_per_frame:
                events = [(fl[1], fl[2], fl[3]) for fl in finish_log if fl[0] > step_counter["n"] - steps_per_frame]
                if events:
                    finish_frame_flags[frame_idx - 1] = events

            recent_bumps = [b for b in bump_log if b[0] > step_counter["n"] - steps_per_frame]
            if recent_bumps:
                best = max(recent_bumps, key=lambda b: b[3])
                bump_frame_flags[frame_idx - 1] = (best[1], best[2], best[3], best[4])

            for i, b in enumerate(bodies):
                if finished[i] and shapes[i] in space.shapes:
                    try:
                        space.remove(bodies[i], shapes[i])
                    except Exception:
                        pass

            if len(finish_log) >= required_finishers and step_counter["n"] >= min_steps:
                break

    def _progress(i):
        r, c = last_cell[i]
        return dist_field[r][c] if dist_field[r][c] is not None else 999999

    finished_order_list = [fl[1] for fl in finish_log]
    remaining = sorted((i for i in range(n_racers) if i not in finished_order_list), key=_progress)
    full_ranking = finished_order_list + remaining
    if winner_idx[0] is None and full_ranking:
        winner_idx[0] = full_ranking[0]

    finale_frames = int(1.6 * fps)
    if frames:
        last = dict(frames[-1])
        last["pos"] = list(last["pos"])
        for _ in range(finale_frames):
            frames.append(dict(last))

    return {
        "frames": frames,
        "finish_frame_flags": finish_frame_flags,
        "bump_frame_flags": bump_frame_flags,
        "racers": racers,
        "n_racers": n_racers,
        "winner_idx": winner_idx[0],
        "winner_name": racers[winner_idx[0]]["name"],
        "finish_order": finished_order_list,
        "n_finished_total": len(finish_log),
        "full_ranking": full_ranking,
        "fps": fps,
        "w": w,
        "h": h,
        "geo": geo,
        "maze_img": maze_img,
        "theme": theme,
        "finish_col": finish_col,
        "finish_zone": (fzx, fzy),
        "finale_start": len(frames) - finale_frames,
        "seed": seed,
    }


# --- Battle mode: shrinking-zone elimination arena --------------------------

BATTLE_KNOCKBACK_IMPULSE = 950.0  # throw strength when a weapon lands a hit
BATTLE_WALL_KILL_IMPULSE = 260.0  # impact strength vs a wall, while airborne, that's fatal
BATTLE_FLYING_SECONDS = 0.5  # window after being thrown during which a hard wall hit eliminates
BATTLE_ZONE_SHRINK_START_FRAC = 0.15  # of max_seconds: the closing walls start moving
BATTLE_ZONE_SHRINK_END_FRAC = 0.85  # walls reach their final (minimum) position
BATTLE_ZONE_MIN_HALF_WIDTH_CELLS = 1.5  # how narrow the left/right walls can close to
BATTLE_ZONE_END_MARGIN_ROWS = 2  # rows of headroom always left above the finish


def _place_pickups(open_right, open_down, cols, rows, rng, k):
    """Scatter k weapon pickups on junction/room cells (>=2 open neighbors,
    so they sit somewhere reachable from more than one direction), spread
    apart via a greedy min-separation pick instead of pure random placement
    so they don't cluster in one corner of the arena."""
    candidates = [(r, c) for r in range(rows) for c in range(cols)
                  if len(open_neighbors(r, c, open_right, open_down, cols, rows)) >= 2]
    rng.shuffle(candidates)
    min_sep = max(2, (cols + rows) // 6)
    chosen = []
    for (r, c) in candidates:
        if all(abs(r - cr) + abs(c - cc) >= min_sep for (cr, cc) in chosen):
            chosen.append((r, c))
            if len(chosen) >= k:
                break
    if len(chosen) < k:
        for cell in candidates:
            if cell not in chosen:
                chosen.append(cell)
                if len(chosen) >= k:
                    break
    return chosen


def simulate_battle(w, h, seed, fps=24, max_seconds=32, min_seconds=14, n_racers=None,
                     cols=None, rows=None, forced_racers=None):
    """Same procedural maze/physics/racer-icon system as simulate_race, and a
    race-to-finish objective still at its heart, but under mounting pressure
    from a closing arena: three kinematic 'zone' walls (top, left, right)
    physically sweep inward over the match — a racer literally can't cross
    one, and gets carried/squeezed along by it if caught against it — while
    the bottom stays open onto the same finish zone simulate_race uses, so
    the closing walls funnel everyone toward it instead of just shrinking to
    a static center. Weapon pickups let an armed racer THROW an unarmed one
    on collision (a strong knockback impulse, not a damage tick); slamming
    into any wall while still airborne from a throw is what actually
    eliminates a racer. First to the finish wins outright; if nobody makes
    it, the last racer standing (or closest to the finish, on a time-out)
    does."""
    rng = random.Random(seed)
    theme = pick_theme(seed)

    if forced_racers is not None:
        racers = [dict(r) for r in forced_racers]
        n_racers = len(racers)
    else:
        if n_racers is None:
            options = list(N_RACERS_WEIGHTS.keys())
            weights = list(N_RACERS_WEIGHTS.values())
            n_racers = rng.choices(options, weights=weights, k=1)[0]
        racers = [dict(r) for r in rng.sample(RACER_POOL, n_racers)]
    _boost_color_contrast(racers, rng)

    border_w_est = w * 0.045
    cols = cols if cols is not None else max(4, round((w - 2 * border_w_est) / TARGET_CELL_PX))
    rows = rows if rows is not None else max(14, min(24, 18 + (n_racers - 6)))

    geo = MazeGeometry(w, cols, rows, has_finish=True)
    maze_rng = random.Random(hashlib.sha256((str(seed) + "maze").encode()).hexdigest())
    structure_kind = pick_maze_structure(seed)
    open_right, open_down = generate_structured_maze(structure_kind, cols, rows, maze_rng, n_racers)
    finish_col = maze_rng.randrange(cols)
    finish_cell = (rows - 1, finish_col)
    dist_field = bfs_distance_field(open_right, open_down, cols, rows, finish_cell)
    maze_img = draw_maze_background(geo, open_right, open_down, finish_col, theme)

    left, right = geo.border_w, geo.w - geo.border_w
    top, bottom = geo.top_border, geo.top_border + rows * geo.cell
    zone_cx, zone_cy = (left + right) / 2, (top + bottom) / 2

    shrink_start = BATTLE_ZONE_SHRINK_START_FRAC * max_seconds
    shrink_end = BATTLE_ZONE_SHRINK_END_FRAC * max_seconds
    shrink_dur = max(0.001, shrink_end - shrink_start)
    top_end_y = bottom - geo.cell * BATTLE_ZONE_END_MARGIN_ROWS
    half_w_start = (right - left) / 2
    half_w_end = geo.cell * BATTLE_ZONE_MIN_HALF_WIDTH_CELLS

    def _zone_state(t_now):
        """Returns (top_y, left_x, right_x, vy, vx) for the three closing
        walls at time t_now — position AND an analytic constant velocity,
        so a racer caught against a wall is carried along by it (pymunk's
        kinematic-vs-dynamic contact resolution uses the kinematic body's
        velocity, not just its position delta)."""
        frac = min(1.0, max(0.0, (t_now - shrink_start) / shrink_dur))
        top_y = top + frac * (top_end_y - top)
        half_w = half_w_start + frac * (half_w_end - half_w_start)
        moving = shrink_start <= t_now <= shrink_end
        vy = (top_end_y - top) / shrink_dur if moving else 0.0
        vx = (half_w_end - half_w_start) / shrink_dur if moving else 0.0
        return top_y, zone_cx - half_w, zone_cx + half_w, vy, vx

    n_pickups = max(2, n_racers // 2)
    pickup_cells = _place_pickups(open_right, open_down, cols, rows, maze_rng, n_pickups)
    pickup_pos = [geo.cell_center(r, c) for (r, c) in pickup_cells]
    pickup_collected = [False] * n_pickups
    pickup_collect_step = [None] * n_pickups
    PICKUP_RADIUS = geo.racer_radius * 1.3

    space = pymunk.Space()
    space.gravity = (0, 0)
    space.damping = 0.996

    for (p1, p2) in build_wall_segments(geo, open_right, open_down, finish_col):
        seg = pymunk.Segment(space.static_body, p1, p2, geo.wall_thickness / 2)
        seg.elasticity = 0.35
        seg.friction = 0.5
        seg.collision_type = WALL_TYPE
        space.add(seg)

    fzx, fzy = geo.finish_zone_center(finish_col)
    finish_shape = pymunk.Circle(space.static_body, geo.cell * 0.55, offset=(fzx, fzy))
    finish_shape.sensor = True
    finish_shape.collision_type = FINISH_TYPE
    space.add(finish_shape)

    # Closing zone walls: three kinematic bodies (top, left, right — bottom
    # stays open onto the finish). collision_type=WALL_TYPE so they get the
    # same bump SFX/flash and the same "flying into a wall" elimination
    # check as the maze's own static walls.
    zone_span = max(right - left, bottom - top) * 1.2
    top_wall_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    top_wall_shape = pymunk.Segment(top_wall_body, (-zone_span / 2, 0), (zone_span / 2, 0), geo.wall_thickness / 2)
    top_wall_shape.elasticity = 0.35
    top_wall_shape.friction = 0.5
    top_wall_shape.collision_type = WALL_TYPE
    top_wall_body.position = (zone_cx, top)
    space.add(top_wall_body, top_wall_shape)

    left_wall_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    left_wall_shape = pymunk.Segment(left_wall_body, (0, -(bottom - top) / 2), (0, (bottom - top) / 2),
                                      geo.wall_thickness / 2)
    left_wall_shape.elasticity = 0.35
    left_wall_shape.friction = 0.5
    left_wall_shape.collision_type = WALL_TYPE
    left_wall_body.position = (left, zone_cy)
    space.add(left_wall_body, left_wall_shape)

    right_wall_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    right_wall_shape = pymunk.Segment(right_wall_body, (0, -(bottom - top) / 2), (0, (bottom - top) / 2),
                                       geo.wall_thickness / 2)
    right_wall_shape.elasticity = 0.35
    right_wall_shape.friction = 0.5
    right_wall_shape.collision_type = WALL_TYPE
    right_wall_body.position = (right, zone_cy)
    space.add(right_wall_body, right_wall_shape)

    bodies, shapes = [], []
    for i in range(n_racers):
        start_r, start_c = i // cols, i % cols
        cx, cy = geo.cell_center(start_r, start_c)
        jx, jy = rng.uniform(-6, 6), rng.uniform(-6, 6)
        mass = racers[i]["weight"]
        body = pymunk.Body(mass=mass, moment=pymunk.moment_for_circle(mass, 0, geo.racer_radius))
        body.position = (cx + jx, cy + jy)
        shape = pymunk.Circle(body, geo.racer_radius)
        shape.elasticity = 0.5
        shape.friction = 0.35
        shape.collision_type = RACER_TYPE_BASE + i
        space.add(body, shape)
        bodies.append(body)
        shapes.append(shape)

    armed = [False] * n_racers
    finished = [False] * n_racers
    eliminated = [False] * n_racers
    active = [True] * n_racers
    flying_until = [0] * n_racers
    last_cell = [(i // cols, i % cols) for i in range(n_racers)]
    target = [geo.cell_center(*last_cell[i]) for i in range(n_racers)]
    winner_idx_box = [None]
    finish_log = []  # (step, racer_idx, x, y)
    elim_log = []  # (step, racer_idx, x, y)
    bump_log = []
    step_counter = {"n": 0}
    per_racer_rng = [random.Random(hashlib.sha256((str(seed) + f"racer{i}").encode()).hexdigest()) for i in range(n_racers)]

    RECOVERY_STEPS = int(0.30 * PHYSICS_HZ)
    RECOVERY_MIN_STEER_MULT = 0.12
    recovery_until = [0] * n_racers
    DECISION_STEPS = int(0.5 * PHYSICS_HZ)
    next_decision = [0] * n_racers
    JUNCTION_HESITATE_STEPS = int(0.15 * PHYSICS_HZ)

    STUCK_CHECK_STEPS = int(0.5 * PHYSICS_HZ)
    STUCK_LIMIT = 3
    stuck_dist_threshold = geo.racer_radius * 0.7
    stuck_check_pos = [None] * n_racers
    stuck_counters = [0] * n_racers

    AWARENESS_PICKUP = geo.cell * 6
    DANGER_RADIUS = geo.cell * 4
    AWARENESS_CHASE = geo.cell * 6

    def _greedy_step(candidates, point, maximize=False):
        def key(n):
            px, py = geo.cell_center(*n)
            return math.hypot(px - point[0], py - point[1])
        return (max if maximize else min)(candidates, key=key)

    def _eliminate(i, step):
        if eliminated[i] or finished[i]:
            return
        eliminated[i] = True
        active[i] = False
        pos = bodies[i].position
        elim_log.append((step, i, pos.x, pos.y))

    def _battle_recompute_target(i):
        """Same shape as simulate_race's _recompute_target (returns True on
        a real fork, for junction hesitation), but the target priority is
        battle-specific: seek a pickup when unarmed, chase the nearest foe
        when armed, flee an armed foe when unarmed and threatened, else fall
        back to the exact same finish-seeking flood-fill race mode uses."""
        r, c = last_cell[i]
        if (r, c) == finish_cell:
            target[i] = (fzx, fzy)
            return False
        candidates = open_neighbors(r, c, open_right, open_down, cols, rows)
        if not candidates:
            return False
        x, y = bodies[i].position

        if not armed[i]:
            best_pickup, best_d = None, AWARENESS_PICKUP
            for k in range(n_pickups):
                if pickup_collected[k]:
                    continue
                d = math.hypot(pickup_pos[k][0] - x, pickup_pos[k][1] - y)
                if d < best_d:
                    best_pickup, best_d = pickup_pos[k], d
            if best_pickup is not None:
                target[i] = geo.cell_center(*_greedy_step(candidates, best_pickup))
                return len(candidates) > 1
            best_enemy, best_d = None, DANGER_RADIUS
            for j in range(n_racers):
                if j == i or not active[j] or not armed[j]:
                    continue
                epos = bodies[j].position
                d = math.hypot(epos.x - x, epos.y - y)
                if d < best_d:
                    best_enemy, best_d = (epos.x, epos.y), d
            if best_enemy is not None:
                target[i] = geo.cell_center(*_greedy_step(candidates, best_enemy, maximize=True))
                return len(candidates) > 1
        else:
            best_enemy, best_d = None, AWARENESS_CHASE
            for j in range(n_racers):
                if j == i or not active[j]:
                    continue
                epos = bodies[j].position
                d = math.hypot(epos.x - x, epos.y - y)
                if d < best_d:
                    best_enemy, best_d = (epos.x, epos.y), d
            if best_enemy is not None:
                target[i] = geo.cell_center(*_greedy_step(candidates, best_enemy))
                return len(candidates) > 1

        best = min(dist_field[nr][nc] for (nr, nc) in candidates)
        best_candidates = [n for n in candidates if dist_field[n[0]][n[1]] == best]
        prng = per_racer_rng[i]
        if len(candidates) > 1 and prng.random() < racers[i]["confusion"]:
            choice = candidates[prng.randrange(len(candidates))]
        else:
            choice = best_candidates[prng.randrange(len(best_candidates))]
        target[i] = geo.cell_center(*choice)
        return len(candidates) > 1

    def on_begin(arbiter, space_, data):
        ct1, ct2 = arbiter.shapes[0].collision_type, arbiter.shapes[1].collision_type
        if FINISH_TYPE in (ct1, ct2):
            other = ct2 if ct1 == FINISH_TYPE else ct1
            idx = other - RACER_TYPE_BASE
            if 0 <= idx < n_racers and not finished[idx] and not eliminated[idx]:
                finished[idx] = True
                active[idx] = False
                finish_log.append((step_counter["n"], idx, bodies[idx].position.x, bodies[idx].position.y))
                if winner_idx_box[0] is None:
                    winner_idx_box[0] = idx
        return True

    RACER_VS_RACER_ELASTICITY = 0.92

    def on_pre_solve(arbiter, space_, data):
        ct1, ct2 = arbiter.shapes[0].collision_type, arbiter.shapes[1].collision_type
        if ct1 >= RACER_TYPE_BASE and ct2 >= RACER_TYPE_BASE:
            arbiter.elasticity = RACER_VS_RACER_ELASTICITY
        return True

    def _throw(loser_i, from_pos):
        lp = bodies[loser_i].position
        dx, dy = lp.x - from_pos.x, lp.y - from_pos.y
        dist = math.hypot(dx, dy) or 1.0
        bodies[loser_i].apply_impulse_at_world_point(
            (dx / dist * BATTLE_KNOCKBACK_IMPULSE, dy / dist * BATTLE_KNOCKBACK_IMPULSE), lp)
        flying_until[loser_i] = step_counter["n"] + int(BATTLE_FLYING_SECONDS * PHYSICS_HZ)

    def on_post_solve(arbiter, space_, data):
        ct1, ct2 = arbiter.shapes[0].collision_type, arbiter.shapes[1].collision_type
        impulse = arbiter.total_impulse.length
        if impulse < 0.5:
            return
        cps = arbiter.contact_point_set.points
        if not cps:
            return
        cx_, cy_ = cps[0].point_a.x, cps[0].point_a.y
        intensity = min(1.0, impulse / 400.0)

        if ct1 == WALL_TYPE or ct2 == WALL_TYPE:
            if len(bump_log) < 4000:
                bump_log.append((step_counter["n"], cx_, cy_, intensity, "wall"))
            other = ct2 if ct1 == WALL_TYPE else ct1
            idx = other - RACER_TYPE_BASE
            if (0 <= idx < n_racers and active[idx] and step_counter["n"] < flying_until[idx]
                    and impulse > BATTLE_WALL_KILL_IMPULSE):
                _eliminate(idx, step_counter["n"])

        elif ct1 >= RACER_TYPE_BASE and ct2 >= RACER_TYPE_BASE:
            if len(bump_log) < 4000:
                bump_log.append((step_counter["n"], cx_, cy_, intensity, "racer"))
            if impulse > 15.0:
                i1, i2 = ct1 - RACER_TYPE_BASE, ct2 - RACER_TYPE_BASE
                until = step_counter["n"] + RECOVERY_STEPS
                if 0 <= i1 < n_racers:
                    recovery_until[i1] = max(recovery_until[i1], until)
                if 0 <= i2 < n_racers:
                    recovery_until[i2] = max(recovery_until[i2], until)
                if 0 <= i1 < n_racers and 0 <= i2 < n_racers and active[i1] and active[i2]:
                    a1, a2 = armed[i1], armed[i2]
                    p1, p2 = bodies[i1].position, bodies[i2].position
                    if a1 and not a2:
                        armed[i1] = False
                        _throw(i2, p1)
                    elif a2 and not a1:
                        armed[i2] = False
                        _throw(i1, p2)
                    elif a1 and a2:
                        armed[i1] = False
                        armed[i2] = False
                        _throw(i2, p1)
                        _throw(i1, p2)

    space.on_collision(begin=on_begin, pre_solve=on_pre_solve, post_solve=on_post_solve)

    for i in range(n_racers):
        _battle_recompute_target(i)

    dt = 1.0 / PHYSICS_HZ
    steps_per_frame = max(1, PHYSICS_HZ // fps)
    max_steps = int(max_seconds * PHYSICS_HZ)
    min_steps = int(min_seconds * PHYSICS_HZ)

    MAX_SPEED = geo.cell / 0.42
    STEER_GAIN = 7.5
    SLOWDOWN_RADIUS = geo.cell * 0.55
    JITTER_HZ_SCALE = 3.0

    speed_mult = [1.0 + (1.0 - racers[i]["weight"]) * 0.6 for i in range(n_racers)]
    steer_mult = [1.0 - (racers[i]["weight"] - 1.0) * 0.5 for i in range(n_racers)]

    frames = []
    finish_frame_flags = {}
    elim_frame_flags = {}
    bump_frame_flags = {}
    frame_idx = 0

    while step_counter["n"] < max_steps:
        step_counter["n"] += 1
        t_now = step_counter["n"] * dt

        top_y, s_left, s_right, vy, vx = _zone_state(t_now)
        top_wall_body.position = (zone_cx, top_y)
        top_wall_body.velocity = (0, vy)
        left_wall_body.position = (s_left, zone_cy)
        left_wall_body.velocity = (vx, 0)
        right_wall_body.position = (s_right, zone_cy)
        right_wall_body.velocity = (-vx, 0)

        for i in range(n_racers):
            if not active[i]:
                continue
            x, y = bodies[i].position

            if not armed[i]:
                for k in range(n_pickups):
                    if pickup_collected[k]:
                        continue
                    if math.hypot(pickup_pos[k][0] - x, pickup_pos[k][1] - y) < PICKUP_RADIUS:
                        armed[i] = True
                        pickup_collected[k] = True
                        pickup_collect_step[k] = step_counter["n"]
                        break

            c = min(cols - 1, max(0, int((x - geo.border_w) / geo.cell)))
            r = min(rows - 1, max(0, int((y - geo.top_border) / geo.cell)))
            r = min(r, rows - 1)
            if (r, c) != last_cell[i] and y < geo.top_border + rows * geo.cell:
                last_cell[i] = (r, c)
                if _battle_recompute_target(i):
                    until = step_counter["n"] + JUNCTION_HESITATE_STEPS
                    recovery_until[i] = max(recovery_until[i], until)
                next_decision[i] = step_counter["n"] + DECISION_STEPS
            elif last_cell[i] == finish_cell:
                target[i] = (fzx, fzy)
            elif step_counter["n"] >= next_decision[i]:
                _battle_recompute_target(i)
                next_decision[i] = step_counter["n"] + DECISION_STEPS

            tx, ty = target[i]
            dx, dy = tx - x, ty - y
            dist = math.hypot(dx, dy) or 1.0
            speed_scale = min(1.0, max(0.35, dist / SLOWDOWN_RADIUS))
            desired_vx = dx / dist * MAX_SPEED * speed_mult[i] * speed_scale
            desired_vy = dy / dist * MAX_SPEED * speed_mult[i] * speed_scale
            vx_, vy_ = bodies[i].velocity
            steer_gain = STEER_GAIN * steer_mult[i]
            if step_counter["n"] < recovery_until[i]:
                remaining = (recovery_until[i] - step_counter["n"]) / RECOVERY_STEPS
                steer_gain *= RECOVERY_MIN_STEER_MULT + (1 - RECOVERY_MIN_STEER_MULT) * (1 - remaining)
            steer_x = (desired_vx - vx_) * steer_gain
            steer_y = (desired_vy - vy_) * steer_gain
            mass = racers[i]["weight"]
            jr = per_racer_rng[i]
            jitter_ang = math.sin(t_now * JITTER_HZ_SCALE + i * 1.7) * jr.uniform(0.5, 1.0)
            jitter_mag = mass * 60
            fx = mass * steer_x + math.cos(jitter_ang) * jitter_mag
            fy = mass * steer_y + math.sin(jitter_ang) * jitter_mag
            bodies[i].apply_force_at_world_point((fx, fy), bodies[i].position)

        space.step(dt)

        if step_counter["n"] % STUCK_CHECK_STEPS == 0:
            for i in range(n_racers):
                if not active[i]:
                    continue
                pos_now = bodies[i].position
                prev = stuck_check_pos[i]
                stuck_check_pos[i] = (pos_now.x, pos_now.y)
                if prev is None:
                    continue
                moved = math.hypot(pos_now.x - prev[0], pos_now.y - prev[1])
                if moved < stuck_dist_threshold:
                    stuck_counters[i] += 1
                else:
                    stuck_counters[i] = 0
                if stuck_counters[i] >= STUCK_LIMIT:
                    tx, ty = target[i]
                    ddx, ddy = tx - pos_now.x, ty - pos_now.y
                    ddist = math.hypot(ddx, ddy) or 1.0
                    nudge = MAX_SPEED * racers[i]["weight"] * 1.4
                    bodies[i].apply_impulse_at_world_point(
                        (ddx / ddist * nudge, ddy / ddist * nudge), pos_now)
                    recovery_until[i] = 0
                    stuck_counters[i] = 0

        if step_counter["n"] % steps_per_frame == 0:
            pos = []
            for i in range(n_racers):
                if active[i]:
                    b = bodies[i]
                    vx_, vy_ = b.velocity
                    ang = math.degrees(math.atan2(vy_, vx_)) + 90 if (vx_ or vy_) else 0.0
                    pos.append((b.position.x, b.position.y, ang))
                else:
                    pos.append(None)
            n_alive_now = sum(1 for a in active if a)
            frames.append({"pos": pos, "active": list(active), "armed": list(armed), "n_alive": n_alive_now})
            frame_idx += 1

            if finish_log and finish_log[-1][0] > step_counter["n"] - steps_per_frame:
                events = [(fl[1], fl[2], fl[3]) for fl in finish_log if fl[0] > step_counter["n"] - steps_per_frame]
                if events:
                    finish_frame_flags[frame_idx - 1] = events

            if elim_log and elim_log[-1][0] > step_counter["n"] - steps_per_frame:
                events = [(el[1], el[2], el[3]) for el in elim_log if el[0] > step_counter["n"] - steps_per_frame]
                if events:
                    elim_frame_flags[frame_idx - 1] = events

            recent_bumps = [b for b in bump_log if b[0] > step_counter["n"] - steps_per_frame]
            if recent_bumps:
                best = max(recent_bumps, key=lambda b: b[3])
                bump_frame_flags[frame_idx - 1] = (best[1], best[2], best[3], best[4])

            for i in range(n_racers):
                if (finished[i] or eliminated[i]) and shapes[i] in space.shapes:
                    try:
                        space.remove(bodies[i], shapes[i])
                    except Exception:
                        pass

            if step_counter["n"] >= min_steps and (finish_log or sum(1 for a in active if a) <= 1):
                break

    def _progress(i):
        r, c = last_cell[i]
        return dist_field[r][c] if dist_field[r][c] is not None else 999999

    if winner_idx_box[0] is not None:
        winner_idx = winner_idx_box[0]
    else:
        alive_now = [i for i in range(n_racers) if active[i]]
        if len(alive_now) == 1:
            winner_idx = alive_now[0]
        elif alive_now:
            winner_idx = min(alive_now, key=_progress)
        else:
            winner_idx = elim_log[-1][1] if elim_log else 0

    eliminated_order = [el[1] for el in elim_log]
    remaining_alive = sorted((i for i in range(n_racers) if active[i] and i != winner_idx), key=_progress)
    remaining_eliminated = [i for i in reversed(eliminated_order) if i != winner_idx]
    full_ranking = [winner_idx] + remaining_alive + remaining_eliminated

    finale_frames = int(1.6 * fps)
    if frames:
        last = dict(frames[-1])
        last["pos"] = list(last["pos"])
        for _ in range(finale_frames):
            frames.append(dict(last))

    return {
        "frames": frames,
        "finish_frame_flags": finish_frame_flags,
        "elim_frame_flags": elim_frame_flags,
        "bump_frame_flags": bump_frame_flags,
        "racers": racers,
        "n_racers": n_racers,
        "winner_idx": winner_idx,
        "winner_name": racers[winner_idx]["name"],
        "winner_finished": winner_idx in [fl[1] for fl in finish_log],
        "full_ranking": full_ranking,
        "pickup_pos": pickup_pos,
        "pickup_collect_step": pickup_collect_step,
        "steps_per_frame": steps_per_frame,
        "zone_state_fn": _zone_state,
        "zone_bounds": (top, bottom),
        "max_seconds": max_seconds,
        "fps": fps,
        "w": w,
        "h": h,
        "geo": geo,
        "maze_img": maze_img,
        "theme": theme,
        "finish_col": finish_col,
        "finish_zone": (fzx, fzy),
        "finale_start": len(frames) - finale_frames,
        "seed": seed,
    }


# --- Wording variety --------------------------------------------------

WIN_TEXT_TEMPLATES = ["{name} WINS!", "{name} TAKES THE MAZE!", "{name} FINDS THE WAY!", "{name} CROSSES FIRST!"]
BATTLE_WIN_TEXT_TEMPLATES = ["{name} SURVIVES!", "{name} IS LAST STANDING!", "{name} WINS THE ARENA!", "{name} TAKES IT ALL!"]
FIGHT_WORD_TEMPLATES = ["GO!", "RACE!", "RUN!", "MOVE!"]


def _pick_variant(seed, salt, templates):
    rng = random.Random(hashlib.sha256((str(seed) + salt).encode()).hexdigest())
    return rng.choice(templates)


# --- Rendering ---------------------------------------------------------

def build_race_clip(race):
    from moviepy import VideoClip

    w, h, fps = race["w"], race["h"], race["fps"]
    frames = race["frames"]
    racers = race["racers"]
    n = race["n_racers"]
    geo = race["geo"]
    theme = race["theme"]
    maze_img = race["maze_img"].convert("RGBA")
    finale_start = race["finale_start"]
    n_frames = len(frames)

    ICON_SIZE = int(geo.racer_radius * 2.6)
    icons = [make_racer_icon(r["color"], ICON_SIZE) for r in racers]

    HUD_MARGIN = int(h * 0.13)
    viewport_h = h - HUD_MARGIN
    maze_img_h = maze_img.height

    CAMERA_SMOOTH = 0.06
    LEAD_FRAC = 0.36
    camera_tops = []
    _prev = None
    for fr in frames:
        alive_y = [p[1] for p in fr["pos"] if p is not None]
        lead_y = max(alive_y) if alive_y else maze_img_h * 0.5
        if _prev is None:
            _prev = lead_y
        else:
            _prev = _prev + CAMERA_SMOOTH * (lead_y - _prev)
        cam_top = _prev - viewport_h * LEAD_FRAC
        cam_top = max(0.0, min(cam_top, max(0.0, maze_img_h - viewport_h)))
        camera_tops.append(cam_top)

    title_font = get_font(int(h * 0.032))
    counter_font = get_font(int(h * 0.028))
    win_font = get_font(int(h * 0.052))
    count_font = get_font(int(h * 0.11))
    finish_pop_font = get_font(int(h * 0.020))

    title_text = f"{n}-Way Maze Race"
    win_text_template = _pick_variant(race["seed"], "wintext", WIN_TEXT_TEMPLATES)
    go_word = _pick_variant(race["seed"], "goword", FIGHT_WORD_TEMPLATES)

    ambient_particles = _make_ambient_particles(race["seed"], 14, w, h)
    intro_frames = int(INTRO_SECONDS * fps)

    def make_frame(t):
        raw_idx = int(round(t * fps))
        in_intro = raw_idx < intro_frames
        idx = 0 if in_intro else min(n_frames - 1, raw_idx - intro_frames)
        st = frames[idx]
        cam_top = camera_tops[0] if in_intro else camera_tops[idx]

        img = Image.new("RGBA", (w, h), (*theme["floor"], 255))
        crop_top = int(cam_top)
        crop_bottom = min(maze_img_h, crop_top + viewport_h)
        maze_slice = maze_img.crop((0, crop_top, w, crop_bottom))
        img.paste(maze_slice, (0, HUD_MARGIN))

        d = ImageDraw.Draw(img, "RGBA")

        for p in ambient_particles:
            twinkle = 0.5 + 0.5 * math.sin(t * 1.6 + p["phase"])
            r = p["r"]
            alpha = int(30 + 70 * twinkle)
            d.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=(*theme["particle"], alpha))

        d.rectangle([0, 0, w, HUD_MARGIN], fill=(20, 20, 26, 235))
        tw = d.textlength(title_text, font=title_font)
        d.text((w / 2 - tw / 2, h * 0.02), title_text, font=title_font, fill=(255, 255, 255, 255))
        n_fin = st.get("n_finished", 0)
        counter_text = f"FINISHED: {n_fin}/{n}"
        cw = d.textlength(counter_text, font=counter_font)
        d.text((w / 2 - cw / 2, h * 0.075), counter_text, font=counter_font, fill=(*theme["accent"], 255))

        if not in_intro:
            for fi in range(max(0, idx - 6), idx + 1):
                if fi not in race["bump_frame_flags"]:
                    continue
                bx, by, intensity, kind = race["bump_frame_flags"][fi]
                age = idx - fi
                if age <= 5:
                    a = max(0, int(180 * intensity * (1 - age / 5.0)))
                    ry = by - crop_top + HUD_MARGIN
                    rr = 8 + age * 3
                    color = (255, 220, 120) if kind == "wall" else (255, 255, 255)
                    d.ellipse([bx - rr, ry - rr, bx + rr, ry + rr], outline=(*color, a), width=3)

            for fi in range(max(0, idx - 20), idx + 1):
                if fi not in race["finish_frame_flags"]:
                    continue
                age = idx - fi
                if age > 24:
                    continue
                pa = max(0, int(255 * (1 - age / 24.0)))
                for (ridx, fx, fy) in race["finish_frame_flags"][fi]:
                    ry = fy - crop_top + HUD_MARGIN - age * 1.5
                    label = f"{racers[ridx]['name']} FINISHED!"
                    lw = d.textlength(label, font=finish_pop_font)
                    d.text((fx - lw / 2, ry), label, font=finish_pop_font, fill=(255, 255, 255, pa),
                           stroke_width=2, stroke_fill=(0, 0, 0, pa))

        for i in range(n):
            pos = st["pos"][i]
            if pos is None:
                continue
            x, y, ang = pos
            ry = y - crop_top + HUD_MARGIN
            if ry < HUD_MARGIN - ICON_SIZE or ry > h + ICON_SIZE:
                continue
            icon = icons[i].rotate(-ang, resample=Image.BICUBIC)
            img.alpha_composite(icon, (int(x - icon.width / 2), int(ry - icon.height / 2)))

        if in_intro:
            remaining = INTRO_SECONDS - t
            if remaining > 0.7:
                num = "3"
            elif remaining > 0.35 if INTRO_SECONDS > 1.4 else False:
                num = "2"
            phase = t / INTRO_SECONDS * 3
            if phase < 1:
                num = "3"
            elif phase < 2:
                num = "2"
            elif phase < 2.6:
                num = "1"
            else:
                num = go_word
            cw2 = d.textlength(num, font=count_font)
            d.text((w / 2 - cw2 / 2, h * 0.42), num, font=count_font, fill=(255, 255, 255, 255),
                   stroke_width=6, stroke_fill=(0, 0, 0, 255))

        if idx >= finale_start and not in_intro:
            win_text = win_text_template.format(name=race["winner_name"])
            fade_in = min(1.0, (idx - finale_start) / (fps * 0.3))
            wa = int(255 * fade_in)
            wtw = d.textlength(win_text, font=win_font)
            d.rectangle([0, h * 0.42, w, h * 0.42 + h * 0.10], fill=(0, 0, 0, int(150 * fade_in)))
            d.text((w / 2 - wtw / 2, h * 0.44), win_text, font=win_font, fill=(255, 215, 60, wa),
                   stroke_width=5, stroke_fill=(0, 0, 0, wa))

        arr = np.array(img.convert("RGB"))

        if not in_intro:
            # A few px of camera shake right after a hard racer-vs-racer
            # bump sells the impact (a collision that only moves an icon a
            # few pixels can otherwise read as barely happening); wall bumps
            # and soft grazes stay shake-free so it doesn't fire constantly.
            shake_dx = shake_dy = 0.0
            for fi in range(max(0, idx - 3), idx + 1):
                flag = race["bump_frame_flags"].get(fi)
                if not flag:
                    continue
                _, _, intensity, kind = flag
                if kind != "racer" or intensity < 0.45:
                    continue
                age = idx - fi
                amt = intensity * max(0.0, 1 - age / 3.0) * 5.0
                jr = _det_jitter(fi)
                shake_dx += math.cos(jr * 6.283) * amt
                shake_dy += math.sin(jr * 6.283) * amt
            if shake_dx or shake_dy:
                arr = np.roll(arr, (int(round(shake_dy)), int(round(shake_dx))), axis=(0, 1))

        return arr

    duration = INTRO_SECONDS + n_frames / fps
    clip = VideoClip(make_frame, duration=duration)
    clip.fps = fps
    return clip


def build_battle_clip(race):
    """Battle-mode counterpart to build_race_clip: same camera/HUD/intro/
    win-banner/camera-shake scaffolding, adapted for a closed arena — camera
    tracks the alive-racer centroid instead of 'furthest along', HUD shows
    ALIVE count, a shrinking red zone-tint overlay replaces the finish
    stripe, weapon pickups are drawn until collected, and elimination
    pop-ups replace finish pop-ups. Racer icons are precomputed in both
    armed/unarmed variants (2 per racer) so the per-frame armed badge is a
    cheap variant swap instead of a fresh icon render (which would redo the
    shadow blur every frame)."""
    from moviepy import VideoClip

    w, h, fps = race["w"], race["h"], race["fps"]
    frames = race["frames"]
    racers = race["racers"]
    n = race["n_racers"]
    geo = race["geo"]
    theme = race["theme"]
    maze_img = race["maze_img"].convert("RGBA")
    finale_start = race["finale_start"]
    n_frames = len(frames)
    steps_per_frame = race["steps_per_frame"]
    zone_state_fn = race["zone_state_fn"]
    zone_top, zone_bottom = race["zone_bounds"]
    max_seconds = race["max_seconds"]

    ICON_SIZE = int(geo.racer_radius * 2.6)
    icons_unarmed = [make_racer_icon(r["color"], ICON_SIZE, armed=False) for r in racers]
    icons_armed = [make_racer_icon(r["color"], ICON_SIZE, armed=True) for r in racers]
    WEAPON_ICON_SIZE = int(geo.racer_radius * 1.6)
    weapon_icon = _make_weapon_icon(WEAPON_ICON_SIZE)

    HUD_MARGIN = int(h * 0.13)
    viewport_h = h - HUD_MARGIN
    maze_img_h = maze_img.height

    CAMERA_SMOOTH = 0.06
    LEAD_FRAC = 0.5
    camera_tops = []
    _prev = None
    for fr in frames:
        alive_pts = [p for p in fr["pos"] if p is not None]
        lead_y = (sum(p[1] for p in alive_pts) / len(alive_pts)) if alive_pts else maze_img_h * 0.5
        if _prev is None:
            _prev = lead_y
        else:
            _prev = _prev + CAMERA_SMOOTH * (lead_y - _prev)
        cam_top = _prev - viewport_h * LEAD_FRAC
        cam_top = max(0.0, min(cam_top, max(0.0, maze_img_h - viewport_h)))
        camera_tops.append(cam_top)

    title_font = get_font(int(h * 0.032))
    counter_font = get_font(int(h * 0.028))
    win_font = get_font(int(h * 0.052))
    count_font = get_font(int(h * 0.11))
    elim_pop_font = get_font(int(h * 0.020))

    title_text = f"{n}-Way Battle Royale"
    win_text_template = (_pick_variant(race["seed"], "wintext", WIN_TEXT_TEMPLATES) if race["winner_finished"]
                          else _pick_variant(race["seed"], "battlewintext", BATTLE_WIN_TEXT_TEMPLATES))
    go_word = _pick_variant(race["seed"], "goword", FIGHT_WORD_TEMPLATES)

    ambient_particles = _make_ambient_particles(race["seed"], 14, w, h)
    intro_frames = int(INTRO_SECONDS * fps)

    def make_frame(t):
        raw_idx = int(round(t * fps))
        in_intro = raw_idx < intro_frames
        idx = 0 if in_intro else min(n_frames - 1, raw_idx - intro_frames)
        st = frames[idx]
        cam_top = camera_tops[0] if in_intro else camera_tops[idx]

        img = Image.new("RGBA", (w, h), (*theme["floor"], 255))
        crop_top = int(cam_top)
        crop_bottom = min(maze_img_h, crop_top + viewport_h)
        maze_slice = maze_img.crop((0, crop_top, w, crop_bottom))
        img.paste(maze_slice, (0, HUD_MARGIN))

        d = ImageDraw.Draw(img, "RGBA")

        for p in ambient_particles:
            twinkle = 0.5 + 0.5 * math.sin(t * 1.6 + p["phase"])
            r = p["r"]
            alpha = int(30 + 70 * twinkle)
            d.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=(*theme["particle"], alpha))

        if not in_intro:
            # Closing-zone tint: solid red fill over the whole arena extent
            # with a transparent hole punched out for the current safe
            # funnel (bounded above by the closing top wall, open all the
            # way down to the finish) — cut on a plain (non-blending) draw
            # context so the punch is a real overwrite-to-transparent
            # rather than a 0-alpha no-op blend.
            t_phys = min(max_seconds, idx * steps_per_frame / PHYSICS_HZ)
            top_y, s_left, s_right, _vy, _vx = zone_state_fn(t_phys)
            danger = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            dd = ImageDraw.Draw(danger)
            arena_top_sy = max(HUD_MARGIN, zone_top - crop_top + HUD_MARGIN)
            arena_bottom_sy = min(h, zone_bottom - crop_top + HUD_MARGIN)
            if arena_bottom_sy > arena_top_sy:
                dd.rectangle([0, arena_top_sy, w, arena_bottom_sy], fill=(200, 30, 30, 85))
            safe_sy0 = max(HUD_MARGIN, top_y - crop_top + HUD_MARGIN)
            if arena_bottom_sy > safe_sy0:
                dd.rectangle([s_left, safe_sy0, s_right, arena_bottom_sy], fill=(0, 0, 0, 0))
            img.alpha_composite(danger)
            d = ImageDraw.Draw(img, "RGBA")

            for k, (px, py) in enumerate(race["pickup_pos"]):
                collect_step = race["pickup_collect_step"][k]
                if collect_step is not None and idx * steps_per_frame >= collect_step:
                    continue
                ry = py - crop_top + HUD_MARGIN
                bob = math.sin(t * 3.0 + k * 1.3) * geo.cell * 0.06
                img.alpha_composite(weapon_icon, (int(px - weapon_icon.width / 2),
                                                    int(ry + bob - weapon_icon.height / 2)))

        d.rectangle([0, 0, w, HUD_MARGIN], fill=(20, 20, 26, 235))
        tw = d.textlength(title_text, font=title_font)
        d.text((w / 2 - tw / 2, h * 0.02), title_text, font=title_font, fill=(255, 255, 255, 255))
        n_alive = st.get("n_alive", n)
        counter_text = f"ALIVE: {n_alive}/{n}"
        cw = d.textlength(counter_text, font=counter_font)
        d.text((w / 2 - cw / 2, h * 0.075), counter_text, font=counter_font, fill=(*theme["accent"], 255))

        if not in_intro:
            for fi in range(max(0, idx - 6), idx + 1):
                if fi not in race["bump_frame_flags"]:
                    continue
                bx, by, intensity, kind = race["bump_frame_flags"][fi]
                age = idx - fi
                if age <= 5:
                    a = max(0, int(180 * intensity * (1 - age / 5.0)))
                    ry = by - crop_top + HUD_MARGIN
                    rr = 8 + age * 3
                    color = (255, 220, 120) if kind == "wall" else (255, 255, 255)
                    d.ellipse([bx - rr, ry - rr, bx + rr, ry + rr], outline=(*color, a), width=3)

            for fi in range(max(0, idx - 20), idx + 1):
                if fi not in race["elim_frame_flags"]:
                    continue
                age = idx - fi
                if age > 24:
                    continue
                pa = max(0, int(255 * (1 - age / 24.0)))
                for (ridx, fx, fy) in race["elim_frame_flags"][fi]:
                    ry = fy - crop_top + HUD_MARGIN - age * 1.5
                    label = f"{racers[ridx]['name']} ELIMINATED!"
                    lw = d.textlength(label, font=elim_pop_font)
                    d.text((fx - lw / 2, ry), label, font=elim_pop_font, fill=(255, 90, 90, pa),
                           stroke_width=2, stroke_fill=(0, 0, 0, pa))

            for fi in range(max(0, idx - 20), idx + 1):
                if fi not in race["finish_frame_flags"]:
                    continue
                age = idx - fi
                if age > 24:
                    continue
                pa = max(0, int(255 * (1 - age / 24.0)))
                for (ridx, fx, fy) in race["finish_frame_flags"][fi]:
                    ry = fy - crop_top + HUD_MARGIN - age * 1.5
                    label = f"{racers[ridx]['name']} FINISHED!"
                    lw = d.textlength(label, font=elim_pop_font)
                    d.text((fx - lw / 2, ry), label, font=elim_pop_font, fill=(255, 255, 255, pa),
                           stroke_width=2, stroke_fill=(0, 0, 0, pa))

        for i in range(n):
            pos = st["pos"][i]
            if pos is None:
                continue
            x, y, ang = pos
            ry = y - crop_top + HUD_MARGIN
            if ry < HUD_MARGIN - ICON_SIZE or ry > h + ICON_SIZE:
                continue
            is_armed = st["armed"][i] if "armed" in st else False
            icon_set = icons_armed if is_armed else icons_unarmed
            icon = icon_set[i].rotate(-ang, resample=Image.BICUBIC)
            img.alpha_composite(icon, (int(x - icon.width / 2), int(ry - icon.height / 2)))

        if in_intro:
            phase = t / INTRO_SECONDS * 3
            if phase < 1:
                num = "3"
            elif phase < 2:
                num = "2"
            elif phase < 2.6:
                num = "1"
            else:
                num = go_word
            cw2 = d.textlength(num, font=count_font)
            d.text((w / 2 - cw2 / 2, h * 0.42), num, font=count_font, fill=(255, 255, 255, 255),
                   stroke_width=6, stroke_fill=(0, 0, 0, 255))

        if idx >= finale_start and not in_intro:
            win_text = win_text_template.format(name=race["winner_name"])
            fade_in = min(1.0, (idx - finale_start) / (fps * 0.3))
            wa = int(255 * fade_in)
            wtw = d.textlength(win_text, font=win_font)
            d.rectangle([0, h * 0.42, w, h * 0.42 + h * 0.10], fill=(0, 0, 0, int(150 * fade_in)))
            d.text((w / 2 - wtw / 2, h * 0.44), win_text, font=win_font, fill=(255, 215, 60, wa),
                   stroke_width=5, stroke_fill=(0, 0, 0, wa))

        arr = np.array(img.convert("RGB"))

        if not in_intro:
            shake_dx = shake_dy = 0.0
            for fi in range(max(0, idx - 3), idx + 1):
                flag = race["bump_frame_flags"].get(fi)
                if not flag:
                    continue
                _, _, intensity, kind = flag
                if kind != "racer" or intensity < 0.45:
                    continue
                age = idx - fi
                amt = intensity * max(0.0, 1 - age / 3.0) * 5.0
                jr = _det_jitter(fi)
                shake_dx += math.cos(jr * 6.283) * amt
                shake_dy += math.sin(jr * 6.283) * amt
            if shake_dx or shake_dy:
                arr = np.roll(arr, (int(round(shake_dy)), int(round(shake_dx))), axis=(0, 1))

        return arr

    duration = INTRO_SECONDS + n_frames / fps
    clip = VideoClip(make_frame, duration=duration)
    clip.fps = fps
    return clip


def build_cold_open_clip(race, seconds=COLD_OPEN_SECONDS):
    """Standalone short (silent) VideoClip: a punched-in zoom + white flash
    + fade-to-black tease of the winner closing in on the finish line, no
    HUD/countdown/labels/win-banner. Renders directly from `race`'s own data
    (independent of build_race_clip's per-call camera-smoothing state) so it
    can be prepended anywhere in a larger timeline — right before a Short's
    own countdown, or way ahead of a tournament's final heat.

    Source frame: a few frames BEFORE the winner's actual finish-line
    crossing (not the crossing itself), so the "{name} FINISHED!" pop-up
    label — which build_race_clip renders starting exactly at the finish
    frame — is guaranteed not to be on screen yet. That's what keeps this a
    tease instead of a spoiler."""
    from moviepy import VideoClip

    w, h, fps = race["w"], race["h"], race["fps"]
    frames = race["frames"]
    racers = race["racers"]
    n = race["n_racers"]
    geo = race["geo"]
    theme = race["theme"]
    maze_img = race["maze_img"].convert("RGBA")
    maze_img_h = maze_img.height

    winner_idx = race["winner_idx"]
    finish_fi = None
    for fi, events in race["finish_frame_flags"].items():
        if any(ridx == winner_idx for (ridx, _, _) in events):
            finish_fi = fi
            break
    if finish_fi is None:
        finish_fi = len(frames) - 1
    src_idx = max(0, finish_fi - 15)

    HUD_MARGIN = int(h * 0.13)
    viewport_h = h - HUD_MARGIN
    ICON_SIZE = int(geo.racer_radius * 2.6)
    icons = [make_racer_icon(r["color"], ICON_SIZE) for r in racers]

    # Replay the exact camera EMA build_race_clip uses, up through src_idx
    # only, so this teaser frames the shot the same way the live race would
    # have at that point instead of guessing a static crop.
    CAMERA_SMOOTH = 0.06
    LEAD_FRAC = 0.36
    cam_top = None
    for i in range(src_idx + 1):
        alive_y = [p[1] for p in frames[i]["pos"] if p is not None]
        lead_y = max(alive_y) if alive_y else maze_img_h * 0.5
        cam_top = lead_y if cam_top is None else cam_top + CAMERA_SMOOTH * (lead_y - cam_top)
    top = (cam_top - viewport_h * LEAD_FRAC) if cam_top is not None else 0.0
    top = max(0.0, min(top, max(0.0, maze_img_h - viewport_h)))

    base_img = Image.new("RGBA", (w, h), (*theme["floor"], 255))
    crop_top = int(top)
    crop_bottom = min(maze_img_h, crop_top + viewport_h)
    maze_slice = maze_img.crop((0, crop_top, w, crop_bottom))
    base_img.paste(maze_slice, (0, HUD_MARGIN))
    st = frames[src_idx]
    for i in range(n):
        pos = st["pos"][i]
        if pos is None:
            continue
        x, y, ang = pos
        ry = y - crop_top + HUD_MARGIN
        icon = icons[i].rotate(-ang, resample=Image.BICUBIC)
        base_img.alpha_composite(icon, (int(x - icon.width / 2), int(ry - icon.height / 2)))
    base_arr = np.array(base_img.convert("RGB")).astype(np.float32)

    def make_frame(t):
        zoom = 1.05 + 0.15 * (t / seconds)
        zw, zh = max(1, int(w / zoom)), max(1, int(h / zoom))
        zx0, zy0 = (w - zw) // 2, (h - zh) // 2
        zimg = (Image.fromarray(base_arr.astype(np.uint8))
                .crop((zx0, zy0, zx0 + zw, zy0 + zh)).resize((w, h), Image.BICUBIC))
        arr = np.array(zimg).astype(np.float32)
        if t < 0.15:
            flash_amt = (1.0 - t / 0.15) ** 1.5
            arr = arr + (255 - arr) * flash_amt * 0.85
        fade_start = seconds - 0.12
        if t > fade_start:
            arr = arr * (1 - (t - fade_start) / 0.12)
        return np.clip(arr, 0, 255).astype(np.uint8)

    clip = VideoClip(make_frame, duration=seconds)
    clip.fps = fps
    return clip


def build_battle_cold_open_clip(race, seconds=COLD_OPEN_SECONDS):
    """Battle-mode counterpart to build_cold_open_clip: same zoom/flash/
    fade tease, sourced from a few frames before the match's climax — the
    winning finish-line crossing, or the final elimination if nobody
    reached the finish — whichever it is, so it teases the arena without
    spoiling the outcome."""
    from moviepy import VideoClip

    w, h, fps = race["w"], race["h"], race["fps"]
    frames = race["frames"]
    racers = race["racers"]
    n = race["n_racers"]
    geo = race["geo"]
    theme = race["theme"]
    maze_img = race["maze_img"].convert("RGBA")
    maze_img_h = maze_img.height

    climax_fis = list(race["elim_frame_flags"].keys()) + list(race["finish_frame_flags"].keys())
    final_fi = max(climax_fis) if climax_fis else len(frames) - 1
    src_idx = max(0, final_fi - 15)

    HUD_MARGIN = int(h * 0.13)
    viewport_h = h - HUD_MARGIN
    ICON_SIZE = int(geo.racer_radius * 2.6)
    icons_unarmed = [make_racer_icon(r["color"], ICON_SIZE, armed=False) for r in racers]
    icons_armed = [make_racer_icon(r["color"], ICON_SIZE, armed=True) for r in racers]

    CAMERA_SMOOTH = 0.06
    LEAD_FRAC = 0.5
    cam_top = None
    for i in range(src_idx + 1):
        alive_pts = [p for p in frames[i]["pos"] if p is not None]
        lead_y = (sum(p[1] for p in alive_pts) / len(alive_pts)) if alive_pts else maze_img_h * 0.5
        cam_top = lead_y if cam_top is None else cam_top + CAMERA_SMOOTH * (lead_y - cam_top)
    top = (cam_top - viewport_h * LEAD_FRAC) if cam_top is not None else 0.0
    top = max(0.0, min(top, max(0.0, maze_img_h - viewport_h)))

    base_img = Image.new("RGBA", (w, h), (*theme["floor"], 255))
    crop_top = int(top)
    crop_bottom = min(maze_img_h, crop_top + viewport_h)
    maze_slice = maze_img.crop((0, crop_top, w, crop_bottom))
    base_img.paste(maze_slice, (0, HUD_MARGIN))
    st = frames[src_idx]
    for i in range(n):
        pos = st["pos"][i]
        if pos is None:
            continue
        x, y, ang = pos
        ry = y - crop_top + HUD_MARGIN
        is_armed = st["armed"][i] if "armed" in st else False
        icon_set = icons_armed if is_armed else icons_unarmed
        icon = icon_set[i].rotate(-ang, resample=Image.BICUBIC)
        base_img.alpha_composite(icon, (int(x - icon.width / 2), int(ry - icon.height / 2)))
    base_arr = np.array(base_img.convert("RGB")).astype(np.float32)

    def make_frame(t):
        zoom = 1.05 + 0.15 * (t / seconds)
        zw, zh = max(1, int(w / zoom)), max(1, int(h / zoom))
        zx0, zy0 = (w - zw) // 2, (h - zh) // 2
        zimg = (Image.fromarray(base_arr.astype(np.uint8))
                .crop((zx0, zy0, zx0 + zw, zy0 + zh)).resize((w, h), Image.BICUBIC))
        arr = np.array(zimg).astype(np.float32)
        if t < 0.15:
            flash_amt = (1.0 - t / 0.15) ** 1.5
            arr = arr + (255 - arr) * flash_amt * 0.85
        fade_start = seconds - 0.12
        if t > fade_start:
            arr = arr * (1 - (t - fade_start) / 0.12)
        return np.clip(arr, 0, 255).astype(np.uint8)

    clip = VideoClip(make_frame, duration=seconds)
    clip.fps = fps
    return clip


# --- Sound synthesis --------------------------------------------------

SR = 44100


def _hook_sting():
    """A short punchy sting for the cold-open flash — a low thump plus a
    quick rising sweep, distinct from every in-race sound so the very first
    thing a viewer hears reads as 'something is about to happen'."""
    dur = 0.35
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    thump = np.sin(2 * np.pi * 85 * t) * np.exp(-t * 12) * 0.8
    sweep_freq = 300 + 900 * np.clip(t / 0.18, 0, 1)
    sweep = np.sin(2 * np.pi * sweep_freq * t) * np.exp(-t * 7) * 0.5
    noise = np.random.default_rng(7).uniform(-1, 1, n) * np.exp(-t * 40) * 0.25
    return np.tanh(thump + sweep + noise).astype(np.float32)


def build_cold_open_sfx(seconds=COLD_OPEN_SECONDS):
    """Stereo float32 array matching build_cold_open_clip's exact duration —
    the sting lands right on the flash at t=0."""
    n_samples = int(seconds * SR)
    buf = np.zeros(n_samples, dtype=np.float32)
    sting = _hook_sting()
    end = min(n_samples, len(sting))
    if end > 0:
        buf[:end] += sting[:end]
    peak = np.max(np.abs(buf)) or 1.0
    buf = (buf / peak) * 0.85
    return np.stack([buf, buf], axis=1)


def _bump_sound(intensity, kind="wall"):
    intensity = max(0.15, min(1.0, intensity))
    dur = 0.09 + 0.03 * intensity
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    base_freq = 340 if kind == "wall" else 260
    env = np.exp(-t * 55)
    tone = sum(np.sin(2 * np.pi * f * t) for f in (base_freq, base_freq * 1.6)) / 2
    noise = np.random.default_rng(int(intensity * 999)).uniform(-1, 1, n) * np.exp(-t * 70) * 0.35
    sfx = (tone * 0.65 + noise) * env * intensity
    return sfx.astype(np.float32)


def _beep(freq, dur=0.12, vol=0.5):
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    env = np.exp(-t * 9)
    return (np.sin(2 * np.pi * freq * t) * env * vol).astype(np.float32)


def _go_horn():
    a = _beep(560, 0.22, 0.75)
    b = _beep(980, 0.26, 0.6)
    n = max(len(a), len(b))
    out = np.zeros(n, dtype=np.float32)
    out[: len(a)] += a
    out[: len(b)] += b
    return out


def _finish_ding():
    dur = 0.30
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    env = np.exp(-t * 6)
    tone = np.sin(2 * np.pi * 1100 * t) * 0.6 + np.sin(2 * np.pi * 1650 * t) * 0.3
    return (tone * env * 0.5).astype(np.float32)


def _elim_sound():
    """Short descending-pitch 'knockout' zap plus a noise crack — distinct
    from _finish_ding's bright rising chime, for battle mode's eliminations."""
    dur = 0.28
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    env = np.exp(-t * 7)
    f0, f1 = 650.0, 120.0
    freq = f0 + (f1 - f0) * (t / dur)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(phase) * env * 0.6
    noise = np.random.default_rng(3).uniform(-1, 1, n) * np.exp(-t * 20) * 0.3
    return (tone + noise).astype(np.float32)


def _victory_chime():
    parts = []
    thump_dur = 0.18
    tn = int(SR * thump_dur)
    tt = np.linspace(0, thump_dur, tn, endpoint=False)
    thump = np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 16) * 0.9
    parts.append((0.0, thump))

    notes = [523.25, 659.25, 783.99, 1046.50]
    t_cursor = 0.05
    for f in notes:
        dur = 0.26
        n = int(SR * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        env = np.exp(-t * 3.2)
        tone = (np.sin(2 * np.pi * f * t) * 0.7 + np.sin(2 * np.pi * f * 2 * t) * 0.2 + np.sin(2 * np.pi * f * 3 * t) * 0.1)
        parts.append((t_cursor, tone * env * 0.45))
        t_cursor += 0.11

    chord_dur = 0.6
    cn = int(SR * chord_dur)
    ct = np.linspace(0, chord_dur, cn, endpoint=False)
    cenv = np.exp(-ct * 2.0)
    chord = sum(np.sin(2 * np.pi * f * ct) for f in notes[:3]) / 3
    parts.append((t_cursor, chord * cenv * 0.5))

    total_dur = max(start + len(p) / SR for start, p in parts)
    n_total = int(total_dur * SR) + 1
    out = np.zeros(n_total, dtype=np.float32)
    for start, p in parts:
        pos = int(start * SR)
        end = min(n_total, pos + len(p))
        if end > pos:
            out[pos:end] += p[: end - pos]
    return np.tanh(out * 1.1).astype(np.float32)


def build_duck_envelope(n_samples, sr, bump_times, depth=0.35, attack=0.03, release=0.35):
    env = np.ones(n_samples, dtype=np.float32)
    a_n, r_n = max(1, int(attack * sr)), max(1, int(release * sr))
    attack_ramp = np.linspace(1.0, depth, a_n, dtype=np.float32)
    release_ramp = np.linspace(depth, 1.0, r_n, dtype=np.float32)
    for t in bump_times:
        pos = int(t * sr)
        a0, a1 = max(0, pos), min(n_samples, pos + a_n)
        if a1 > a0:
            env[a0:a1] = np.minimum(env[a0:a1], attack_ramp[: a1 - a0])
        r0, r1 = max(0, pos + a_n), min(n_samples, pos + a_n + r_n)
        if r1 > r0:
            env[r0:r1] = np.minimum(env[r0:r1], release_ramp[: r1 - r0])
    return env


def build_sfx_array(race):
    fps = race["fps"]
    T0 = INTRO_SECONDS
    n_frames = len(race["frames"])
    duration = T0 + n_frames / fps
    n_samples = int(duration * SR) + SR
    buf = np.zeros(n_samples, dtype=np.float32)

    def _add(t, sfx, vol=1.0):
        pos = int(t * SR)
        end = min(n_samples, pos + len(sfx))
        if end > pos:
            buf[pos:end] += sfx[: end - pos] * vol

    quarter = INTRO_SECONDS / 3
    for i in range(2):
        _add(i * quarter, _beep(700, 0.10, 0.55))
    _add(2 * quarter, _go_horn())

    for frame_idx, (bx, by, intensity, kind) in race["bump_frame_flags"].items():
        t = T0 + frame_idx / fps
        _add(t, _bump_sound(intensity, kind), vol=0.8 if kind == "racer" else 0.55)

    for frame_idx, events in race.get("finish_frame_flags", {}).items():
        t = T0 + frame_idx / fps
        for _ in events:
            _add(t, _finish_ding(), vol=0.7)
    if "elim_frame_flags" in race:
        for frame_idx, events in race["elim_frame_flags"].items():
            t = T0 + frame_idx / fps
            for _ in events:
                _add(t, _elim_sound(), vol=0.75)

    finale_t = T0 + race["finale_start"] / fps
    _add(finale_t, _victory_chime(), vol=0.9)

    peak = np.max(np.abs(buf)) or 1.0
    buf = (buf / peak) * 0.85
    stereo = np.stack([buf, buf], axis=1)
    return stereo, SR


def race_bump_times(race):
    fps = race["fps"]
    return [INTRO_SECONDS + fi / fps for fi in race["bump_frame_flags"].keys()]


# --- Thumbnail -----------------------------------------------------------

def generate_thumbnail(race, output_path, w=1280, h=720, caption="WHO FINISHES FIRST?",
                        banner_color=(60, 180, 90), badge_text=None):
    theme = race["theme"]
    racers = race["racers"]
    n = race["n_racers"]

    grad = np.zeros((h, w, 3), dtype=np.uint8)
    for ch in range(3):
        grad[:, :, ch] = int(theme["floor"][ch])
    img = Image.fromarray(grad, mode="RGB").convert("RGBA")

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w * 0.25, -h * 0.3, w * 0.75, h * 0.7], fill=(*theme["particle"], 90))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img, glow)

    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, h * 0.78, w, h], fill=(*banner_color, 255))

    icon_size = int(h * (0.30 if n <= 6 else 0.24))
    gap = w * 0.015
    max_row_w = w * 0.94
    while icon_size * n + gap * (n - 1) > max_row_w and icon_size > 30:
        icon_size -= 4
    icons = [make_racer_icon(r["color"], icon_size) for r in racers]
    total_w = sum(ic.width for ic in icons) + gap * (n - 1)
    x = (w - total_w) / 2
    for ic in icons:
        img.alpha_composite(ic, (int(x), int(h * 0.42 - ic.height / 2)))
        x += ic.width + gap

    badge_font = get_font(int(h * 0.09))
    badge_text = badge_text or f"{n}-WAY MAZE RACE"
    bw = d.textlength(badge_text, font=badge_font)
    d.text((w / 2 - bw / 2, h * 0.05), badge_text, font=badge_font, fill=(255, 215, 60, 255),
           stroke_width=6, stroke_fill=(0, 0, 0, 255))

    title_font = get_font(int(h * 0.08))
    title_text = caption
    tw = d.textlength(title_text, font=title_font)
    d.text((w / 2 - tw / 2, h * 0.85), title_text, font=title_font, fill=(255, 255, 255, 255),
           stroke_width=5, stroke_fill=(0, 0, 0, 255))

    img.convert("RGB").save(output_path, "JPEG", quality=92)
    return output_path

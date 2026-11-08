"""Deterministic, render-only motion shared by all recorded game modes.

MoviePy can request frames in any order. All state is prepared from the
physics history once; drawing never advances a simulation or a random RNG.
"""
import bisect
import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

VICTORY_SECONDS = 3.2
VICTORY_STYLES = {
    "Blacky": ("bow", 8, 1.2), "Sunny": ("twirl", 13, 1),
    "Cocoa": ("toast", 11, 1.4), "Pine": ("toast", 8, 1.1),
    "Tango": ("bow", 11, 1.6), "Ghost": ("float", 15, .8),
    "Sky": ("float", 11, .65), "Rosy": ("twirl", 9, 2),
    "Cherry": ("sway", 7, 1.9), "Minty": ("jelly", 10, 1.7),
    "Grape": ("orbit", 12, .9), "Coral": ("jelly", 7, 2.2),
    "Lime": ("hop", 17, 1.6), "Slate": ("robot", 7, 1.4),
    "Amber": ("flutter", 12, 1.8), "Ruby": ("stomp", 10, 1.05),
}


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass(frozen=True)
class Impact:
    time: float
    racer: int
    x: float
    y: float
    nx: float
    ny: float
    strength: float


class ImpactRecorder:
    """Observe real contact normals/impulses without touching physics bodies."""
    def __init__(self, count, type_base, radius, physics_hz):
        self.count, self.type_base = count, type_base
        self.radius, self.physics_hz = radius, physics_hz
        self.events = []
        self.last = [-1.0] * count

    def record(self, arbiter, step):
        if len(self.events) >= 8192 or not arbiter.contact_point_set.points:
            return
        now = step / self.physics_hz
        normal = arbiter.contact_point_set.normal
        impulse = arbiter.total_impulse.length
        for side, shape in enumerate(arbiter.shapes):
            racer = shape.collision_type - self.type_base
            if not 0 <= racer < self.count:
                continue
            strength = min(1.0, impulse / max(1, shape.body.mass * self.radius * 12))
            # Resting contacts must not continually restart the spring.
            if strength < .10 or now - self.last[racer] < .075:
                continue
            point = arbiter.contact_point_set.points[0]
            contact = point.point_a if side == 0 else point.point_b
            sign = -1 if side == 0 else 1
            self.events.append(Impact(now, racer, contact.x, contact.y,
                                      normal.x * sign, normal.y * sign, strength))
            self.last[racer] = now


def impact_scale(age, strength):
    """Compression, one spring rebound, then an exact return to rest."""
    if age < 0 or age >= .45:
        return 1.0, 1.0
    compression = .22 * strength * math.exp(-age * 10) * math.cos(age * 23)
    normal = 1 - compression
    return normal, 1 / normal


def victory_pose(name, time):
    x = y = angle = 0.0
    sx = 1.0
    if time <= 0 or time >= VICTORY_SECONDS:
        return x, y, angle, sx, sx
    move, amplitude, frequency = VICTORY_STYLES.get(name, ("hop", 10, 1))
    envelope = min(1, time / .18) * min(1, (VICTORY_SECONDS - time) / .65)
    phase = time * frequency * math.tau
    wave = math.sin(phase)
    if move == "float":
        y, angle = -amplitude * (.65 + .35 * wave), wave * .12
    elif move == "twirl":
        t = clamp((time - .15) / 1.5, 0, 1)
        angle = frequency * math.tau * t * t * (3 - 2 * t)
        y, sx = -amplitude * math.sin(math.pi * t), 1 + wave * .04 * envelope
    elif move == "toast":
        y, angle = -amplitude * min(1, time / .35), wave * .15
    elif move == "bow":
        angle, y, x = wave * .24, abs(wave) * 4, wave * amplitude * .35
    elif move == "sway":
        x, angle, y = wave * amplitude, math.sin(phase + .4) * .2, -abs(wave) * 5
    elif move == "jelly":
        sx, y = 1 + wave * .17 * envelope, -abs(math.sin(phase * .5)) * amplitude
    elif move == "orbit":
        x, y, angle = wave * amplitude * .65, -amplitude * (.5 + .5 * math.cos(phase)), wave * .18
    elif move in ("hop", "stomp"):
        jump = max(0, wave)
        y = -jump * amplitude
        sx = 1 + (.13 * max(0, -wave) - .06 * jump) * envelope
        angle = math.sin(phase * .5) * (.08 if move == "stomp" else .18)
    elif move == "robot":
        x = math.copysign(amplitude * .35, wave)
        angle = math.copysign(.12, math.cos(phase))
        y = -max(0, wave) * 5
    elif move == "flutter":
        x, y, angle = wave * 4, -amplitude * (.6 + .4 * wave), math.sin(phase * 2) * .16
    return x * envelope, y * envelope, angle if move == "twirl" else angle * envelope, sx, 1 / sx


def victory_tile(icon, name, time, size):
    """Fit even rotating poses inside their card tile; never clip names."""
    x, y, angle, sx, sy = victory_pose(name, time)
    unit = size / 120
    x, y = x * unit, size * .04 + y * unit
    c, s = abs(math.cos(angle)), abs(math.sin(angle))
    extent = min(size * .74, (size - 2 * abs(x) - 8 * unit) / (c * sx + s * sy),
                 (size - 2 * abs(y) - 8 * unit) / (s * sx + c * sy))
    sprite = icon.resize((max(1, round(extent * sx)), max(1, round(extent * sy))), Image.Resampling.LANCZOS)
    sprite = sprite.rotate(-math.degrees(angle), Image.Resampling.BICUBIC, expand=True)
    tile = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(tile)
    d.ellipse((size * .23, size * .82, size * .77, size * .91), fill=(0, 0, 0, 45))
    tile.alpha_composite(sprite, (round(size / 2 + x - sprite.width / 2),
                                 round(size / 2 + y - sprite.height / 2)))
    return tile


def squash_sprite(icon, angle, event, now):
    sprite = icon.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    if event is None:
        return sprite
    normal, tangent = impact_scale(now - event.time, event.strength)
    if abs(normal - 1) < .002:
        return sprite
    # Inverse of the screen-space scale along the physical contact normal.
    nx, ny = event.nx, event.ny
    a = nx * nx / normal + ny * ny / tangent
    b = nx * ny * (1 / normal - 1 / tangent)
    e = ny * ny / normal + nx * nx / tangent
    size = math.ceil(max(sprite.size) * 1.32)
    src = Image.new("RGBA", (size, size))
    src.alpha_composite(sprite, ((size - sprite.width) // 2, (size - sprite.height) // 2))
    center = size / 2
    return src.transform(src.size, Image.Transform.AFFINE,
                         (a, b, center * (1 - a - b), b, e, center * (1 - b - e)),
                         Image.Resampling.BICUBIC)


class VideoMotion:
    def __init__(self, race, camera_tops, viewport_h, physics_hz=120):
        self.race, self.frames, self.fps = race, race["frames"], race["fps"]
        self.w, self.viewport_h = race["w"], viewport_h
        self.radius = race["geo"].racer_radius if "geo" in race else race["racer_radius"]
        self.speed_unit = race["geo"].cell * 2.4 if "geo" in race else 760 * race["w"] / 1080
        self.times = []
        self.impacts, self.velocities = [], []
        events = sorted(race.get("motion_impacts", ()), key=lambda event: event.time)
        self.events, self.event_times = events, [event.time for event in events]
        latest, cursor = [None] * race["n_racers"], 0
        for fi, frame in enumerate(self.frames):
            now = frame.get("step", (fi + 1) * physics_hz / self.fps) / physics_hz
            if self.times:
                now = max(now, self.times[-1] + 1 / self.fps)
            self.times.append(now)
            while cursor < len(events) and events[cursor].time <= now:
                event = events[cursor]
                latest[event.racer] = event
                cursor += 1
            self.impacts.append(tuple(latest))
            velocities = []
            for ri, pos in enumerate(frame["pos"]):
                prev = self.frames[fi - 1]["pos"][ri] if fi else None
                dt = now - self.times[fi - 1] if fi else 1 / self.fps
                velocities.append(((pos[0] - prev[0]) / dt, (pos[1] - prev[1]) / dt)
                                  if pos is not None and prev is not None else (0, 0))
            self.velocities.append(velocities)
        self.cameras = self._cameras(camera_tops)

    def _cameras(self, camera_tops):
        result, zoom, cx, leader, changed_at = [], 1.0, self.w / 2, None, -10.0
        blend = 1 - math.exp(-4.5 / self.fps)
        finishers, finish_point = set(), None
        finish_y = self.race["geo"].finish_line_y if "geo" in self.race else self.race["finish_y"]
        for fi, (frame, base_top) in enumerate(zip(self.frames, camera_tops)):
            now = self.times[fi]
            for ri, x, y in self.race.get("finish_frame_flags", {}).get(fi, ()):
                finishers.add(ri)
                if len(finishers) >= self.race.get("qualifier_count", 1):
                    finish_point = (x, y)
            visible = [(i, p) for i, p in enumerate(frame["pos"]) if p is not None
                       and base_top <= p[1] <= base_top + self.viewport_h]
            ordered = sorted(visible, key=lambda item: (-item[1][1], item[0]))
            target = ordered[0] if ordered else None
            wanted, focus = 1.0, (self.w / 2, base_top + self.viewport_h * .4)
            if target:
                ri, point = target
                if leader is not None and ri != leader:
                    changed_at = now
                leader, focus = ri, point
                event = self.impacts[fi][ri]
                if finish_y - point[1] < self.viewport_h * .65:
                    wanted = 1.12
                elif now - changed_at < 1.1:
                    wanted = 1.07
                elif event and now - event.time < .25 and event.strength > .55:
                    wanted = 1.045
                elif len(ordered) > 1 and abs(point[1] - ordered[1][1][1]) < self.radius * 6:
                    wanted = 1.035
            if finish_point:
                focus, wanted = finish_point, 1.12
            zoom += (wanted - zoom) * blend
            cx += (focus[0] - cx) * blend
            vw, vh = self.w / zoom, self.viewport_h / zoom
            margin = self.radius * 1.6
            x = clamp(cx - vw / 2, focus[0] - vw + margin, focus[0] - margin)
            y = clamp(base_top + (self.viewport_h - vh) * .42,
                      focus[1] - vh + margin, focus[1] - margin)
            result.append((clamp(x, 0, self.w - vw), clamp(y, base_top, base_top + self.viewport_h - vh), vw, vh))
        return result

    def presentation(self, states):
        for fi, view in enumerate(states):
            x, top, width, height = self.cameras[fi]
            directions = []
            for active, pos in zip(self.frames[fi]["active"], self.frames[fi]["pos"]):
                direction = None
                if active and pos is not None:
                    if pos[1] + self.radius < top:
                        direction = "above"
                    elif pos[1] - self.radius > top + height:
                        direction = "below"
                directions.append(direction)
            view.update(camera=self.cameras[fi], directions=tuple(directions))
        return states

    def apply_camera(self, image, idx, camera_top, hud):
        x, y, width, height = self.cameras[idx]
        # Only the playfield is transformed. Labels and the HUD remain crisp.
        # The composited world is opaque. RGB's separable resize avoids the
        # costly premultiplied RGBA affine resample at 1080p/60 FPS.
        scene = image.crop((0, hud, self.w, image.height)).convert("RGB")
        top = clamp(y - camera_top, 0, scene.height - height)
        scene = scene.resize(scene.size, Image.Resampling.BICUBIC,
                             box=(x, top, x + width, top + height))
        image.paste(scene, (0, hud))

    def paint(self, image, idx, camera_top, hud, icons, intro=False, armed_icons=None, angle_sign=1):
        frame, now = self.frames[idx], self.times[idx]
        if not intro:
            layer = Image.new("RGBA", (self.w, self.viewport_h))
            d = ImageDraw.Draw(layer)
            for ri, pos in enumerate(frame["pos"]):
                if pos is None or not camera_top - self.radius * 3 < pos[1] < camera_top + self.viewport_h + self.radius * 3:
                    continue
                vx, vy = self.velocities[idx][ri]
                energy = clamp(math.hypot(vx, vy) / self.speed_unit, 0, 1)
                if energy < .18:
                    continue
                points = []
                for sample in range(18):
                    at = now - (17 - sample) * .018
                    fi = bisect.bisect_right(self.times, at, 0, idx + 1) - 1
                    p = self.frames[fi]["pos"][ri] if fi >= 0 else None
                    if p is not None:
                        points.append((p[0], p[1] - camera_top))
                color = self.race["racers"][ri]["color"]
                for j in range(1, len(points)):
                    fraction = j / len(points)
                    width = max(1, round(self.radius * .55 * energy * fraction))
                    d.line((points[j - 1], points[j]), fill=(*color, round(125 * energy * fraction)), width=width)
                if energy > .65:
                    speed = max(1, math.hypot(vx, vy))
                    ux, uy = vx / speed, vy / speed
                    for side in (-1, 1):
                        x, y = pos[0] - uy * self.radius * side, pos[1] - camera_top + ux * self.radius * side
                        d.line((x - ux * self.radius, y - uy * self.radius,
                                x - ux * self.radius * (1.7 + energy), y - uy * self.radius * (1.7 + energy)),
                               fill=(255, 248, 212, round(110 * energy)), width=max(1, round(self.w / 540)))
            first = bisect.bisect_left(self.event_times, now - .32)
            last = bisect.bisect_right(self.event_times, now)
            for event in self.events[max(first, last - 12):last]:
                if not camera_top - self.radius * 4 < event.y < camera_top + self.viewport_h + self.radius * 4:
                    continue
                age = now - event.time
                for particle in range(3 + round(event.strength * 5)):
                    spread = (particle / 7 - .5) * 2.6
                    angle = math.atan2(event.ny, event.nx) + spread
                    speed = self.radius * (3 + event.strength * 6) * (.7 + .3 * math.sin(particle * 7 + event.racer))
                    dx, dy = math.cos(angle) * speed, math.sin(angle) * speed
                    x, y = event.x + dx * age, event.y - camera_top + dy * age + self.radius * 3 * age * age
                    tail = .025 * (1 - age / .32)
                    d.line((x - dx * tail, y - dy * tail, x, y),
                           fill=(255, 227, 158, round(220 * (1 - age / .32) * event.strength)),
                           width=max(1, round(self.w / 540)))
            image.alpha_composite(layer, (0, hud))
        for ri, pos in enumerate(frame["pos"]):
            if pos is None:
                continue
            x, y, angle = pos
            sy = y - camera_top + hud
            if sy < hud - self.radius * 3 or sy > image.height + self.radius * 3:
                continue
            icon = armed_icons[ri] if armed_icons and frame.get("armed", (False,) * len(icons))[ri] else icons[ri]
            sprite = squash_sprite(icon, angle * angle_sign, None if intro else self.impacts[idx][ri], now)
            image.alpha_composite(sprite, (round(x - sprite.width / 2), round(sy - sprite.height / 2)))

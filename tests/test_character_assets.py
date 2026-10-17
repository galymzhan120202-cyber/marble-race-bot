"""Object characters retain their identity across videos and browser assets."""
from pathlib import Path
import json
import re

import numpy as np
from PIL import Image, ImageDraw
import pytest

import racer_art as art
import race_sim as sim

ROOT = Path(__file__).resolve().parents[1]


def test_browser_and_video_rosters_keep_the_same_identity_and_physics_traits():
    source = (ROOT / 'web' / 'game-core.js').read_text(encoding='utf8')
    block = re.search(r'const RACER_POOL\s*=\s*\[(.*?)\n\];', source, re.S).group(1)
    browser = []
    for entry in re.findall(r'\{([^{}]+)\}', block):
        browser.append({
            'name': re.search(r'name\s*:\s*"([^"]+)"', entry).group(1),
            'color': tuple(map(int, re.search(r'color\s*:\s*\[([^]]+)\]', entry).group(1).split(','))),
            'weight': float(re.search(r'weight\s*:\s*([\d.]+)', entry).group(1)),
            'confusion': float(re.search(r'confusion\s*:\s*([\d.]+)', entry).group(1)),
        })
    assert browser == sim.RACER_POOL
    expected = {r['name'] for r in sim.RACER_POOL}
    assert set(art.STYLES) == expected
    assert set(art.IDENTITIES) == expected
    for name, identity in art.IDENTITIES.items():
        assert all(isinstance(identity[key], str) and identity[key].strip()
                   for key in ('name', 'kind', 'label', 'description')), name


@pytest.mark.parametrize('size', [32, 64, 256])
def test_every_character_has_a_distinct_silhouette_at_game_sizes(size):
    silhouettes = []
    for racer in sim.RACER_POOL:
        portrait = art.make_portrait((125, 125, 125), size, name=racer['name'])
        assert portrait.mode == 'RGBA' and portrait.size == (size, size)
        alpha = np.array(portrait.getchannel('A'))
        silhouette = alpha >= 128
        assert silhouette.sum() > size*size*.08, racer['name']
        assert all(alpha[y, x] < 16 for x, y in ((0,0),(size-1,0),(0,size-1),(size-1,size-1)))
        silhouettes.append(silhouette.tobytes())
    # Comparing RGB alone would allow identical squares with different
    # eyes. This checks the object outline and transparent cutouts instead.
    assert len(set(silhouettes)) == len(sim.RACER_POOL)


@pytest.mark.parametrize('racer', sim.RACER_POOL, ids=lambda r: r['name'])
def test_browser_png_is_the_exact_canonical_video_portrait(racer):
    filename = ROOT / 'assets' / 'racers' / (racer['name'].lower()+'.png')
    with Image.open(filename) as image:
        assert image.mode == 'RGBA' and image.size == (256, 256)
        expected = art.make_portrait(racer['color'], 256, name=racer['name'])
        assert image.tobytes() == expected.tobytes(), f'Rebuild stale browser asset: {filename.name}'


def test_portrait_cache_does_not_leak_edits_between_game_consumers():
    racer = sim.RACER_POOL[0]
    first = art.make_portrait(racer['color'], 64, name=racer['name'])
    expected = first.tobytes()
    first.paste((255,0,255,255), (0,0,64,64))
    assert art.make_portrait(racer['color'], 64, name=racer['name']).tobytes() == expected


def test_browser_identity_catalog_matches_python_and_loads_before_the_ui():
    source = (ROOT / 'assets' / 'racers' / 'catalog.js').read_text(encoding='utf8')
    match = re.search(r'\bRACER_IDENTITIES\s*=\s*(\{.*\})\s*;?\s*$', source, re.S)
    assert match, 'The generated catalog must contain the shared identity data'
    assert json.loads(match.group(1)) == art.IDENTITIES
    html = (ROOT / 'index.html').read_text(encoding='utf8')
    assert html.index('assets/racers/catalog.js') < html.index('web/game.js')


@pytest.mark.parametrize('run', [sim.simulate_race, sim.simulate_battle, sim.simulate_drop])
@pytest.mark.parametrize('seed', [0, 1, 17, 41])
def test_random_rosters_keep_canonical_browser_colours_and_traits(run, seed):
    canonical = {r['name']: r for r in sim.RACER_POOL}
    race = run(360,640,seed,n_racers=8,max_seconds=1,min_seconds=0)
    assert all(racer == canonical[racer['name']] for racer in race['racers'])


@pytest.mark.parametrize('run,builder', [
    (sim.simulate_race,sim.build_race_clip),
    (sim.simulate_battle,sim.build_battle_clip),
    (sim.simulate_drop,sim.build_drop_clip),
])
def test_rotating_sprite_renderers_preserve_ears_straws_and_badge_pixels(monkeypatch, run, builder):
    # An extreme, opaque-corner silhouette catches clipping that ordinary
    # circular sprites hide. Exercise the real video drawing paths.
    def portrait(color, size=90, armed=False, name=''):
        image = Image.new('RGBA', (size,size))
        ImageDraw.Draw(image).rectangle((1,1,size-2,size-2),fill=(230,20,130,255))
        return image
    monkeypatch.setattr(sim, 'make_racer_icon', portrait)
    original = Image.Image.rotate
    rotations = []
    def record(image, angle, *args, **kwargs):
        output = original(image, angle, *args, **kwargs)
        if abs(angle) == 45:
            before = np.array(image.getchannel('A'),dtype=float).sum()
            after = np.array(output.getchannel('A'),dtype=float).sum()
            rotations.append(after/before)
            assert output.width > image.width and output.height > image.height
        return output
    monkeypatch.setattr(Image.Image, 'rotate', record)
    race = run(360,640,17,n_racers=2,max_seconds=1,min_seconds=0)
    for frame in race['frames']:
        frame['pos'] = [(p[0],p[1],45) if p else None for p in frame['pos']]
    clip = builder(race)
    try:
        frame = clip.get_frame(sim.INTRO_SECONDS+.1)
        assert frame.shape == (640,360,3)
        assert rotations and min(rotations) >= .98
    finally:
        clip.close()

"""Local previews and music fallback must work without publishing or HTTP."""
import json
from pathlib import Path
import wave

import numpy as np
import pytest
import requests

import video_gen


MUSIC = Path(__file__).resolve().parents[1] / 'music'


def test_offline_selection_never_calls_openverse(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('An offline preview attempted an HTTP request')

    monkeypatch.setattr(video_gen.requests, 'get', forbidden)
    monkeypatch.setattr(video_gen, 'base_dir', str(MUSIC.parent))
    music, attribution = video_gen.pick_background_music(90, allow_network=False)
    assert Path(music).is_file()
    assert not Path(music).name.startswith('_openverse')
    assert attribution.startswith('Original music:')


def test_openverse_failure_uses_bundled_music(monkeypatch):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(args[0])
        raise requests.ConnectionError('Network unavailable')

    monkeypatch.setattr(video_gen.requests, 'get', unavailable)
    monkeypatch.setattr(video_gen, 'base_dir', str(MUSIC.parent))
    music, attribution = video_gen.pick_background_music(90)
    assert calls
    assert Path(music).parent == MUSIC
    assert Path(music).suffix == '.wav'
    assert 'Original music:' in attribution


def test_online_selection_remains_openverse_first(monkeypatch):
    monkeypatch.setattr(video_gen, 'fetch_openverse_music',
                        lambda duration: ('downloaded.mp3', 'External track credit'))
    assert video_gen.pick_background_music(10) == ('downloaded.mp3', 'External track credit')


def test_unexpected_download_error_still_reaches_local_fallback(monkeypatch):
    def failed_download(duration):
        raise RuntimeError('Unexpected download failure')

    monkeypatch.setattr(video_gen, 'fetch_openverse_music', failed_download)
    monkeypatch.setattr(video_gen, 'base_dir', str(MUSIC.parent))
    music, attribution = video_gen.pick_background_music(20)
    assert Path(music).is_file()
    assert Path(music).suffix == '.wav'
    assert attribution.startswith('Original music:')


def test_empty_offline_library_uses_sfx_only_and_ignores_stale_download(monkeypatch, tmp_path):
    music = tmp_path / 'music'
    music.mkdir()
    (music / '_openverse_temp.mp3').write_bytes(b'stale download')
    monkeypatch.setattr(video_gen, 'base_dir', str(tmp_path))
    assert video_gen.pick_background_music(20, allow_network=False) == (None, None)


def test_third_party_attribution_keeps_license_and_source(monkeypatch, tmp_path):
    music = tmp_path / 'music'
    music.mkdir()
    (music / 'fallback_attribution.json').write_text(json.dumps([
        dict(file='credit.wav', title='Example', creator='Composer', license='by',
             foreign_landing_url='https://example.test/track'),
        dict(file='public.wav', license='cc0'),
    ]))
    monkeypatch.setattr(video_gen, 'base_dir', str(tmp_path))
    assert video_gen.get_local_music_attribution('credit.wav') == (
        'Music: "Example" by Composer (BY) — https://example.test/track')
    assert video_gen.get_local_music_attribution('public.wav') is None


def test_bundled_loops_are_audible_unclipped_and_seamless():
    metadata = json.loads((MUSIC / 'fallback_attribution.json').read_text(encoding='utf-8'))
    assert len(metadata) == 3
    samples = []
    total_size = 0
    for entry in metadata:
        path = MUSIC / entry['file']
        total_size += path.stat().st_size
        assert entry['license'] == 'original'
        assert (MUSIC.parent / entry['source']).is_file()
        with wave.open(str(path)) as wav:
            assert wav.getnchannels() == 2 and wav.getsampwidth() == 2
            rate = wav.getframerate()
            audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, 2) / 32768
        assert 12 <= len(audio) / rate <= 20
        assert abs(len(audio) / rate - entry['duration_seconds']) < .001
        assert .4 < np.max(np.abs(audio)) < .7
        assert np.max(np.abs(audio[0] - audio[-1])) < 1 / 32768
        # No silent bars, DC bias or coincident stereo channels.
        for second in range(int(len(audio) / rate)):
            assert np.sqrt(np.mean(audio[second * rate:(second + 1) * rate] ** 2)) > .03
        assert np.max(np.abs(audio.mean(axis=0))) < .001
        assert np.sqrt(np.mean((audio[:, 0] - audio[:, 1]) ** 2)) > .005
        samples.append(audio[:rate].tobytes())
    assert len(set(samples)) == 3
    assert total_size < 5_000_000


def test_bundled_audio_can_be_rebuilt_exactly_from_original_source():
    from scripts.generate_fallback_music import TRACKS, synthesize

    for track in TRACKS:
        expected = np.round(synthesize(track) * 32767).astype('<i2').tobytes()
        with wave.open(str(MUSIC / track['file'])) as wav:
            assert wav.readframes(wav.getnframes()) == expected

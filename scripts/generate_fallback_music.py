"""Rebuild three original, seamless instrumental loops without downloads.

All notes, envelopes and percussion are synthesized here; no samples, songs,
external recordings or generative services are used. Keep the resulting WAVs
and fallback_attribution.json in music/ so production uploads have a local bed.
"""
import argparse
import json
from pathlib import Path
import wave

import numpy as np


SAMPLE_RATE = 22050
TRACKS = (
    dict(file='grid_glide.wav', title='Grid Glide', bpm=120, root=48, seed=137,
         progression=(0, 5, 7, 0), melody=(12, 16, 19, 16, 14, 16, 21, 19), tone=.18),
    dict(file='soft_sparks.wav', title='Soft Sparks', bpm=128, root=50, seed=241,
         progression=(0, 7, 5, 0), melody=(19, 16, 14, 12, 16, 19, 21, 16), tone=.26),
    dict(file='sunny_circuit.wav', title='Sunny Circuit', bpm=112, root=53, seed=419,
         progression=(0, 5, 0, 7), melody=(12, 14, 16, 19, 21, 19, 16, 14), tone=.12),
)


def _frequency(note):
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def _envelope(length, attack, release):
    env = np.ones(length)
    a = min(length, max(1, round(attack * SAMPLE_RATE)))
    r = min(length, max(1, round(release * SAMPLE_RATE)))
    env[:a] *= np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    env[-r:] *= np.sin(np.linspace(np.pi / 2, 0, r)) ** 2
    return env


def synthesize(track):
    """Eight bars of restrained plucks, warm chords, soft bass and percussion."""
    beat = 60.0 / track['bpm']
    length = round(32 * beat * SAMPLE_RATE)
    mix = np.zeros((length, 2), dtype=np.float64)
    rng = np.random.default_rng(track['seed'])

    def add(signal, when, gain, pan=0.0):
        indices = (round(when * SAMPLE_RATE) + np.arange(len(signal))) % length
        # Equal-power panning and wrapped tails preserve continuity at the loop.
        angle = (pan + 1) * np.pi / 4
        np.add.at(mix[:, 0], indices, signal * gain * np.cos(angle))
        np.add.at(mix[:, 1], indices, signal * gain * np.sin(angle))

    def note(midi, duration, brightness=.15, decay=None):
        t = np.arange(round(duration * SAMPLE_RATE)) / SAMPLE_RATE
        phase = 2 * np.pi * _frequency(midi) * t
        sound = np.sin(phase) + brightness * np.sin(2 * phase) + .035 * np.sin(3 * phase)
        if decay is not None:
            sound *= np.exp(-t / decay)
        return sound * _envelope(len(t), .012, min(.1, duration / 3))

    for bar in range(8):
        start = bar * 4 * beat
        chord_root = track['root'] + track['progression'][bar % 4]
        for interval, pan in ((0, -.5), (4, .1), (7, .5)):
            chord = note(chord_root + 12 + interval, 4.25 * beat, .06)
            chord *= _envelope(len(chord), .16, .38)
            add(chord, start, .048, pan)

        for pulse in range(4):
            when = start + pulse * beat
            add(note(chord_root - 12 + (7 if pulse == 3 else 0), .8 * beat, .08, .25),
                when, .19)
            # Rounded sine kick: a gentle pitch fall, with no clipped transient.
            t = np.arange(round(.2 * SAMPLE_RATE)) / SAMPLE_RATE
            kick = np.sin(2 * np.pi * (48 * t + 2.8 * (1 - np.exp(-25 * t))))
            kick *= np.exp(-22 * t) * _envelope(len(t), .004, .025)
            add(kick, when, .14 if pulse % 2 == 0 else .09)
            if pulse % 2:
                # Filtered noise gives a brushed backbeat rather than a sharp snare.
                noise = rng.normal(0, 1, round(.09 * SAMPLE_RATE))
                brush = np.convolve(noise, np.ones(9) / 9, mode='same')
                brush *= _envelope(len(brush), .008, .07)
                add(brush, when, .07, -.12)

        for eighth in range(8):
            when = start + eighth * beat / 2
            motif = track['melody'][(eighth + (bar // 4) * 2) % 8]
            # Keep the melody in the home key; leave a breath at every bar end.
            if eighth != 7:
                add(note(track['root'] + motif, .62 * beat, track['tone'], .19),
                    when, .10 if eighth % 2 == 0 else .067, .28 if eighth % 2 else -.28)
            noise = rng.normal(0, 1, round(.035 * SAMPLE_RATE))
            # A quiet, short shaker; no bright sustained high-frequency layer.
            noise -= np.convolve(noise, np.ones(5) / 5, mode='same')
            noise *= _envelope(len(noise), .004, .026)
            add(noise, when, .008, -.35 if eighth % 2 else .35)

    # A six-millisecond seam taper prevents a click when WAV playback loops.
    seam = round(.006 * SAMPLE_RATE)
    fade = np.sin(np.linspace(0, np.pi / 2, seam))[:, None] ** 2
    mix[:seam] *= fade
    mix[-seam:] *= fade[::-1]
    mix -= mix.mean(axis=0)
    peak = np.max(np.abs(mix))
    if peak:
        mix *= .62 / peak
    return mix.astype(np.float32)


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    metadata = []
    for track in TRACKS:
        sound = synthesize(track)
        with wave.open(str(output / track['file']), 'wb') as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(np.round(sound * 32767).astype('<i2').tobytes())
        metadata.append(dict(
            file=track['file'], title=track['title'], creator='Marble Race',
            license='original', source='scripts/generate_fallback_music.py',
            description='Original procedural composition; no external samples or recordings.',
            bpm=track['bpm'], duration_seconds=round(len(sound) / SAMPLE_RATE, 3),
        ))
        print(f"{track['file']}: {len(sound) / SAMPLE_RATE:.2f}s, stereo {SAMPLE_RATE} Hz")
    (output / 'fallback_attribution.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'music')
    generate(parser.parse_args().output)

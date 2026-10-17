"""Decode music once, close its reader, then mix an owned sample buffer."""
import math

import numpy as np
from moviepy import AudioFileClip, AudioArrayClip

from race_sim import SR, build_duck_envelope


def prepare_music(path, duration, volume, bump_times):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Music needs a positive finite duration')
    # The old pipelines replaced AudioFileClip with AudioArrayClip without
    # closing the original FFmpeg reader. Repeated scheduled runs leaked it.
    with AudioFileClip(str(path)) as source:
        length = min(duration, source.duration)
        if not math.isfinite(length) or length <= 0:
            raise ValueError('Empty music track')
        samples = source.subclipped(0, length).to_soundarray(fps=SR)
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim == 1:
            samples = np.repeat(samples[:, None], 2, axis=1)
        elif samples.ndim == 2 and samples.shape[1] == 1:
            samples = np.repeat(samples, 2, axis=1)
        if samples.ndim != 2 or samples.shape[1] != 2 or not len(samples) or not np.isfinite(samples).all():
            raise ValueError('Invalid music samples')
    # Own the final array: neither loop playback nor ducking retains a reader.
    total = math.ceil(duration*SR)
    audio = np.tile(samples, (math.ceil(total/len(samples)), 1))[:total].copy()
    envelope = build_duck_envelope(total, SR, bump_times).astype(np.float32)
    fade_in = min(total, round(SR*.025))
    fade_out = min(total, round(SR*.18))
    envelope[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)
    envelope[-fade_out:] *= np.linspace(1, 0, fade_out, dtype=np.float32)
    audio *= envelope[:, None] * volume
    return AudioArrayClip(audio, fps=SR).with_duration(duration)

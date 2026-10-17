from pathlib import Path

import numpy as np
import pytest

import audio_mix


def test_looped_music_is_audible_after_source_reader_closes(monkeypatch):
    original=audio_mix.AudioFileClip
    readers=[]
    def track(*args, **kwargs):
        clip=original(*args, **kwargs);readers.append(clip);return clip
    monkeypatch.setattr(audio_mix,'AudioFileClip',track)
    clip=audio_mix.prepare_music(Path(__file__).parents[1]/'music/grid_glide.wav',33.2,.15,[])
    try:
        assert readers and all(source.reader is None for source in readers)
        assert clip.duration==33.2
        for start in (1,17,32):
            frames=clip.get_frame(start+np.arange(400)/audio_mix.SR)
            assert frames.shape==(400,2) and np.isfinite(frames).all()
            assert np.sqrt(np.mean(frames**2))>.001
        assert np.max(np.abs(clip.array[0]))==0
        assert np.max(np.abs(clip.array[-1]))==0
        assert np.max(np.abs(clip.array))<1
    finally:
        clip.close()


def test_decode_error_closes_reader(monkeypatch):
    class Broken:
        duration=1
        closed=False
        def __enter__(self):return self
        def __exit__(self,*args):self.closed=True
        def subclipped(self,*args):return self
        def to_soundarray(self,**kwargs):raise RuntimeError('decode failed')
    source=Broken()
    monkeypatch.setattr(audio_mix,'AudioFileClip',lambda *args:source)
    with pytest.raises(RuntimeError):audio_mix.prepare_music('broken.wav',3,.2,[])
    assert source.closed

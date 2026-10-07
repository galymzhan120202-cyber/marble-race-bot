from unittest.mock import MagicMock
import random

import video_gen
import battle_gen
import drop_gen
import tournament_gen
import pytest


def test_upload_retries_chunks_on_one_resumable_request(monkeypatch):
    credentials=MagicMock(expired=False)
    monkeypatch.setattr(video_gen.Credentials,'from_authorized_user_file',lambda *a:credentials)
    monkeypatch.setattr(video_gen.os.path,'exists',lambda *a:True)
    client=MagicMock()
    monkeypatch.setattr(video_gen.googleapiclient.discovery,'build',lambda *a,**k:client)
    monkeypatch.setattr(video_gen.googleapiclient.http,'MediaFileUpload',MagicMock())
    request=client.videos.return_value.insert.return_value
    request.next_chunk.side_effect=[(None,None),(None,{'id':'mock-video'})]
    assert video_gen.upload_to_youtube('preview.mp4','Title','Description')=='mock-video'
    assert client.videos.return_value.insert.call_count==1
    assert request.next_chunk.call_count==2
    for call in request.next_chunk.call_args_list:
        assert call.kwargs['num_retries']==video_gen.MAX_RETRIES


@pytest.mark.parametrize('build',[video_gen.build_title_and_description,battle_gen.build_battle_title_and_description,drop_gen.build_drop_title_and_description])
def test_timeout_description_does_not_claim_a_finish(build):
    _,description,_=build(['Sky','Ghost'],'Sky','timeout')
    assert 'Time limit reached' in description
    assert 'first' not in description


def test_battle_description_explains_both_win_conditions_without_revealing_result():
    _,description,_=battle_gen.build_battle_title_and_description(['Sky','Ghost'],'Sky','finish')
    assert 'finish line first' in description
    assert 'last racer standing' in description
    assert 'Sky wins' not in description


@pytest.mark.parametrize('build', [video_gen.build_title_and_description,
    battle_gen.build_battle_title_and_description, drop_gen.build_drop_title_and_description])
@pytest.mark.parametrize('reason', ['finish', 'last_standing', 'timeout'])
def test_public_metadata_is_independent_of_the_winner(build, reason):
    for seed in range(30):
        random.seed(seed)
        first = build(['Sky', 'Ghost'], 'Sky', reason)
        random.seed(seed)
        second = build(['Sky', 'Ghost'], 'Ghost', reason)
        assert first == second


def test_tournament_metadata_does_not_reveal_the_champion_in_tags_or_text():
    for seed in range(30):
        random.seed(seed)
        first = tournament_gen.build_tournament_title_and_description('Sky')
        random.seed(seed)
        second = tournament_gen.build_tournament_title_and_description('Ghost')
        assert first == second
        assert 'Sky' not in str(first) and 'Ghost' not in str(first)

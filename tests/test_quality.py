import pytest
import numpy as np

from race_quality import quality_issues, generate_playable, SimulationQualityError
import race_sim as sim
from racer_art import make_portrait, STYLES


def sample_race():
    return dict(n_racers=2,full_ranking=[0,1],winner_idx=0,result_reason='finish',
        n_finished_total=1,racer_radius=10,fps=24,finale_start=100,
        racers=[{'name':'Sky'},{'name':'Ghost'}],
        frames=[{'pos':[(0,i*2,0),(30,i*2,0)]} for i in range(100)])


@pytest.mark.parametrize('problem',['timeout','stall','coordinates','ranking','qualifiers'])
def test_publish_gate_rejects_bad_simulations(problem):
    race=sample_race()
    required=1
    if problem=='timeout': race['result_reason']='timeout'
    if problem=='stall':
        for f in race['frames']: f['pos'][0]=(0,10,0)
    if problem=='coordinates': race['frames'][0]['pos'][0]=(float('nan'),0,0)
    if problem=='ranking': race['full_ranking']=[0,0]
    if problem=='qualifiers': required=2
    assert quality_issues(race,required)


def test_retries_choose_new_seed_and_stop_after_valid_race():
    seeds=[]
    def simulate(seed):
        seeds.append(seed)
        race=sample_race()
        if len(seeds)==1: race['result_reason']='timeout'
        return race
    result=generate_playable(simulate,seed=7)
    assert result['generation_attempts']==2
    assert len(set(seeds))==2
    assert not quality_issues(result)


def test_failed_simulations_are_never_returned_for_upload():
    calls=[]
    def simulate(seed):
        calls.append(seed)
        race=sample_race(); race['result_reason']='timeout'
        return race
    with pytest.raises(SimulationQualityError):
        generate_playable(simulate,seed=7,max_attempts=3)
    assert len(calls)==3


@pytest.mark.parametrize('run,builder',[
    (sim.simulate_race,sim.build_cold_open_clip),
    (sim.simulate_battle,sim.build_battle_cold_open_clip),
    (sim.simulate_drop,sim.build_drop_cold_open_clip)])
def test_hook_has_moving_action_and_never_shows_finish(run,builder):
    race=run(360,640,17,n_racers=4,max_seconds=8,min_seconds=1)
    start,end=sim.hook_window(race)
    assert 0 <= start <= end < race['finale_start']
    if race['finish_frame_flags']:
        assert end < min(race['finish_frame_flags'])
    winner=race['winner_idx']
    race['winner_idx']=(winner+1)%race['n_racers']
    assert (start,end)==sim.hook_window(race)
    clip=builder(race)
    try:
        a,b=clip.get_frame(0),clip.get_frame(.5)
        assert a.shape==(640,360,3)
        assert np.mean(np.abs(a.astype(float)-b.astype(float)))>0.5
        assert np.mean(a)<240  # no white flash hiding the first frame
    finally:
        clip.close()


def test_all_character_portraits_remain_distinct_without_color():
    portraits=[make_portrait((100,140,180),96,name=name).tobytes() for name in STYLES]
    assert len(set(portraits))==16
    for name in STYLES:
        normal=np.array(make_portrait((40,40,46),64,name=name))
        armed=np.array(make_portrait((40,40,46),64,name=name,armed=True))
        assert normal.shape==(64,64,4)
        assert normal[:,:,3].min()==0 and normal[:,:,3].max()==255
        assert not np.array_equal(normal,armed)

const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=['web/game-core.js','web/game-session.js'].map(p=>fs.readFileSync(path.join(root,p),'utf8')).join('\n');
const {session,buildRace,stepRace}=new Function(source+'\nreturn {session:GameSession,buildRace,stepRace};')();
const config={seed:0xffffffff,roster:[6,1,7,12],youIdx:6,mode:'race',arena:'crossroads',arenaSize:'m',finishTarget:1};

test('race links preserve all inputs and reject incompatible or malformed links',()=>{
  assert.deepEqual(session.decode(session.encode(config)),config);
  for(const c of [{...config,seed:-1},{...config,seed:2**32},{...config,roster:[6,6]},
    {...config,youIdx:99},{...config,arena:'missing'},{...config,finishTarget:9}]) assert.equal(session.encode(c),null);
  for(const text of ['', '2~race',session.encode(config).replace(/^2/,'1'),session.encode(config)+'~extra',
    '2~race~crossroads~m~NaN~6~6.1~1','2~race~crossroads~m~f~6~6.6~1', '<script>']) assert.equal(session.decode(text),null);
});

test('cup rotates three distinct arenas and preserves the entrant set and selected racer',()=>{
  const a=session.makeCup(config),b=session.makeCup(config);
  assert.deepEqual(a,b);
  assert.equal(new Set(a.rounds.map(r=>r.arena)).size,3);
  for(const c of a.rounds){assert.deepEqual([...c.roster].sort(),[...config.roster].sort());assert.equal(c.youIdx,6);assert.equal(c.finishTarget,3);}
  assert.notDeepEqual(a.rounds[0].roster,a.rounds[1].roster);
});

test('new arena links and Cup rounds preserve the selected layout and roster',()=>{
  for(const [mode,arena] of [['race','aurora_loops'],['race','pulse_grid'],['drop','diamond_drift'],['drop','pinwheel_pass']]){
    const input={...config,mode,arena};
    assert.deepEqual(session.decode(session.encode(input)),input);
    const cup=session.makeCup(input);
    assert.equal(cup.rounds[0].arena,arena);
    assert.equal(new Set(cup.rounds.map(round=>round.arena)).size,3);
    for(const round of cup.rounds)assert.deepEqual(session.decode(session.encode(round)),round);
  }
});

test('cup only scores actual finishers and cannot award a round twice',()=>{
  const cup=session.makeCup(config);
  assert.equal(session.scoreRound(cup,0,[2,0]),true);
  assert.equal(cup.scores[7],5);assert.equal(cup.scores[6],3);assert.equal(cup.scores[1],0);
  assert.equal(session.scoreRound(cup,0,[3,1,0]),false);assert.equal(cup.scores[12],0);
  assert.equal(session.scoreRound(cup,1,[]),true); // timeout without a finisher awards nobody
  assert.equal(cup.scores.reduce((a,b)=>a+b),8);
  assert.deepEqual(session.cupLeaders(cup),[7]);
});

test('two-racer cups rotate both starts and can share a points tie',()=>{
  const cup=session.makeCup({...config,roster:[6,1]});
  assert.equal(cup.rounds[0].finishTarget,2);
  session.scoreRound(cup,0,[0,1]);session.scoreRound(cup,1,[0,1]);
  assert.deepEqual(session.cupLeaders(cup),[6,1]);
  const empty=session.makeCup(config);assert.deepEqual(session.cupLeaders(empty),[]);
});

test('history filters invalid results, duplicate links and excessive payloads',()=>{
  const race=session.encode(config),record={race,winner:6,seconds:7.2,at:100};
  assert.deepEqual(session.history([null,{},record,record,{...record,winner:99}]),[record]);
  const many=Array.from({length:25},(_,i)=>({...record,race:session.encode({...config,seed:i})}));
  assert.equal(session.history(many).length,20);
});

test('progress records a finish once against the latest stored results',()=>{
  const first={race:session.encode(config),winner:6,seconds:7.2,at:100,won:true};
  const second={...first,race:session.encode({...config,seed:42}),winner:1,at:200,won:false};
  const latest=session.progress({},first);
  assert.equal(latest.races,1);assert.equal(latest.wins,1);
  assert.deepEqual(session.progress(latest,first),latest,'another tab replaying the same race cannot count it twice');
  const combined=session.progress(latest,second);
  assert.equal(combined.races,2);assert.equal(combined.wins,1);
  assert.deepEqual(combined.history.map(entry=>entry.race),[second.race,first.race]);
  assert.deepEqual(session.progress(combined),combined,'saving settings preserves both results');
  assert.deepEqual(session.progress(combined,{...first,race:'broken'}),combined);
  const retried=session.progress(session.progress({},second),first);
  assert.equal(retried.races,2);assert.equal(retried.wins,1);
  assert.deepEqual(retried.history.map(entry=>entry.at),[200,100],'retrying an older unsaved finish preserves chronological history');
});

test('progress sanitizes saved counts and retains history replay protection',()=>{
  const race=session.encode(config),entry={race,winner:6,seconds:7.2,at:100};
  const restored=session.progress({races:2,wins:99,history:[entry],countedRuns:[]});
  assert.equal(restored.wins,2);assert.deepEqual(restored.countedRuns,[race]);
  assert.equal(session.progress(restored,{...entry,won:true}).races,2);
  assert.deepEqual(session.progress({races:Infinity,wins:4}),{races:0,wins:0,history:[],countedRuns:[]});
});

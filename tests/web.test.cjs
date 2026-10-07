const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({console});
vm.runInContext(source.split('const state =')[0]+'\nglobalThis.api={buildRace,stepRace,buildDrop,stepDrop,RACER_POOL,DROP_ARENA_KINDS:Object.keys(DROP_ARENA_SPINNERS),wallBlocks};',context);
const api=context.api;

test('browser script parses',()=>new vm.Script(source));
test('maze racers reach the actual finish line without non-finite coordinates',()=>{
  for(const size of ['s','m','l']) for(const n of [2,4,8]) for(let seed=0;seed<8;seed++){
    const r=api.buildRace(seed,api.RACER_POOL.slice(0,n),size);
    while(!r.winner&&r.step<120*90) api.stepRace(r,r.step/120);
    assert.ok(r.winner,`race ${seed}/${n}/${size} timed out`);
    assert.ok(r.winner.y+r.geo.racerRadius>=r.geo.topBorder+r.rows*r.geo.cell+r.geo.finishDepth*.45);
    for(const p of r.racers) assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));
  }
});
test('every drop arena completes and blades have clearance',()=>{
  for(const kind of api.DROP_ARENA_KINDS) for(const n of [2,4,8]) for(let seed=0;seed<8;seed++){
    const r=api.buildDrop(seed,api.RACER_POOL.slice(0,n),kind);
    for(const p of r.pegs) for(const b of r.blades)
      assert.ok(Math.hypot(p.x-b.x,p.y-b.y)>=b.len/2+r.pegRadius*1.8+r.racerRadius*2.5);
    while(!r.winner&&r.step<120*60) api.stepDrop(r,r.step/120);
    assert.ok(r.winner,`drop ${seed}/${n}/${kind} timed out`);
    for(const p of r.racers) assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));
  }
});

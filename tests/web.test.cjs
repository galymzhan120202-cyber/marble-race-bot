const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'web/game-core.js'),'utf8');
// Evaluate the pure core in this realm: VM proxying Math on every physics
// operation made the old seeded suite needlessly slow. No DOM is involved.
const api=new Function(source+'\nreturn {buildRace,stepRace,buildDrop,stepDrop,drawRace,drawDrop,drawSelectedRacerIndicator,recordFinishCrossings,makeRng,buildMazeLayout,RACER_POOL,MAZE_ARENAS,DROP_ARENAS,DROP_ARENA_SPINNERS,wallBlocks,PHYSICS_HZ};')();
const roster=n=>api.RACER_POOL.slice(0,n);
const finite=r=>r.racers.every(p=>[p.x,p.y,p.vx,p.vy,p.angle].every(Number.isFinite));

test('external browser scripts parse and the page loads both in order',()=>{
  new vm.Script(source);
  new vm.Script(fs.readFileSync(path.join(root,'web/game.js'),'utf8'));
  const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
  assert.ok(html.includes('web/game-core.js'));
  assert.ok(html.indexOf('web/game-core.js')<html.indexOf('web/game.js'));
});

test('every maze layout is connected with distinct, clear starts and an open finish',()=>{
  for(const {id} of api.MAZE_ARENAS) for(const size of ['s','m','l']) for(const n of [2,4,8]) for(let seed=0;seed<12;seed++){
    const r=api.buildRace(seed,roster(n),size,id);
    const label=`${id}/${size}/${n}/${seed}`;
    assert.ok(r.distField.flat().every(d=>Number.isInteger(d)&&d>=0),`disconnected ${label}`);
    assert.equal(new Set(r.spawnCells.map(cell=>cell.join(','))).size,n,`overlapping starts ${label}`);
    for(const p of r.racers) assert.equal(api.wallBlocks(r,[p.x,p.y],[p.x,p.y],r.geo.racerRadius),false,`blocked start ${label}`);
    assert.equal(api.wallBlocks(r,r.geo.cellCenter(...r.finishCell),[r.fzx,r.fzy],r.geo.racerRadius),false,`blocked finish ${label}`);
    assert.ok(r.viewportH<=r.geo.imgH);
  }
});

test('all maze layouts reach the actual finish with 2, 4 and 8 racers',()=>{
  for(const {id} of api.MAZE_ARENAS) for(const size of ['s','m','l']) for(const n of [2,4,8]) for(const seed of [0,1,7,41]){
    const r=api.buildRace(seed,roster(n),size,id);
    while(!r.winner&&r.step<api.PHYSICS_HZ*90){
      api.stepRace(r,r.step/api.PHYSICS_HZ);
      if(r.step%120===0) assert.ok(finite(r),`${id}/${seed}/${n}/${size} became non-finite`);
    }
    assert.ok(r.winner,`race ${id}/${seed}/${n}/${size} timed out`);
    assert.equal(r.resultReason,'finish');
    assert.ok(r.winner.y+r.geo.racerRadius>=r.geo.topBorder+r.rows*r.geo.cell+r.geo.finishDepth*.45);
    assert.ok(finite(r));
    assert.ok(r.cameraY>=0&&r.cameraY<=r.geo.imgH-r.viewportH);
    assert.ok(r.winner.y>=r.cameraY&&r.winner.y<=r.cameraY+r.viewportH,'winner is framed');
  }
});

test('drop layouts leave clear peg gaps, blade sweeps, walls and finish',()=>{
  assert.deepEqual(api.DROP_ARENAS.map(a=>a.id),Object.keys(api.DROP_ARENA_SPINNERS));
  for(const {id} of api.DROP_ARENAS) for(let seed=0;seed<12;seed++){
    const r=api.buildDrop(seed,roster(8),id);
    for(const p of r.pegs){
      assert.ok(p.y+r.pegRadius<r.finishY-r.racerRadius*2);
      for(const b of r.blades) assert.ok(Math.hypot(p.x-b.x,p.y-b.y)>=b.len/2+r.pegRadius*1.8+r.racerRadius*2.5,`${id}: peg in blade sweep`);
    }
    for(const b of r.blades){
      assert.ok(b.x-b.len/2-r.pegRadius*.8>r.left+r.racerRadius*2,`${id}: blade-wall trap`);
      assert.ok(b.x+b.len/2+r.pegRadius*.8<r.right-r.racerRadius*2,`${id}: blade-wall trap`);
    }
    for(let a=0;a<r.pegs.length;a++) for(let b=a+1;b<r.pegs.length;b++){
      const p=r.pegs[a],q=r.pegs[b];
      assert.ok(Math.hypot(p.x-q.x,p.y-q.y)>r.pegRadius*2+r.racerRadius*2,`${id}: gap too narrow`);
    }
  }
});

test('every drop layout completes with 2, 4 and 8 racers',()=>{
  for(const {id} of api.DROP_ARENAS) for(const n of [2,4,8]) for(const seed of [0,1,7,41]){
    const r=api.buildDrop(seed,roster(n),id);
    while(!r.winner&&r.step<api.PHYSICS_HZ*60){
      api.stepDrop(r,r.step/api.PHYSICS_HZ);
      if(r.step%120===0) assert.ok(finite(r),`${id}/${seed}/${n} became non-finite`);
    }
    assert.ok(r.winner,`drop ${id}/${seed}/${n} timed out`);
    assert.equal(r.resultReason,'finish');
    assert.ok(r.winner.y+r.racerRadius>=r.finishY);
    assert.ok(finite(r));
  }
});

test('drop winners encounter real obstacles and no straight side lane bypasses the course',()=>{
  for(const {id} of api.DROP_ARENAS) for(const n of [4,6,8]) for(let seed=0;seed<=20;seed++){
    const r=api.buildDrop(seed,roster(n),id),label=`${id}/${seed}/${n}`;
    const reach=r.racerRadius+r.pegRadius;
    const intervals=r.pegs.map(p=>[p.x-reach,p.x+reach]).sort((a,b)=>a[0]-b[0]);
    let covered=r.left+r.racerRadius;
    for(const [start,end] of intervals){
      if(end<covered) continue;
      assert.ok(start<=covered,`${label}: unobstructed vertical side lane`);
      covered=Math.max(covered,end);
    }
    assert.ok(covered>=r.right-r.racerRadius,`${label}: open right edge`);
    while(!r.winner&&r.step<api.PHYSICS_HZ*60) api.stepDrop(r,r.step/api.PHYSICS_HZ);
    assert.ok(r.winner,`${label}: no finish`);
    // These are unique pegs/blades registered by collision response,
    // excluding rails and other racers; duration is not the criterion.
    assert.ok(r.winner.obstacleContacts.size>=2,`${label}: winner skipped the obstacle course`);
  }
});

test('camera focus leaves seeded physics unchanged and stays inside the world',()=>{
  for(const kind of ['race','drop']){
    const build=kind==='race'?api.buildRace:api.buildDrop;
    const step=kind==='race'?api.stepRace:api.stepDrop;
    const args=kind==='race'?[314,roster(8),'l','crossroads']:[314,roster(8),'orbit_run'];
    const a=build(...args),b=build(...args);
    b.followYou=true;b.youIdx=7;
    for(let i=0;i<720&&!a.winner;i++){step(a,i/120);step(b,i/120);}
    assert.deepEqual(a.racers.map(r=>[r.x,r.y,r.vx,r.vy]),b.racers.map(r=>[r.x,r.y,r.vx,r.vy]));
    for(const r of [a,b]) assert.ok(r.cameraY>=0&&r.cameraY<=(r.geo?r.geo.imgH:r.worldH)-r.viewportH);
  }
});

test('unknown layout IDs safely use the original arenas',()=>{
  assert.equal(api.buildRace(1,roster(4),'m','missing').arenaKind,'classic');
  assert.equal(api.buildDrop(1,roster(4),'missing').arenaKind,'classic_plinko');
});

function finishFixture(kind,distances){
  const sim=kind==='race'?api.buildRace(7,roster(distances.length),'s'):api.buildDrop(7,roster(distances.length));
  const radius=sim.geo?sim.geo.racerRadius:sim.racerRadius;
  const line=sim.geo?sim.geo.topBorder+sim.rows*sim.geo.cell+sim.geo.finishDepth*.45:sim.finishY;
  const width=sim.geo?sim.geo.w:sim.stageW;
  sim.racers.forEach((r,i)=>{
    r.x=width*(i+1)/(distances.length+1);r.y=line-radius-distances[i];r.vx=0;r.vy=1200;
    if(sim.geo){r.lastCell=[...sim.finishCell];r.target=[r.x,sim.fzy];}
  });
  return sim;
}

test('same-step finishes use the crossing time in both modes, not roster priority',()=>{
  for(const kind of ['race','drop']) for(const distances of [[6,1],[1,6]]){
    const sim=finishFixture(kind,distances),step=kind==='race'?api.stepRace:api.stepDrop;
    step(sim,0);
    const first=distances.indexOf(1);
    assert.equal(sim.winner.idx,first,`${kind}: later crossing incorrectly won`);
    assert.deepEqual(sim.finishOrder,[first,1-first]);
    assert.ok(sim.racers[first].finishStep<sim.racers[1-first].finishStep);
    assert.ok(sim.racers.every(r=>r.finishStep>=0&&r.finishStep<=1));
    assert.equal(sim.complete,true);
    const snapshot=JSON.stringify(sim.racers),endStep=sim.step;
    step(sim,1/120);
    assert.equal(sim.step,endStep);assert.equal(JSON.stringify(sim.racers),snapshot,'completed result moved');
  }
});

test('exact crossing ties are deterministic',()=>{
  const sim=finishFixture('drop',[2,2]),active=[...sim.racers];
  const prior=new Map(active.map(r=>[r,98]));
  active.forEach(r=>r.y=102);sim.step=10;sim.finishTarget=2;
  api.recordFinishCrossings(sim,active,prior,0,100);
  assert.deepEqual(sim.finishOrder,[0,1]);
  assert.deepEqual(sim.racers.map(r=>r.finishStep),[9.5,9.5]);
  assert.equal(sim.complete,true);
});

test('podium mode continues after the winner, follows contenders and freezes only at its target',()=>{
  for(const kind of ['race','drop']){
    const sim=finishFixture(kind,[1,450,700]),step=kind==='race'?api.stepRace:api.stepDrop;
    sim.finishTarget=3;sim.followYou=true;sim.youIdx=0;
    const worldH=sim.geo?sim.geo.imgH:sim.worldH;
    sim.viewportH=400;sim.cameraY=0;
    step(sim,0);
    assert.equal(sim.winner.idx,0);assert.equal(sim.complete,false);
    assert.deepEqual(sim.finishOrder,[0]);
    const winnerPose=[sim.winner.x,sim.winner.y,sim.winner.angle];
    const lockedCamera=Math.max(0,Math.min(worldH-sim.viewportH,sim.winner.y-sim.viewportH*.42));
    assert.ok(sim.cameraY<lockedCamera,'camera prematurely locked on the first finisher');
    const radius=sim.geo?sim.geo.racerRadius:sim.racerRadius;
    const line=sim.geo?sim.geo.topBorder+sim.rows*sim.geo.cell+sim.geo.finishDepth*.45:sim.finishY;
    sim.racers[2].y=line-radius-1;sim.racers[2].vy=1200;
    sim.racers[1].y=line-radius-6;sim.racers[1].vy=1200;
    step(sim,1/120);
    assert.equal(sim.complete,true);assert.equal(sim.winner.idx,0);
    assert.deepEqual(sim.finishOrder,[0,2,1]);
    assert.deepEqual([sim.winner.x,sim.winner.y,sim.winner.angle],winnerPose,'finished racer moved while podium filled');
    assert.equal(sim.cameraY,lockedCamera);
  }
});

test('all layouts produce actual podiums with varied characters and field sizes',()=>{
  for(const kind of ['race','drop']) for(const arena of kind==='race'?api.MAZE_ARENAS:api.DROP_ARENAS)
    for(const n of [2,4,8]) for(const seed of [0,7,41]){
      const varied=Array.from({length:n},(_,i)=>api.RACER_POOL[(i*3+seed+n)%api.RACER_POOL.length]);
      const sim=kind==='race'?api.buildRace(seed,varied,'m',arena.id):api.buildDrop(seed,varied,arena.id);
      const step=kind==='race'?api.stepRace:api.stepDrop;
      sim.finishTarget=Math.min(3,n);
      while(!sim.complete&&sim.step<(kind==='race'?90:60)*api.PHYSICS_HZ) step(sim,sim.step/api.PHYSICS_HZ);
      const label=`${kind}/${arena.id}/${n}/${seed}`;
      assert.equal(sim.complete,true,`${label}: podium timed out`);
      assert.ok(finite(sim));assert.ok(sim.finishOrder.length>=sim.finishTarget);
      assert.equal(new Set(sim.finishOrder).size,sim.finishOrder.length);
      assert.equal(sim.finishOrder[0],sim.winner.idx);
      assert.ok(sim.finishOrder.every(idx=>sim.racers[idx].finished&&!sim.racers[idx].active));
      const steps=sim.finishOrder.map(idx=>sim.racers[idx].finishStep);
      assert.deepEqual(steps,[...steps].sort((a,b)=>a-b));
    }
});

test('32-bit maze seeds retain their exact low bits',()=>{
  for(const seed of [3000000001,4294967295]){
    const sim=api.buildRace(seed,roster(4),'m','classic');
    const mixed=Number((BigInt(seed)*2654435761n)&0xffffffffn);
    const rng=api.makeRng(mixed),expected=api.buildMazeLayout(sim.cols,sim.rows,rng,'classic');
    assert.deepEqual(sim.openRight,expected.openRight);
    assert.deepEqual(sim.openDown,expected.openDown);
    assert.equal(sim.finishCol,rng.int(sim.cols));
  }
});

test('selected racer indicator follows the live viewport and is absent when visible',()=>{
  const texts=[],ctx=new Proxy({}, {get:(_,key)=>{
    if(key==='fillText') return text=>texts.push(text);
    if(key==='createRadialGradient') return ()=>({addColorStop(){}});
    return ()=>{};
  }});
  for(const kind of ['race','drop']){
    const sim=kind==='race'?api.buildRace(7,roster(4),'m'):api.buildDrop(7,roster(4));
    sim.cameraY=400;sim.viewportH=820;
    for(const [y,expected] of [[100,'↑'],[1300,'↓'],[600,null]]){
      sim.racers[2].y=y;texts.length=0;
      (kind==='race'?api.drawRace:api.drawDrop)(ctx,sim,{},0,2);
      assert.equal(texts.length,expected?1:0);
      if(expected) assert.equal(texts[0],`${expected} YOU · Cocoa`);
    }
  }
});

test('short viewports keep the followed racer visible without changing seeded finishes',()=>{
  for(const {id} of api.DROP_ARENAS) for(const seed of [0,7,0xffffffff]) for(const followYou of [false,true]){
    const short=api.buildDrop(seed,roster(8),id),normal=api.buildDrop(seed,roster(8),id);
    short.viewportH=360;short.followYou=followYou;short.youIdx=7;
    short.finishTarget=3;normal.finishTarget=3;
    while(!short.complete&&short.step<api.PHYSICS_HZ*60){
      api.stepDrop(short,short.step/api.PHYSICS_HZ);
      api.stepDrop(normal,normal.step/api.PHYSICS_HZ);
      const active=short.racers.filter(r=>r.active);
      const followed=short.complete?short.winner:followYou&&short.racers[7].active?short.racers[7]:active.reduce((best,r)=>r.y>best.y?r:best);
      assert.ok(followed.y-short.racerRadius>=short.cameraY,`${id}/${seed}: followed racer left the top`);
      assert.ok(followed.y+short.racerRadius<=short.cameraY+short.viewportH,`${id}/${seed}: followed racer fell below the viewport`);
      assert.ok(short.cameraY>=0&&short.cameraY<=short.worldH-short.viewportH);
    }
    assert.equal(short.complete,true);
    assert.deepEqual(short.finishOrder,normal.finishOrder);
    assert.deepEqual(short.racers.map(r=>[r.x,r.y,r.vx,r.vy,r.angle,r.finishStep]),normal.racers.map(r=>[r.x,r.y,r.vx,r.vy,r.angle,r.finishStep]));
  }
});

test('all maze sizes keep camera targets framed across edge seeds and leader changes',()=>{
  for(const {id} of api.MAZE_ARENAS) for(const size of ['s','m','l']) for(const seed of [0x80000000,0xffffffff]){
    const sim=api.buildRace(seed,roster(8),size,id);sim.viewportH=360;sim.finishTarget=3;
    while(!sim.complete&&sim.step<api.PHYSICS_HZ*90){
      api.stepRace(sim,sim.step/api.PHYSICS_HZ);
      const active=sim.racers.filter(r=>r.active);
      const followed=sim.complete?sim.winner:active.reduce((best,r)=>sim.distField[r.lastCell[0]][r.lastCell[1]]<sim.distField[best.lastCell[0]][best.lastCell[1]]?r:best);
      assert.ok(followed.y-sim.geo.racerRadius>=sim.cameraY,`${id}/${size}/${seed}: target above frame`);
      assert.ok(followed.y+sim.geo.racerRadius<=sim.cameraY+sim.viewportH,`${id}/${size}/${seed}: target below frame`);
    }
    assert.equal(sim.complete,true);
  }
});

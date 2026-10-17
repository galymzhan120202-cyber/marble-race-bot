const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'web/game-core.js'),'utf8');
// Evaluate the pure core in this realm: VM proxying Math on every physics
// operation made the old seeded suite needlessly slow. No DOM is involved.
const api=new Function(source+'\nreturn {buildRace,stepRace,buildDrop,stepDrop,RACER_POOL,MAZE_ARENAS,DROP_ARENAS,DROP_ARENA_SPINNERS,wallBlocks,PHYSICS_HZ};')();
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

const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=['web/game-core.js','web/game-presentation.js'].map(file=>fs.readFileSync(path.join(root,file),'utf8')).join('\n');
const api=new Function(source+'\nreturn {RacePresentation,buildRace,buildDrop,RACER_POOL,registerImpact,racerMotion,trailMetrics,drawImpacts,renderView};')();
const roster=api.RACER_POOL.slice(0,8);

test('collision springs follow the normal, rebound, settle and respect reduced motion',()=>{
  const sim=api.buildDrop(7,roster),racer=sim.racers[0];
  racer.vx=racer.vy=0;
  api.registerImpact(sim,racer,1,racer.x,racer.y,0,-1,760,'peg');
  const compressed=api.racerMotion(sim,racer,1.01),rebound=api.racerMotion(sim,racer,1.13),settled=api.racerMotion(sim,racer,1.5);
  assert.ok(compressed.sx<1&&compressed.sy>1);
  assert.equal(compressed.axis,-Math.PI/2);
  assert.ok(rebound.sx>1&&rebound.sy<1,'spring overshoots instead of abruptly resetting');
  assert.equal(settled.sx,1);assert.equal(settled.sy,1);
  sim.reducedMotion=true;
  assert.deepEqual(api.racerMotion(sim,racer,1.01),{sx:1,sy:1,axis:0,offset:0});
});

test('repeated resting contacts cannot restart the spring or grow effect history without bound',()=>{
  const sim=api.buildDrop(7,roster),racer=sim.racers[0];
  api.registerImpact(sim,racer,1,0,0,1,0,700,'wall');
  for(let i=0;i<100;i++)api.registerImpact(sim,racer,1.01,0,0,1,0,200,'wall');
  assert.equal(sim.bumps.length,1);assert.equal(racer.impact.born,1);
  for(let i=0;i<1000;i++)api.registerImpact(sim,racer,2+i*.06,0,0,1,0,700,'wall');
  assert.ok(sim.bumps.length<=64);
  assert.ok(sim.bumps.every(b=>Number.isFinite(b.speed)&&Number.isFinite(b.nx)&&Number.isFinite(b.ny)));
});

test('speed increases the trail while the particle draw budget stays bounded under load',()=>{
  const sim=api.buildDrop(7,roster),racer=sim.racers[0];
  racer.vx=0;racer.vy=50;const slow=api.trailMetrics(sim,racer);
  racer.vy=900;const fast=api.trailMetrics(sim,racer);
  assert.ok(fast.opacity>slow.opacity&&fast.segments>slow.segments);
  sim.bumps=Array.from({length:64},(_,i)=>({x:i,y:100,born:1,intensity:1,nx:0,ny:-1,kind:'peg'}));
  let strokes=0;
  const ctx=new Proxy({}, {get:(_,key)=>key==='stroke'?()=>strokes++:()=>{}});
  sim.effectsQuality=0;api.drawImpacts(ctx,sim,20,1.1);const economical=strokes;
  strokes=0;sim.effectsQuality=2;api.drawImpacts(ctx,sim,20,1.1);
  assert.ok(strokes>economical&&economical<=12&&strokes<=48);
  strokes=0;sim.reducedMotion=true;api.drawImpacts(ctx,sim,20,1.1);assert.equal(strokes,0);
});

test('cinematic crops remain inside the course and retain the selected racer at the edges',()=>{
  for(const kind of ['race','drop']){
    const sim=kind==='race'?api.buildRace(41,roster,'s','open_rooms'):api.buildDrop(41,roster);
    sim.viewportH=360;sim.youIdx=3;sim.followYou=true;sim.step=600;
    const w=sim.geo?.w??sim.stageW,h=sim.geo?.imgH??sim.worldH,r=sim.geo?.racerRadius??sim.racerRadius;
    const target=sim.racers[3];
    for(const x of [r*2,w-r*2])for(const y of [r*2,h-r*3]){
      target.x=x;target.y=y;
      if(sim.geo)target.lastCell=[sim.rows-1,sim.finishCol];
      sim.cameraY=Math.max(0,Math.min(h-sim.viewportH,y-sim.viewportH*.42));
      for(let i=0;i<90;i++)api.RacePresentation.updateCamera(sim,1/60);
      const view=api.renderView(sim);
      assert.ok(view.zoom>1&&view.zoom<=1.12);
      assert.ok(view.x>=0&&view.y>=0&&view.x+view.w<=w+.001&&view.y+view.h<=h+.001);
      assert.ok(x-r>=view.x&&x+r<=view.x+view.w&&y-r>=view.y&&y+r<=view.y+view.h);
      assert.equal(view.target,3,'manual follow must not be stolen by a dramatic event');
    }
    sim.reducedMotion=true;api.RacePresentation.updateCamera(sim,1/60);
    assert.equal(api.renderView(sim).zoom,1);
  }
});

test('all sixteen victory gestures differ, end at rest and fit inside a tied-champion tile',()=>{
  const signatures=new Set();
  for(const racer of api.RACER_POOL){
    signatures.add(JSON.stringify([.35,.8,1.4].map(t=>api.RacePresentation.victoryPose(racer.name,t))));
    for(let frame=0;frame<=210;frame++){
      const t=frame/60,{pose,x,y,size}=api.RacePresentation.victoryLayout(racer.name,t,40);
      assert.ok(Object.values(pose).every(Number.isFinite));
      assert.ok(pose.sx>.7&&pose.sy>.7);
      const c=Math.abs(Math.cos(pose.angle)),s=Math.abs(Math.sin(pose.angle));
      assert.ok(Math.abs(x)+size/2*(c*pose.sx+s*pose.sy)<=20);
      assert.ok(Math.abs(y)+size/2*(s*pose.sx+c*pose.sy)<=20);
    }
    assert.deepEqual(api.RacePresentation.victoryPose(racer.name,4),{x:0,y:0,angle:0,sx:1,sy:1});
  }
  assert.equal(signatures.size,16);
});

test('adaptive quality responds to sustained work, avoids frame spikes and caps high-DPI buffers',()=>{
  const budget=api.RacePresentation.createFrameBudget(false);
  for(let i=0;i<10;i++)budget.sample(110,60);
  assert.equal(budget.tier,2,'isolated stalls cannot immediately reduce quality');
  for(let i=0;i<140;i++)budget.sample(35,18);
  assert.ok(budget.tier<2);
  const low=budget.tier;
  for(let i=0;i<500;i++)budget.sample(16.7,3);
  assert.ok(budget.tier>low,'quality can recover after sustained headroom');
  const phone=api.RacePresentation.createFrameBudget(true);
  const dpr=phone.rasterScale(390,700,3);
  assert.ok(dpr<=1.5&&390*700*dpr*dpr<=phone.settings.pixels);
  assert.ok(phone.rasterScale(3000,2000,3)**2*3000*2000<=phone.settings.pixels+1);
});

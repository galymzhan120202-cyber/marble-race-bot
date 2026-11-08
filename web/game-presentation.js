"use strict";

// Presentation owns its own clocks. Nothing here consumes the race's RNG,
// changes a score, or alters the fixed-step simulation.
const RacePresentation = (() => {
  let reduced = true;
  const animations = new Set();
  const rowAnimations = new WeakMap();
  const directors = new WeakMap();
  const maps = new WeakMap();
  let winnerPlayer=null,suspended=false;
  const qualityLevels=[
    {dpr:1.25,pixels:650000,mapInterval:170},
    {dpr:1.5,pixels:1100000,mapInterval:125},
    {dpr:2,pixels:2200000,mapInterval:85},
  ];
  function createFrameBudget(coarse=false){
    let tier=coarse?1:2,slow=0,fast=0,elapsed=0,changedAt=-4000,average=16.7;
    return {
      get tier(){return tier;},get settings(){return qualityLevels[tier];},
      sample(interval,cost){
        // Ignore tab switches, debugging pauses and startup stalls.
        if(interval<=0||interval>120)return false;
        elapsed+=interval;average+=(interval-average)*.08;
        const loaded=average>22&&cost>9;
        slow=loaded?slow+1:Math.max(0,slow-2);
        fast=average<19&&cost<6?fast+1:0;
        if(elapsed-changedAt<3500)return false;
        const next=slow>=30?Math.max(0,tier-1):fast>=240?Math.min(coarse?1:2,tier+1):tier;
        if(next===tier)return false;
        tier=next;changedAt=elapsed;slow=fast=0;return true;
      },
      rasterScale(width,height,dpr){
        const level=qualityLevels[tier];
        return Math.min(dpr||1,level.dpr,Math.sqrt(level.pixels/Math.max(1,width*height)));
      },
      snapshot:()=>({tier,average,slow,fast}),
    };
  }
  function resetCamera(sim){directors.delete(sim);sim.cameraView=null;}
  function updateCamera(sim,dt){
    if(sim.reducedMotion){resetCamera(sim);return;}
    const w=sim.geo?.w??sim.stageW,h=sim.viewportH||sim.geo.imgH,worldH=sim.geo?.imgH??sim.worldH;
    let director=directors.get(sim);
    if(!director){director={zoom:1,centerX:w/2,leader:null,leadAt:-10};directors.set(sim,director);}
    const distance=r=>sim.geo?sim.distField[r.lastCell[0]][r.lastCell[1]]:Math.max(0,sim.finishY-r.y);
    const active=sim.racers.filter(r=>r.active).sort((a,b)=>distance(a)-distance(b)||a.idx-b.idx);
    const leader=active[0]||sim.winner||sim.racers[0],selected=sim.racers[sim.youIdx];
    const target=sim.complete&&sim.winner?sim.winner:sim.followYou&&selected?.active?selected:leader;
    const now=sim.step*DT;
    if(director.leader!==null&&director.leader!==leader.idx)director.leadAt=now;
    director.leader=leader.idx;
    const remaining=distance(target),nearFinish=sim.geo?remaining<=3:remaining<h*.6;
    const closeRace=active.length>1&&Math.abs(distance(active[0])-distance(active[1]))<(sim.geo?2:100);
    const impact=target.impact,hit=impact&&now-impact.born<.25&&impact.intensity>.55;
    const mode=nearFinish?'finish':now-director.leadAt<1.1?'lead-change':hit?'impact':closeRace?'close-race':'cruise';
    const wanted=mode==='finish'?1.12:mode==='lead-change'?1.07:mode==='impact'?1.045:mode==='close-race'?1.035:1;
    const blend=1-Math.exp(-Math.min(.05,Math.max(0,dt))*4.5),pose=renderPose(sim,target);
    director.zoom+=(wanted-director.zoom)*blend;
    director.centerX+=(pose.x-director.centerX)*blend;
    const zoom=director.zoom,viewW=w/zoom,viewH=h/zoom,radius=sim.geo?.racerRadius??sim.racerRadius;
    const margin=Math.min(viewW/4,viewH/4,radius*1.9);
    let x=director.centerX-viewW/2,y=renderCamera(sim)+(h-viewH)*.42;
    // A cinematic crop must retain the camera's chosen racer at every edge.
    x=motionClamp(x,pose.x-viewW+margin,pose.x-margin);
    y=motionClamp(y,pose.y-viewH+margin,pose.y-margin);
    sim.cameraView={x:motionClamp(x,0,w-viewW),y:motionClamp(y,0,worldH-viewH),w:viewW,h:viewH,zoom,mode,target:target.idx};
  }
  const victoryStyles={
    Blacky:['bow',8,1.2],Sunny:['twirl',13,1],Cocoa:['toast',11,1.4],Pine:['toast',8,1.1],
    Tango:['bow',11,1.6],Ghost:['float',15,.8],Sky:['float',11,.65],Rosy:['twirl',9,2],
    Cherry:['sway',7,1.9],Minty:['jelly',10,1.7],Grape:['orbit',12,.9],Coral:['jelly',7,2.2],
    Lime:['hop',17,1.6],Slate:['robot',7,1.4],Amber:['flutter',12,1.8],Ruby:['stomp',10,1.05],
  };
  function victoryPose(name,time){
    const pose={x:0,y:0,angle:0,sx:1,sy:1};
    if(time<=0||time>=3.2)return pose;
    const [move,amplitude,frequency]=victoryStyles[name]||['hop',10,1];
    const envelope=Math.min(1,time/.18)*Math.min(1,(3.2-time)/.65),phase=time*frequency*Math.PI*2;
    if(move==='float'){pose.y=-amplitude*(.65+.35*Math.sin(phase));pose.angle=Math.sin(phase)*.12;}
    if(move==='twirl'){
      const t=motionClamp((time-.15)/1.5,0,1);pose.angle=frequency*Math.PI*2*(t*t*(3-2*t));
      pose.y=-amplitude*Math.sin(Math.PI*t);pose.sx=1+Math.sin(phase)*.04*envelope;
    }
    if(move==='toast'){pose.y=-amplitude*Math.min(1,time/.35);pose.angle=Math.sin(phase)*.15;}
    if(move==='bow'){pose.angle=Math.sin(phase)*.24;pose.y=Math.abs(Math.sin(phase))*4;pose.x=Math.sin(phase)*amplitude*.35;}
    if(move==='sway'){pose.x=Math.sin(phase)*amplitude;pose.angle=Math.sin(phase+.4)*.2;pose.y=-Math.abs(Math.sin(phase))*5;}
    if(move==='jelly'){pose.sx=1+Math.sin(phase)*.17*envelope;pose.y=-Math.abs(Math.sin(phase*.5))*amplitude;}
    if(move==='orbit'){pose.x=Math.sin(phase)*amplitude*.65;pose.y=-amplitude*(.5+.5*Math.cos(phase));pose.angle=Math.sin(phase)*.18;}
    if(move==='hop'||move==='stomp'){
      const jump=Math.max(0,Math.sin(phase));pose.y=-jump*amplitude;
      pose.sx=1+(.13*Math.max(0,-Math.sin(phase))-.06*jump)*envelope;
      pose.angle=Math.sin(phase*.5)*(move==='stomp'?.08:.18);
    }
    if(move==='robot'){pose.x=Math.sign(Math.sin(phase))*amplitude*.35;pose.angle=Math.sign(Math.cos(phase))*.12;pose.y=-Math.max(0,Math.sin(phase))*5;}
    if(move==='flutter'){pose.x=Math.sin(phase)*4;pose.y=-amplitude*(.6+.4*Math.sin(phase));pose.angle=Math.sin(phase*2)*.16;}
    pose.x*=envelope;pose.y*=envelope;
    if(move!=='twirl')pose.angle*=envelope;
    pose.sy=1/pose.sx;return pose;
  }
  function victoryLayout(name,time,cell=120){
    const pose=victoryPose(name,time),unit=cell/120;
    const x=pose.x*unit,y=cell*.04+pose.y*unit;
    const c=Math.abs(Math.cos(pose.angle)),s=Math.abs(Math.sin(pose.angle));
    const size=Math.min(cell*.74,(cell-2*Math.abs(x)-8*unit)/(c*pose.sx+s*pose.sy),
      (cell-2*Math.abs(y)-8*unit)/(s*pose.sx+c*pose.sy));
    return {pose,x,y,size};
  }
  function paintWinner(){
    if(!winnerPlayer)return;
    const {canvas,portraits,selected,elapsed}=winnerPlayer,ctx=canvas.getContext('2d');
    ctx.setTransform(canvas.width/120,0,0,canvas.height/120,0,0);ctx.clearRect(0,0,120,120);
    const columns=Math.ceil(Math.sqrt(portraits.length)),cell=120/(columns||1),rows=Math.ceil(portraits.length/(columns||1));
    portraits.forEach((portrait,i)=>{
      const row=Math.floor(i/columns),count=Math.min(columns,portraits.length-row*columns);
      const layout=victoryLayout(portrait.name,reduced?3.2:elapsed,cell),{pose,size}=layout;
      const x=(120-count*cell)/2+(i%columns+.5)*cell,y=(120-rows*cell)/2+(row+.5)*cell;
      ctx.save();ctx.translate(x,y);
      ctx.fillStyle='rgba(0,0,0,.18)';ctx.beginPath();ctx.ellipse(0,cell*.36,cell*.28*(1+pose.y/50),cell*.055,0,0,Math.PI*2);ctx.fill();
      ctx.translate(layout.x,layout.y);ctx.rotate(pose.angle);ctx.scale(pose.sx,pose.sy);
      ctx.translate(-size/2,-size/2);drawRacerFace(ctx,size,portrait.color,0,portrait.name===selected,portrait.name);ctx.restore();
    });
  }
  function queueWinner(){
    if(!winnerPlayer||winnerPlayer.raf!==null||suspended||document.hidden||reduced||winnerPlayer.elapsed>=3.2)return;
    winnerPlayer.last=performance.now();winnerPlayer.raf=requestAnimationFrame(tickWinner);
  }
  function tickWinner(now){
    if(!winnerPlayer)return;
    winnerPlayer.raf=null;
    if(suspended||document.hidden||reduced)return;
    winnerPlayer.elapsed=Math.min(3.2,winnerPlayer.elapsed+Math.min(.05,(now-winnerPlayer.last)/1000));
    paintWinner();queueWinner();
  }
  function stopWinner(){if(winnerPlayer?.raf!==null&&winnerPlayer)cancelAnimationFrame(winnerPlayer.raf);winnerPlayer=null;}
  function presentWinner(canvas,portraits,selected,play){
    stopWinner();canvas.width=canvas.height=240;canvas.hidden=portraits.length===0;
    canvas.dataset.gesture=portraits.map(p=>victoryStyles[p.name]?.[0]||'hop').join(' ');
    winnerPlayer={canvas,portraits,selected,elapsed:play&&!reduced?0:3.2,raf:null,last:0};
    paintWinner();queueWinner();
  }
  function suspendWinner(value){
    suspended=value;
    if(winnerPlayer?.raf!==null&&winnerPlayer){cancelAnimationFrame(winnerPlayer.raf);winnerPlayer.raf=null;}
    if(!value)queueWinner();
  }
  function winnerStatus(){return {running:winnerPlayer?.raf!=null,elapsed:winnerPlayer?.elapsed??3.2,names:winnerPlayer?.portraits.map(p=>p.name)||[]};}
  function animate(element, frames, options) {
    if (reduced || !element.animate) return null;
    const animation = element.animate(frames, options);
    animations.add(animation);
    const done = () => animations.delete(animation);
    animation.finished.then(done, done);
    return animation;
  }
  function cancelAnimations() {
    for (const animation of animations) animation.cancel();
    animations.clear();
  }
  function setReduced(value) {
    reduced = value;
    document.body.dataset.motion = value ? "reduced" : "full";
    if (value) {
      cancelAnimations();clearCelebration();
      if(winnerPlayer){if(winnerPlayer.raf!==null)cancelAnimationFrame(winnerPlayer.raf);winnerPlayer.raf=null;winnerPlayer.elapsed=3.2;paintWinner();}
    }
  }
  function countdown(element) {
    for (const animation of element.getAnimations()) animation.cancel();
    animate(element, [{opacity:.3,transform:"scale(.8)"},{opacity:1,transform:"scale(1.06)",offset:.5},{opacity:1,transform:"scale(1)"}],
      {duration:420,easing:"cubic-bezier(.2,.75,.2,1)"});
  }
  function reorderRows(rows, previousBounds) {
    // Cancel, measure, then animate in batches: interleaving these operations
    // used to force a layout pass for every row on slower phones.
    for(const row of rows)rowAnimations.get(row)?.cancel();
    const finalBounds=new Map(rows.map(row=>[row,row.getBoundingClientRect()]));
    for(const row of rows){
      const before=previousBounds.get(row),after=finalBounds.get(row);
      const dx=before.left-after.left,dy=before.top-after.top,distance=Math.hypot(dx,dy);
      if(distance<2||distance>600)continue;
      const animation=animate(row,[{transform:`translate(${dx}px,${dy}px)`},{transform:'translate(0,0)'}],
        {duration:280,easing:'cubic-bezier(.2,.75,.2,1)'});
      if(animation)rowAnimations.set(row,animation);
    }
  }
  function clearCelebration() { document.getElementById("celebration").replaceChildren(); }
  function celebrate(quality=2) {
    clearCelebration();
    if (reduced) return;
    const layer = document.getElementById("celebration");
    const colors = ["#d4f779","#b6a2f3","#8ee1cf","#f0c58b","#f6f5ed"];
    for (let i = 0; i < [16,24,30][quality]; i++) {
      const particle = document.createElement("i");
      particle.className = "confetti";
      particle.style.setProperty("--x", ((i * 37) % 100) + "%");
      particle.style.setProperty("--color", colors[i % colors.length]);
      particle.style.setProperty("--delay", (i % 7) * .06 + "s");
      particle.style.setProperty("--duration", (1.8 + i % 5 * .22) + "s");
      particle.style.setProperty("--drift", ((i * 53) % 180 - 90) + "px");
      particle.style.setProperty("--spin", ((i % 2 ? 1 : -1) * (180 + i * 19)) + "deg");
      particle.addEventListener("animationend", () => particle.remove(), {once:true});
      layer.append(particle);
    }
  }
  function drawMap(canvas, sim) {
    if (!sim?.offscreen) return;
    const ctx = canvas.getContext("2d"), w = sim.offscreen.width, h = sim.offscreen.height;
    const scale = Math.min((canvas.width-30)/h, (canvas.height-30)/w);
    let cached=maps.get(sim);
    if(!cached||cached.source!==sim.offscreen||cached.canvas.width!==canvas.width||cached.canvas.height!==canvas.height){
      const layer=document.createElement('canvas');layer.width=canvas.width;layer.height=canvas.height;
      const bg=layer.getContext('2d');bg.translate(canvas.width/2,canvas.height/2);bg.rotate(-Math.PI/2);
      bg.scale(scale,scale);bg.translate(-w/2,-h/2);bg.globalAlpha=.65;bg.drawImage(sim.offscreen,0,0);
      cached={canvas:layer,source:sim.offscreen};maps.set(sim,cached);
    }
    ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(cached.canvas,0,0);
    ctx.save();ctx.translate(canvas.width/2,canvas.height/2);ctx.rotate(-Math.PI/2);
    ctx.scale(scale,scale);ctx.translate(-w/2,-h/2);
    const view=renderView(sim);
    ctx.fillStyle="rgba(212,247,121,.06)";ctx.fillRect(view.x,view.y,view.w,view.h);
    ctx.strokeStyle="#e5f0d0";ctx.lineWidth=2/scale;
    ctx.strokeRect(view.x+2/scale,view.y+1/scale,view.w-4/scale,Math.max(1,view.h-2/scale));
    for (const racer of sim.racers) {
      ctx.beginPath();ctx.arc(racer.x,racer.y,(racer.idx===sim.youIdx?7:5)/scale,0,Math.PI*2);
      ctx.fillStyle=racer.idx===sim.youIdx?"#d4f779":rgb(racer.color);ctx.fill();
      ctx.strokeStyle="#111722";ctx.lineWidth=2/scale;ctx.stroke();
    }
    ctx.restore();
  }
  function createPreview(canvas, button, caption) {
    const ctx = canvas.getContext("2d");
    const source = document.createElement("canvas");
    let sim, seed=137, raf=null, last=0, accumulator=0, hold=0;
    let active=false, visible=true, manuallyPaused=false, lastCaption=-1;
    function build() {
      sim=buildRace(seed++,[6,1,7,9,5,11].map(i=>({...RACER_POOL[i]})),"s","open_rooms");
      sim.youIdx=0;sim.effectsQuality=1;sim.viewportH=sim.geo.w*canvas.height/canvas.width;
      source.width=sim.geo.w;source.height=sim.geo.imgH;
      drawMazeBackground(source.getContext("2d"),sim);
      // Show an interesting static frame as well when motion is reduced.
      for(let i=0;i<180&&!sim.complete;i++)stepRace(sim,sim.step*DT);
      accumulator=0;hold=0;lastCaption=-1;
    }
    function paint() {
      if (!sim) build();
      sim.reducedMotion=reduced;
      sim.renderAlpha=sim.complete||reduced?1:accumulator/DT;
      ctx.setTransform(canvas.width/sim.geo.w,0,0,canvas.height/sim.viewportH,0,0);
      drawRace(ctx,sim,source,sim.step*DT,0);
      if(lastCaption<0||sim.step-lastCaption>36||sim.complete){
        const leader=sim.winner||sim.racers.slice().sort((a,b)=>sim.distField[a.lastCell[0]][a.lastCell[1]]-sim.distField[b.lastCell[0]][b.lastCell[1]])[0];
        caption.textContent=leader.name+(sim.complete?" wins the warm-up!":" leads the warm-up");
        lastCaption=sim.step;
      }
    }
    function tick(now) {
      raf=null;
      if(!active||!visible||document.hidden||reduced||manuallyPaused)return;
      const elapsed=Math.min(.05,Math.max(0,(now-last)/1000));last=now;
      if(sim.complete){hold+=elapsed;if(hold>1.5)build();}
      else{
        accumulator+=elapsed;
        while(accumulator>=DT&&!sim.complete){stepRace(sim,sim.step*DT);accumulator-=DT;}
        if(sim.step>120*45)build();
      }
      updateCamera(sim,elapsed);paint();raf=requestAnimationFrame(tick);
    }
    function sync(isActive=active) {
      active=isActive;
      if(raf!==null)cancelAnimationFrame(raf);
      raf=null;
      const paused=reduced||manuallyPaused;
      button.textContent=paused?"▶ Play preview":"Ⅱ Pause preview";
      button.setAttribute("aria-label",paused?"Play preview":"Pause preview");
      button.setAttribute("aria-pressed",String(paused));
      button.disabled=reduced;
      button.title=reduced?"Enable motion to play the preview":"";
      if(active){paint();if(visible&&!document.hidden&&!paused){last=performance.now();raf=requestAnimationFrame(tick);}}
    }
    button.addEventListener("click",()=>{manuallyPaused=!manuallyPaused;sync();});
    const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.05});
    observer.observe(canvas);
    return {sync,refresh:()=>{if(active)paint();},isRunning:()=>raf!==null};
  }
  return {setReduced,countdown,reorderRows,celebrate,clearCelebration,cancelAnimations,drawMap,createPreview,
    createFrameBudget,updateCamera,resetCamera,victoryPose,victoryLayout,presentWinner,stopWinner,suspendWinner,winnerStatus};
})();

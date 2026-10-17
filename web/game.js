"use strict";

const $ = id => document.getElementById(id);
const STORAGE_KEY = "marble-race-v2";
function readSaved() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {}; }
  catch { return {}; }
}
const saved = readSaved();
const validArena = (list, value, fallback) => list.some(a => a.id === value) ? value : fallback;
const state = {
  screen:"menu", youIdx:Number.isInteger(saved.youIdx) && saved.youIdx >= 0 && saved.youIdx < RACER_POOL.length ? saved.youIdx : 6,
  fieldSize:Number.isInteger(saved.fieldSize) && saved.fieldSize >= 2 && saved.fieldSize <= 8 ? saved.fieldSize : 6,
  mode:saved.mode === "drop" ? "drop" : "race",
  arenaSize:["s","m","l"].includes(saved.arenaSize) ? saved.arenaSize : "m",
  mazeArena:validArena(MAZE_ARENAS, saved.mazeArena, "classic"),
  dropArena:validArena(DROP_ARENAS, saved.dropArena, "classic_plinko"),
  sound:saved.sound === true, followYou:false,
  races:Number.isInteger(saved.races) && saved.races >= 0 ? saved.races : 0,
  wins:Number.isInteger(saved.wins) && saved.wins >= 0 ? saved.wins : 0,
  sim:null, raf:null, lastTime:0, accumulator:0, phase:"idle", paused:false,
  countdownRemaining:0, countdownTick:null, lastRun:null, standingsAt:-1, runId:0,
};
const SIM_KINDS = {
  race:{step:stepRace,draw:drawRace,size:s=>[s.geo.w,s.viewportH || s.geo.imgH]},
  drop:{step:stepDrop,draw:drawDrop,size:s=>[s.stageW,s.viewportH]},
};
function persist() {
  const {youIdx,fieldSize,mode,arenaSize,mazeArena,dropArena,sound,races,wins} = state;
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({youIdx,fieldSize,mode,arenaSize,mazeArena,dropArena,sound,races,wins})); } catch {}
}
function announce(message) { $("announcement").textContent = message; }
function arenaInfo(mode = state.mode, id = mode === "race" ? state.mazeArena : state.dropArena) {
  return (mode === "race" ? MAZE_ARENAS : DROP_ARENAS).find(a => a.id === id);
}
let audioContext;
function tone(frequency, duration=.1, delay=0) {
  if (!state.sound) return;
  try {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    if (!audioContext) audioContext = new Audio();
    if (audioContext.state === "suspended") audioContext.resume().catch(()=>{});
    const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
    const time = audioContext.currentTime + delay;
    oscillator.type = "sine"; oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0,time); gain.gain.linearRampToValueAtTime(.085,time+.01);
    gain.gain.exponentialRampToValueAtTime(.001,time+duration);
    oscillator.connect(gain); gain.connect(audioContext.destination);
    oscillator.start(time); oscillator.stop(time+duration+.02);
  } catch {}
}
function updateSoundButton() {
  $("sound-state").textContent = state.sound ? "ON" : "OFF";
  $("btn-sound").setAttribute("aria-label", state.sound ? "Turn sound off" : "Turn sound on");
  $("btn-sound").setAttribute("aria-pressed", String(state.sound));
  $("btn-sound").title = state.sound ? "Sound on" : "Sound off";
}
function updateSession() {
  $("session-label").textContent = state.races ? state.races + " races · " + state.wins + " wins for your picks" : "Ready when you are";
}
function stopSimulation() {
  state.runId++;
  if (state.raf !== null) cancelAnimationFrame(state.raf);
  state.raf = null; state.paused = false; state.phase = "idle";
  $("countdown").hidden = true;
  $("pause-overlay").hidden = true;
  $("winner-overlay").hidden = true;
}
function showScreen(name) {
  if (!["menu","mode","race"].includes(name)) return;
  if (name !== "race") stopSimulation();
  state.screen = name;
  document.body.dataset.screen = name;
  document.querySelectorAll(".screen").forEach(el => {
    const active = el.dataset.screen === name;
    el.classList.toggle("active",active); el.setAttribute("aria-hidden",String(!active));
  });
  if (name === "mode") updateSetup();
  window.scrollTo({top:0,behavior:"instant"});
  if (name === "mode") $("setup-title").focus({preventScroll:true});
}
function racerTrait(racer) {
  if (racer.weight >= 1.05) return "Heavyweight. Holds a steady line.";
  if (racer.confusion >= .12) return "A wildcard. Expect a few detours.";
  if (racer.weight < .95) return "Lightweight. Quick off a bounce.";
  return "A balanced all-rounder.";
}
function racerIdentity(racer) {
  return (typeof RACER_IDENTITIES!=="undefined"&&RACER_IDENTITIES[racer.name]) ||
    {name:racer.name,kind:"racer",label:"Racer",description:racerTrait(racer)};
}
function buildRacerGrid() {
  const grid = $("racer-grid");
  grid.replaceChildren();
  RACER_POOL.forEach((r,i)=>{
    const identity=racerIdentity(r);
    const card = document.createElement("button");
    card.type="button"; card.className="racer-card"; card.dataset.racer=i;
    card.dataset.identity=identity.kind;
    card.style.setProperty("--racer-color",r.color.join(" "));
    card.setAttribute("aria-label","Choose "+r.name+", "+identity.label);
    card.title=r.name+" · "+identity.label+". "+identity.description;
    const img = new Image(64,64); img.src="assets/racers/"+r.name.toLowerCase()+".png"; img.alt="";
    const label=document.createElement("strong"); label.className="racer-name";label.textContent=r.name;
    const kind=document.createElement("small");kind.className="racer-kind";kind.textContent=identity.label;
    card.append(img,label,kind);
    card.addEventListener("click",()=>{state.youIdx=i;updateSetup();announce(r.name+", "+identity.label+", selected.");tone(520,.07);});
    grid.append(card);
  });
}
function makePreview(canvas, mode, arena) {
  const roster = RACER_POOL.slice(0,4), seed=137;
  const sim = mode==="race" ? buildRace(seed,roster,"s",arena.id) : buildDrop(seed,roster,arena.id);
  const source = document.createElement("canvas");
  source.width = mode==="race" ? sim.geo.w : sim.stageW;
  source.height = mode==="race" ? sim.geo.imgH : sim.worldH;
  (mode==="race" ? drawMazeBackground : drawDropBackground)(source.getContext("2d"),sim);
  canvas.width=400;canvas.height=210;
  const ctx=canvas.getContext("2d");
  const cropHeight=source.width*.525;
  const cropTop=mode==="drop"?Math.min(sim.worldH-cropHeight,sim.finishY*.35):0;
  if(mode==="race"){
    // An overview makes the layout differences visible before starting.
    // Rotate the tall map into the wide preview without distorting its paths.
    ctx.fillStyle="#111c24";ctx.fillRect(0,0,400,210);
    const scale=Math.min(380/source.height,190/source.width);
    ctx.save();ctx.translate(200,105);ctx.rotate(-Math.PI/2);ctx.scale(scale,scale);
    ctx.drawImage(source,-source.width/2,-source.height/2);ctx.restore();
  }else ctx.drawImage(source,0,cropTop,source.width,cropHeight,0,0,400,210);
  if(mode==="drop"){
    const b=sim.blades.find(blade=>blade.y>=cropTop&&blade.y<=cropTop+cropHeight);
    if(b){
      const scale=400/source.width;
      ctx.save();ctx.scale(scale,scale);ctx.translate(0,-cropTop);
      ctx.lineCap="round";ctx.lineWidth=sim.pegRadius*1.6;ctx.strokeStyle=arena.accent;
      ctx.beginPath();ctx.moveTo(b.x-b.len*.42,b.y-b.len*.15);ctx.lineTo(b.x+b.len*.42,b.y+b.len*.15);ctx.stroke();ctx.restore();
    }
  }
  source.width=source.height=1;
}
function buildArenaCards() {
  for(const [mode,list,id] of [["race",MAZE_ARENAS,"arena-choices-race"],["drop",DROP_ARENAS,"arena-choices-drop"]]){
    const grid=$(id);grid.replaceChildren();
    for(const arena of list){
      const card=document.createElement("button");card.type="button";card.className="arena-card";card.dataset.arena=arena.id;
      card.setAttribute("aria-label",arena.name+". "+arena.description);
      const canvas=document.createElement("canvas");canvas.setAttribute("aria-hidden","true");
      const check=document.createElement("span");check.className="arena-check";check.textContent="✓";check.setAttribute("aria-hidden","true");
      const text=document.createElement("span");text.className="arena-text";
      const name=document.createElement("strong");name.textContent=arena.name;
      const description=document.createElement("small");description.textContent=arena.description;
      text.append(name,description);card.append(canvas,check,text);grid.append(card);
      makePreview(canvas,mode,arena);
      card.addEventListener("click",()=>{if(mode==="race")state.mazeArena=arena.id;else state.dropArena=arena.id;updateSetup();});
    }
  }
}
function updateSetup() {
  const racer=RACER_POOL[state.youIdx], arena=arenaInfo(),identity=racerIdentity(racer);
  document.querySelectorAll(".racer-card").forEach(el=>{
    const selected=Number(el.dataset.racer)===state.youIdx;
    el.classList.toggle("selected",selected);el.setAttribute("aria-pressed",String(selected));
  });
  $("selected-portrait").src="assets/racers/"+racer.name.toLowerCase()+".png";
  $("selected-name").textContent=racer.name;$("selected-kind").textContent=identity.label;
  $("selected-description").textContent=identity.description;$("selected-trait").textContent=racerTrait(racer);
  $("selected-portrait").closest(".selected-racer").style.setProperty("--racer-color",racer.color.join(" "));
  $("field-val").textContent=state.fieldSize;
  $("field-minus").disabled=state.fieldSize<=2;$("field-plus").disabled=state.fieldSize>=8;
  document.querySelectorAll("[data-mode]").forEach(el=>{
    const on=el.dataset.mode===state.mode;el.classList.toggle("selected",on);el.setAttribute("aria-pressed",String(on));
  });
  $("arena-box-race").hidden=state.mode!=="race";$("arena-box-drop").hidden=state.mode!=="drop";
  $("arena-count").textContent=(state.mode==="race"?MAZE_ARENAS:DROP_ARENAS).length+" LAYOUTS";
  $("mode-description").textContent=state.mode==="race"?"Find a path through the maze. First across the line wins.":"Fall through pegs and spinning obstacles. First to the bottom wins.";
  for(const [id,selected] of [["arena-choices-race",state.mazeArena],["arena-choices-drop",state.dropArena]]){
    $(id).querySelectorAll("button").forEach(el=>{const on=el.dataset.arena===selected;el.classList.toggle("on",on);el.setAttribute("aria-pressed",String(on));});
  }
  $("arena-choices").querySelectorAll("button").forEach(el=>{const on=el.dataset.size===state.arenaSize;el.classList.toggle("on",on);el.setAttribute("aria-pressed",String(on));});
  $("setup-summary").textContent=racer.name+" · "+arena.name+" · "+state.fieldSize+" racers";
  $("btn-mode-next").firstChild.textContent=state.mode==="drop"?"Start drop ":"Start race ";
  persist();
}
function shuffle(list,rng) {for(let i=list.length-1;i>0;i--){const j=Math.floor(rng()*(i+1));[list[i],list[j]]=[list[j],list[i]];}return list;}
function newRun() {
  let seed;
  try {seed=crypto.getRandomValues(new Uint32Array(1))[0];}catch{seed=(Date.now()^Math.floor(Math.random()*1e9))>>>0;}
  const rng=mulberry32(seed^0xa34f1);
  const roster=shuffle([state.youIdx,...shuffle(RACER_POOL.map((_,i)=>i).filter(i=>i!==state.youIdx),rng).slice(0,state.fieldSize-1)],rng);
  return {seed,roster,youIdx:state.youIdx,mode:state.mode,arenaSize:state.arenaSize,arena:state.mode==="race"?state.mazeArena:state.dropArena,counted:false};
}
const canvas=$("race-canvas"), cctx=canvas.getContext("2d");
function startSim(replay=false) {
  const config=replay&&state.lastRun?{...state.lastRun,roster:[...state.lastRun.roster]}:newRun();
  stopSimulation();showScreen("race");
  state.lastRun=config;
  const roster=config.roster.map(i=>({...RACER_POOL[i]}));
  const sim=config.mode==="drop"?buildDrop(config.seed,roster,config.arena):buildRace(config.seed,roster,config.arenaSize,config.arena);
  sim.youIdx=config.roster.indexOf(config.youIdx);sim.kind=config.mode;sim.followYou=state.followYou;
  sim.isReplay=replay;sim.recorded=false;sim.runConfig=config;
  const background=document.createElement("canvas");
  background.width=config.mode==="drop"?sim.stageW:sim.geo.w;background.height=config.mode==="drop"?sim.worldH:sim.geo.imgH;
  (config.mode==="drop"?drawDropBackground:drawMazeBackground)(background.getContext("2d"),sim);sim.offscreen=background;
  if(state.sim&&state.sim.offscreen){state.sim.offscreen.width=state.sim.offscreen.height=1;}
  state.sim=sim;state.phase="countdown";state.countdownRemaining=1.8;state.countdownTick=null;state.accumulator=0;state.standingsAt=-1;
  const arena=arenaInfo(config.mode,config.arena);
  $("live-title").textContent=arena.name;$("live-mode").textContent=config.mode==="drop"?"MARBLE DROP":"MAZE RACE";
  $("race-seed").textContent="RACE #"+config.seed.toString(16).toUpperCase();
  $("following-racer").textContent="Your pick: "+RACER_POOL[config.youIdx].name+" · "+racerIdentity(RACER_POOL[config.youIdx]).label;
  $("live-rule").textContent=config.mode==="drop"?"First to the bottom wins. Spinning obstacles can change the order.":"First across the line wins. One corner can change the race.";
  $("standings-note").textContent=config.mode==="drop"?"Positions estimated by height on the track.":"Positions estimated by distance to finish.";
  $("finish-total").textContent=roster.length;$("race-status").textContent=replay?"Same grid. Same race.":"Taking our places…";
  $("countdown").hidden=false;$("countdown-number").textContent="3";
  $("btn-pause").disabled=false;$("btn-restart").disabled=false;
  updatePauseControl();buildStandings();updateStandings(true);fitCanvas();
  state.lastTime=performance.now();state.raf=requestAnimationFrame(loop);
  $("btn-pause").focus({preventScroll:true});
  announce(arena.name+". "+roster.length+" racers. Your pick is "+RACER_POOL[config.youIdx].name+".");
}
function fitCanvas() {
  if(!state.sim||state.screen!=="race")return;
  const [w,h]=SIM_KINDS[state.sim.kind].size(state.sim),rect=$("race-stage").getBoundingClientRect();
  const scale=Math.min(rect.width/w,rect.height/h),dpr=Math.min(2,window.devicePixelRatio||1);
  canvas.style.width=Math.max(1,w*scale)+"px";canvas.style.height=Math.max(1,h*scale)+"px";
  canvas.width=Math.max(1,Math.round(w*scale*dpr));canvas.height=Math.max(1,Math.round(h*scale*dpr));
  cctx.setTransform(canvas.width/w,0,0,canvas.height/h,0,0);
  drawCurrent();
}
function drawCurrent(){if(state.sim)SIM_KINDS[state.sim.kind].draw(cctx,state.sim,state.sim.offscreen,state.sim.step*DT,state.sim.youIdx);}
function progress(sim,racer) {
  if(sim.kind==="drop")return Math.max(0,sim.finishY-racer.y);
  return sim.distField[racer.lastCell[0]]?.[racer.lastCell[1]] ?? 1e9;
}
function buildStandings(){
  const list=$("standings");list.replaceChildren();
  state.sim.racers.forEach((r,i)=>{
    const row=document.createElement("li");row.className="standing"+(i===state.sim.youIdx?" you":"");row.dataset.racer=i;
    const place=document.createElement("span");place.className="place";
    const img=new Image(30,30);img.src="assets/racers/"+r.name.toLowerCase()+".png";img.alt="";
    const name=document.createElement("span");name.className="standing-name";name.textContent=r.name;
    const identity=document.createElement("small");identity.className="standing-identity";identity.textContent=racerIdentity(r).label;name.append(identity);
    row.title=r.name+", "+racerIdentity(r).label+(i===state.sim.youIdx?", your pick":"");
    if(i===state.sim.youIdx){const label=document.createElement("small");label.className="standing-pick";label.textContent="YOUR PICK";name.append(label);}
    const distance=document.createElement("span");distance.className="distance";
    row.append(place,img,name,distance);list.append(row);
  });
}
function updateStandings(force=false) {
  const sim=state.sim;
  if(!force&&sim.step-state.standingsAt<24)return;
  state.standingsAt=sim.step;
  const ranking=sim.racers.map((r,i)=>({r,i,d:progress(sim,r)})).sort((a,b)=>{
    if(a.r.finished!==b.r.finished)return a.r.finished?-1:1;
    if(a.r.finished&&b.r.finished)return (a.r.finishStep??0)-(b.r.finishStep??0)||a.i-b.i;
    return a.d-b.d||a.i-b.i;
  });
  ranking.forEach(({r,i,d},rank)=>{
    const row=$("standings").querySelector('[data-racer="'+i+'"]');
    row.querySelector(".place").textContent=rank+1;
    row.querySelector(".distance").textContent=r.finished?"FINISHED":sim.kind==="drop"?Math.max(0,Math.round((1-d/sim.finishY)*100))+"%":Math.round(d)+" cells";
    row.classList.toggle("finished",r.finished);$("standings").append(row);
  });
  $("finish-count").textContent=sim.finishedCount;
  $("race-clock").textContent=(sim.step*DT).toFixed(1).padStart(4,"0");
}
function loop(now) {
  state.raf=null;
  if(state.screen!=="race"||state.paused||!state.sim||state.phase==="finished")return;
  const dtReal=Math.min(Math.max(0,(now-state.lastTime)/1000),.05);state.lastTime=now;
  if(state.phase==="countdown"){
    state.countdownRemaining-=dtReal;
    const tick=Math.max(1,Math.ceil(state.countdownRemaining/.6));
    if(tick!==state.countdownTick){state.countdownTick=tick;$("countdown-number").textContent=tick;tone(420,.07);}
    if(state.countdownRemaining<=0){state.phase="racing";$("countdown").hidden=true;$("race-status").textContent="And they’re off. First across wins.";tone(840,.18);announce("Race started.");}
  }else{
    const sim=state.sim;state.accumulator+=dtReal;
    while(state.accumulator>=DT&&!sim.winner){
      SIM_KINDS[sim.kind].step(sim,sim.step*DT);state.accumulator-=DT;
      if(!sim.winner&&sim.step*DT>=(sim.kind==="drop"?60:90)){
        sim.winner=sim.racers.filter(r=>r.active).sort((a,b)=>progress(sim,a)-progress(sim,b))[0]||sim.racers[0];
        sim.resultReason="timeout";
      }
    }
    updateStandings();drawCurrent();
    if(sim.winner){showWinner(sim);return;}
  }
  state.raf=requestAnimationFrame(loop);
}
function updatePauseControl(){
  $("btn-pause").innerHTML=state.paused?"▶ <span>Resume</span>":"Ⅱ <span>Pause</span>";
  $("btn-pause").setAttribute("aria-label",state.paused?"Resume race":"Pause race");
}
function pauseRace(){
  if(!state.sim||state.phase==="finished"||state.screen!=="race"||state.paused)return;
  state.paused=true;if(state.raf!==null)cancelAnimationFrame(state.raf);state.raf=null;
  $("pause-overlay").hidden=false;updatePauseControl();$("race-status").textContent="Paused. Your race can wait.";
  $("btn-resume").focus({preventScroll:true});announce("Race paused.");
}
function resumeRace(){
  if(!state.paused||state.screen!=="race")return;
  state.paused=false;$("pause-overlay").hidden=true;state.lastTime=performance.now();
  updatePauseControl();$("race-status").textContent=state.phase==="countdown"?"Taking our places…":"First across the line wins.";
  $("btn-pause").focus({preventScroll:true});state.raf=requestAnimationFrame(loop);
}
function showWinner(sim){
  if(sim!==state.sim)return;
  if(state.raf!==null)cancelAnimationFrame(state.raf);state.raf=null;state.phase="finished";state.paused=false;
  $("countdown").hidden=true;$("pause-overlay").hidden=true;
  updateStandings(true);drawCurrent();
  const winner=sim.winner,won=sim.racers.indexOf(winner)===sim.youIdx,timeout=sim.resultReason==="timeout";
  $("winner-name").textContent=winner.name+(timeout?" leads!":" wins!");
  $("winner-identity").textContent=racerIdentity(winner).label;
  $("winner-sub").textContent=timeout?"Time limit reached. Furthest progress takes the lead.":won?"Your pick crossed the finish first. Nicely called.":"First across the finish. There’s always a rematch.";
  $("result-eyebrow").textContent=timeout?"TIME’S UP":won?"THAT’S YOUR RACER!":"THE FINISH IS IN";
  $("result-time").textContent=(sim.step*DT).toFixed(2)+" seconds";
  $("result-pick").textContent="Your pick: "+sim.racers[sim.youIdx].name;
  $("race-status").textContent=timeout?"Time limit · "+winner.name+" leads":winner.name+" takes the finish!";
  const winnerCanvas=$("winner-swatch"),ctx=winnerCanvas.getContext("2d");ctx.clearRect(0,0,120,120);
  drawRacerFace(ctx,120,winner.color,0,won,winner.name);
  $("winner-overlay").hidden=false;$("btn-pause").disabled=true;
  if(!sim.recorded){
    sim.recorded=true;
    if(!sim.runConfig.counted){sim.runConfig.counted=true;state.races++;if(won)state.wins++;persist();updateSession();}
    tone(523,.14);tone(659,.14,.12);tone(784,.3,.24);
  }
  $("btn-again").focus({preventScroll:true});
  announce($("winner-name").textContent+" "+$("winner-sub").textContent);
}
function setCamera(followYou){
  state.followYou=followYou;if(state.sim)state.sim.followYou=followYou;
  $("camera-leader").classList.toggle("on",!followYou);$("camera-you").classList.toggle("on",followYou);
  $("camera-leader").setAttribute("aria-pressed",String(!followYou));$("camera-you").setAttribute("aria-pressed",String(followYou));
  announce(followYou?"Camera follows your racer.":"Camera follows the leader.");
}
document.querySelectorAll("[data-nav]").forEach(el=>el.addEventListener("click",()=>showScreen(el.dataset.nav)));
$("btn-play").addEventListener("click",()=>showScreen("mode"));
document.querySelectorAll("[data-enter-mode]").forEach(el=>el.addEventListener("click",()=>{state.mode=el.dataset.enterMode;showScreen("mode");}));
document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",()=>{state.mode=el.dataset.mode;updateSetup();}));
$("field-minus").addEventListener("click",()=>{state.fieldSize=Math.max(2,state.fieldSize-1);updateSetup();});
$("field-plus").addEventListener("click",()=>{state.fieldSize=Math.min(8,state.fieldSize+1);updateSetup();});
$("arena-choices").addEventListener("click",event=>{const button=event.target.closest("[data-size]");if(button){state.arenaSize=button.dataset.size;updateSetup();}});
$("btn-random").addEventListener("click",()=>{
  state.youIdx=Math.floor(Math.random()*RACER_POOL.length);
  state.mode=Math.random()<.5?"race":"drop";
  state.mazeArena=MAZE_ARENAS[Math.floor(Math.random()*MAZE_ARENAS.length)].id;
  state.dropArena=DROP_ARENAS[Math.floor(Math.random()*DROP_ARENAS.length)].id;
  state.fieldSize=2+Math.floor(Math.random()*7);updateSetup();announce("Setup shuffled.");
});
$("btn-mode-next").addEventListener("click",()=>startSim());
$("btn-again").addEventListener("click",()=>startSim());
$("btn-replay").addEventListener("click",()=>startSim(true));
$("btn-newracer").addEventListener("click",()=>showScreen("mode"));
$("btn-restart").addEventListener("click",()=>startSim(true));
$("btn-pause").addEventListener("click",()=>state.paused?resumeRace():pauseRace());
$("btn-resume").addEventListener("click",resumeRace);
$("camera-leader").addEventListener("click",()=>setCamera(false));
$("camera-you").addEventListener("click",()=>setCamera(true));
$("btn-sound").addEventListener("click",()=>{state.sound=!state.sound;updateSoundButton();persist();tone(620,.1);});
function openHelp(){if(state.screen==="race")pauseRace();$("help-dialog").showModal();}
$("btn-help").addEventListener("click",openHelp);$("btn-how").addEventListener("click",openHelp);
$("btn-close-help").addEventListener("click",()=>$("help-dialog").close());
$("btn-help-play").addEventListener("click",()=>{$("help-dialog").close();if(state.screen==="race")resumeRace();else showScreen("mode");});
$("help-dialog").addEventListener("click",event=>{if(event.target===$("help-dialog")){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
document.addEventListener("keydown",event=>{
  if($("help-dialog").open)return;
  if(state.screen!=="race"||state.phase==="finished")return;
  if(event.key==="Escape"||(event.code==="Space"&&!/BUTTON|INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName))){
    event.preventDefault();state.paused?resumeRace():pauseRace();
  }
});
document.addEventListener("visibilitychange",()=>{if(document.hidden)pauseRace();});
window.addEventListener("resize",fitCanvas,{passive:true});
for(const racer of RACER_POOL){
  const portrait=new Image();racerPortraits.set(racer.name,portrait);
  portrait.src="assets/racers/"+racer.name.toLowerCase()+".png";
  portrait.onload=()=>{if(state.screen==="race"&&state.sim)drawCurrent();};
}
buildRacerGrid();buildArenaCards();updateSetup();updateSession();updateSoundButton();

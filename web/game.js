"use strict";

const $ = id => document.getElementById(id);
const STORAGE_KEY = "marble-race-v2";
function readSaved(fallback={}) {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {}; }
  catch { return fallback; }
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
  format:saved.format === "cup" ? "cup" : "single",
  speed:[.5,1,2].includes(saved.speed) ? saved.speed : 1,
  ...GameSession.progress(saved), cup:null,
  sim:null, raf:null, lastTime:0, accumulator:0, phase:"idle", paused:false,
  countdownRemaining:0, countdownTick:null, lastRun:null, standingsAt:-1, runId:0,
};
const SIM_KINDS = {
  race:{step:stepRace,draw:drawRace,size:s=>[s.geo.w,s.viewportH || s.geo.imgH]},
  drop:{step:stepDrop,draw:drawDrop,size:s=>[s.stageW,s.viewportH]},
};
let storedProgress=GameSession.progress(saved);
const pendingResults=new Map();
function refreshProgress(){
  storedProgress=GameSession.progress(readSaved(storedProgress));
  let latest=storedProgress;
  for(const result of pendingResults.values())latest=GameSession.progress(latest,result);
  Object.assign(state,latest);
}
function persist(result=null) {
  // A tab may have finished another race since this screen was opened.
  // Merge against storage at write time so settings cannot erase its result.
  if(result)pendingResults.set(result.race,result);
  refreshProgress();
  const {youIdx,fieldSize,mode,arenaSize,mazeArena,dropArena,sound,races,wins,format,speed,history,countedRuns} = state;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({youIdx,fieldSize,mode,arenaSize,mazeArena,dropArena,sound,races,wins,format,speed,history,countedRuns}));
    storedProgress=GameSession.progress(state);pendingResults.clear();
  } catch {}
  updateSession();
}
function announce(message) { $("announcement").textContent = message; }
function arenaInfo(mode = state.mode, id = mode === "race" ? state.mazeArena : state.dropArena) {
  return (mode === "race" ? MAZE_ARENAS : DROP_ARENAS).find(a => a.id === id);
}
let audioContext;
const activeTones = new Set();
function silence(){for(const oscillator of activeTones){try{oscillator.stop();}catch{}}activeTones.clear();}
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
    activeTones.add(oscillator);oscillator.onended=()=>{activeTones.delete(oscillator);oscillator.disconnect();gain.disconnect();};
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
  silence();
  state.runId++;
  if (state.raf !== null) cancelAnimationFrame(state.raf);
  state.raf = null; state.paused = false; state.phase = "idle";
  $("countdown").hidden = true;
  $("pause-overlay").hidden = true;
  $("winner-overlay").hidden = true;
}
function showScreen(name) {
  if (!["menu","mode","race"].includes(name)) return;
  if (name !== "race") {stopSimulation();updateRaceUrl();}
  state.screen = name;
  document.body.dataset.screen = name;
  document.querySelectorAll(".screen").forEach(el => {
    const active = el.dataset.screen === name;
    el.classList.toggle("active",active); el.setAttribute("aria-hidden",String(!active));
  });
  if (name === "mode") updateSetup();
  if (name === "menu") renderHistory();
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
  $("btn-mode-next").firstChild.textContent=state.format==="cup"?"Start cup ":state.mode==="drop"?"Start drop ":"Start race ";
  document.querySelectorAll("[data-format]").forEach(el=>{const on=el.dataset.format===state.format;el.classList.toggle("on",on);el.setAttribute("aria-pressed",String(on));});
  persist();
}
function shuffle(list,rng) {for(let i=list.length-1;i>0;i--){const j=Math.floor(rng()*(i+1));[list[i],list[j]]=[list[j],list[i]];}return list;}
function newRun() {
  let seed;
  try {seed=crypto.getRandomValues(new Uint32Array(1))[0];}catch{seed=(Date.now()^Math.floor(Math.random()*1e9))>>>0;}
  const rng=mulberry32(seed^0xa34f1);
  const roster=shuffle([state.youIdx,...shuffle(RACER_POOL.map((_,i)=>i).filter(i=>i!==state.youIdx),rng).slice(0,state.fieldSize-1)],rng);
  return {seed,roster,youIdx:state.youIdx,mode:state.mode,arenaSize:state.arenaSize,arena:state.mode==="race"?state.mazeArena:state.dropArena,finishTarget:1,counted:false};
}
function updateRaceUrl(config=null){
  try{
    const url=new URL(location.href);
    if(!url.searchParams.has("race"))return;
    if(config)url.searchParams.set("race",GameSession.encode(config));
    else url.searchParams.delete("race");
    window.history.replaceState(null,"",url.href);
  }catch{}
}
function openExternalRace(config){
  state.cup=null;
  Object.assign(state,{youIdx:config.youIdx,fieldSize:config.roster.length,mode:config.mode,arenaSize:config.arenaSize,format:"single"});
  if(config.mode==="race")state.mazeArena=config.arena;else state.dropArena=config.arena;
  startSim(false,config);
}
function startSelected(){
  if(state.format==="cup"){
    state.cup=GameSession.makeCup(newRun());startCupRound(0);
  }else{state.cup=null;startSim(false,newRun());}
}
function startCupRound(round){
  state.cup.round=round;
  startSim(false,{...state.cup.rounds[round],cupId:state.cup.id,cupRound:round});
}
function nextRun(){
  if(state.cup && state.lastRun?.cupId===state.cup.id){
    if(state.cup.round<2){startCupRound(state.cup.round+1);return;}
    state.format="cup";
  }
  startSelected();
}
function cupFor(sim=state.sim){return state.cup&&sim?.runConfig.cupId===state.cup.id?state.cup:null;}
function renderCup(){
  const cup=cupFor();$("cup-strip").hidden=!cup;
  if(!cup)return;
  $("cup-round-label").textContent="CUP · ROUND "+(cup.round+1)+" OF 3";
  $("cup-track").replaceChildren();
  cup.rounds.forEach((config,i)=>{const chip=document.createElement("span");chip.className="cup-round"+(i===cup.round?" current":"")+(cup.results[i]!==null?" complete":"");chip.textContent=(cup.results[i]!==null?"✓ ":(i+1)+". ")+arenaInfo(config.mode,config.arena).name;$("cup-track").append(chip);});
  $("cup-scores").replaceChildren();
  [...cup.rounds[0].roster].sort((a,b)=>cup.scores[b]-cup.scores[a]||a-b).forEach(i=>{
    const chip=document.createElement("span");chip.className="cup-score"+(i===state.lastRun.youIdx?" you":"");
    const img=new Image(24,24);img.src="assets/racers/"+RACER_POOL[i].name.toLowerCase()+".png";img.alt="";
    const text=document.createElement("span");text.textContent=RACER_POOL[i].name+" "+cup.scores[i];chip.append(img,text);$("cup-scores").append(chip);
  });
}
function renderHistory(){
  $("recent-races").hidden=state.history.length===0;$("recent-list").replaceChildren();
  for(const entry of state.history.slice(0,5)){
    const config=GameSession.decode(entry.race),racer=RACER_POOL[entry.winner];
    const button=document.createElement("button");button.type="button";button.className="history-race";
    const img=new Image(40,40);img.src="assets/racers/"+racer.name.toLowerCase()+".png";img.alt="";
    const text=document.createElement("span"),title=document.createElement("strong"),detail=document.createElement("small");
    title.textContent=racer.name+" won · "+entry.seconds.toFixed(2)+"s";
    detail.textContent=arenaInfo(config.mode,config.arena).name+" · Replay";text.append(title,detail);button.append(img,text);
    button.addEventListener("click",()=>openExternalRace({...config,counted:true}));
    const item=document.createElement("li");item.append(button);$("recent-list").append(item);
  }
}
const canvas=$("race-canvas"), cctx=canvas.getContext("2d");
function startSim(replay=false, override=null) {
  const config=override || (replay&&state.lastRun?{...state.lastRun,roster:[...state.lastRun.roster]}:newRun());
  stopSimulation();showScreen("race");
  state.lastRun=config;
  updateRaceUrl(config);
  const roster=config.roster.map(i=>({...RACER_POOL[i]}));
  const sim=config.mode==="drop"?buildDrop(config.seed,roster,config.arena):buildRace(config.seed,roster,config.arenaSize,config.arena);
  sim.youIdx=config.roster.indexOf(config.youIdx);sim.kind=config.mode;sim.followYou=state.followYou;
  sim.finishTarget=config.finishTarget||1;sim.defaultViewportH=sim.viewportH;
  sim.startDistances=sim.racers.map(r=>progress(sim,r));sim.startDistance=sim.startDistances[sim.youIdx];sim.leaderIdx=null;sim.eventAt=-1;sim.bumpAt=-1;
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
  $("live-rule").textContent=sim.finishTarget>1?"Real finishers score 5 / 3 / 1. Unfinished racers score zero.":config.mode==="drop"?"First to the bottom wins. Spinning obstacles can change the order.":"First across the line wins. One corner can change the race.";
  $("standings-note").textContent=config.mode==="drop"?"Positions estimated by height on the track.":"Positions estimated by distance to finish.";
  $("finish-total").textContent=roster.length;$("race-status").textContent=replay?"Same grid. Same race.":"Taking our places…";
  $("countdown").hidden=false;$("countdown-number").textContent="3";
  $("btn-pause").disabled=false;$("btn-restart").disabled=false;
  $("share-status").textContent="";$("share-link").hidden=true;$("share-link").value="";$("race-event").textContent="Your crew is ready.";
  $("standings-status").textContent="LIVE";
  renderCup();setSpeed(state.speed);
  updatePauseControl();buildStandings();updateStandings(true);fitCanvas();
  state.lastTime=performance.now();state.raf=requestAnimationFrame(loop);
  $("btn-pause").focus({preventScroll:true});
  announce(arena.name+". "+roster.length+" racers. Your pick is "+RACER_POOL[config.youIdx].name+".");
}
function fitCanvas() {
  if(!state.sim||state.screen!=="race")return;
  const [w,h]=SIM_KINDS[state.sim.kind].size(state.sim),rect=$("race-stage").getBoundingClientRect();
  const worldH=state.sim.worldH||state.sim.geo.imgH;
  state.sim.viewportH=Math.min(worldH,state.sim.defaultViewportH||h,Math.max(360,w*rect.height/Math.max(1,rect.width)));
  state.sim.cameraY=Math.max(0,Math.min(worldH-state.sim.viewportH,state.sim.cameraY));
  const viewH=state.sim.viewportH,scale=Math.min(rect.width/w,rect.height/viewH),dpr=Math.min(2,window.devicePixelRatio||1);
  canvas.style.width=Math.max(1,w*scale)+"px";canvas.style.height=Math.max(1,viewH*scale)+"px";
  canvas.width=Math.max(1,Math.round(w*scale*dpr));canvas.height=Math.max(1,Math.round(viewH*scale*dpr));
  cctx.setTransform(canvas.width/w,0,0,canvas.height/viewH,0,0);
  frameCamera();
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
    row.querySelector(".distance").textContent=r.finished?"FINISHED":sim.kind==="drop"?Math.max(0,Math.min(99,Math.round((1-d/Math.max(1,sim.startDistances[i]))*100)))+"%":Math.round(d)+" cells";
    row.classList.toggle("finished",r.finished);$("standings").append(row);
  });
  $("finish-count").textContent=sim.finishedCount;
  $("race-clock").textContent=(sim.step*DT).toFixed(1).padStart(4,"0");
  const you=sim.racers[sim.youIdx],fraction=you.finished?1:Math.max(0,Math.min(.99,1-progress(sim,you)/Math.max(1,sim.startDistance)));
  $("your-progress").value=Math.round(fraction*100);
  $("your-progress-label").textContent=you.name+" · "+(you.finished?"FINISHED":Math.round(fraction*100)+"% complete");
  $("your-progress").setAttribute("aria-label",$("your-progress-label").textContent);
  const finishOrder=sim.finishOrder||[];
  if(finishOrder.length>(sim.announcedFinishes||0)){
    const finisher=sim.racers[finishOrder[finishOrder.length-1]];
    $("race-event").textContent=finisher.name+" finishes #"+finishOrder.length+(sim.finishTarget>finishOrder.length?" · podium still open":"");
    sim.announcedFinishes=finishOrder.length;sim.eventAt=sim.step;
    announce($("race-event").textContent);
  }else if(!sim.complete){
    const leader=ranking.find(entry=>entry.r.active);
    if(leader && leader.i!==sim.leaderIdx && sim.step-sim.eventAt>180){
      $("race-event").textContent=leader.r.name+(sim.finishedCount?" leads the chase":" takes the lead")+(leader.i===sim.youIdx?" · your pick!":"");
      sim.leaderIdx=leader.i;sim.eventAt=sim.step;
    }
  }
}
function setSpeed(value){
  state.speed=[.5,1,2].includes(value)?value:1;
  document.querySelectorAll("[data-speed]").forEach(button=>{const on=Number(button.dataset.speed)===state.speed;button.classList.toggle("on",on);button.setAttribute("aria-pressed",String(on));});
  persist();
}
function finishAtTimeLimit(sim){
  sim.complete=true;sim.timedOut=true;
  sim.resultReason=sim.winner?"finish":"timeout";
  if(!sim.winner)sim.timeoutLeader=[...sim.racers].sort((a,b)=>progress(sim,a)-progress(sim,b))[0];
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
    const sim=state.sim;state.accumulator+=dtReal*state.speed;
    while(state.accumulator>=DT&&!sim.complete){
      SIM_KINDS[sim.kind].step(sim,sim.step*DT);state.accumulator-=DT;
      if(!sim.complete&&sim.step*DT>=(sim.kind==="drop"?60:90))finishAtTimeLimit(sim);
    }
    updateStandings();drawCurrent();
    const bump=sim.bumps[sim.bumps.length-1];
    if(bump && bump.born>(sim.lastBumpTime??-1) && sim.step-sim.bumpAt>=18){tone(170+bump.intensity*120,.045);sim.lastBumpTime=bump.born;sim.bumpAt=sim.step;}
    if(sim.complete){showWinner(sim);return;}
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
  silence();
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
  const winner=sim.winner||sim.timeoutLeader||sim.racers[0],timeout=!sim.winner||sim.resultReason==="timeout",won=!timeout&&sim.racers.indexOf(winner)===sim.youIdx;
  const finishSeconds=(timeout?sim.step:(winner.finishStep??sim.step))*DT;
  const cup=cupFor(sim),round=sim.runConfig.cupRound;
  if(cup)GameSession.scoreRound(cup,round,sim.finishOrder||[]);
  const cupDone=cup&&cup.results.every(result=>result!==null),champions=cupDone?GameSession.cupLeaders(cup):[];
  $("winner-name").textContent=winner.name+(timeout?" leads!":" wins!");
  $("winner-identity").textContent=racerIdentity(winner).label;
  $("winner-sub").textContent=timeout?"No racer finished before the time limit. No win recorded.":sim.timedOut?"Time limit reached. Only actual finishers earn points.":won?"Your pick crossed the finish first. Nicely called.":"First across the finish. There’s always a rematch.";
  $("result-eyebrow").textContent=timeout?"TIME’S UP":won?"THAT’S YOUR RACER!":"THE FINISH IS IN";
  $("result-time").textContent=(cup&&!timeout?"Round win: ":"")+finishSeconds.toFixed(2)+" seconds";
  $("result-pick").textContent="Your pick: "+sim.racers[sim.youIdx].name;
  $("result-context").textContent=cup?"ROUND "+(round+1)+" / 3":sim.finishTarget>1?"PODIUM RACE":"SINGLE RACE";
  $("result-score").hidden=!cup;
  if(cup){
    const awarded=cup.results[round].find(p=>p.racer===sim.runConfig.youIdx)?.points||0;
    $("result-score").textContent="Your pick: +"+awarded+" points · "+cup.scores[sim.runConfig.youIdx]+" total";
    if(cupDone){
      $("result-eyebrow").textContent="CUP COMPLETE";
      $("winner-name").textContent=champions.length===1?RACER_POOL[champions[0]].name+" wins the Cup!":champions.length?"Shared Cup victory":"No Cup winner";
      $("winner-identity").textContent=champions.length===1?racerIdentity(RACER_POOL[champions[0]]).label:champions.map(i=>RACER_POOL[i].name).join(" · ");
      $("winner-sub").textContent=champions.length?"Three rounds settled. "+cup.scores[champions[0]]+" points takes the Cup.":"No racer reached a scoring place. Try a new Cup.";
      $("result-context").textContent="ROUND 3 / 3 · "+(timeout?"No finisher":winner.name+" finished first");
    }
  }
  $("btn-again").textContent=cup?(cupDone?"New Cup ↗":"Next round →"):"New race ↗";
  $("standings-status").textContent="FINAL";
  $("standings-note").textContent=sim.finishTarget>1?"Podium places are actual finishes. Other positions show progress at the stop.":"Winner finished first. Other positions show progress when the race ended.";
  if(timeout)$("standings-note").textContent="Time limit reached. Positions show progress; nobody won.";
  $("race-status").textContent=timeout?"Time limit · "+winner.name+" leads":winner.name+" takes the finish!";
  if(cupDone)$("race-status").textContent="Cup complete · "+(champions.map(i=>RACER_POOL[i].name).join(" & ")||"No scoring finish");
  const winnerCanvas=$("winner-swatch"),ctx=winnerCanvas.getContext("2d");ctx.clearRect(0,0,120,120);
  const portraits=cupDone?champions.map(i=>RACER_POOL[i]):[winner];
  winnerCanvas.hidden=portraits.length===0;
  const columns=Math.ceil(Math.sqrt(portraits.length)),size=120/(columns||1),rows=Math.ceil(portraits.length/(columns||1));
  portraits.forEach((portrait,i)=>{
    const row=Math.floor(i/columns),rowCount=Math.min(columns,portraits.length-row*columns);
    ctx.save();ctx.translate((120-rowCount*size)/2+(i%columns)*size,(120-rows*size)/2+row*size);
    drawRacerFace(ctx,size,portrait.color,0,portrait.name===sim.racers[sim.youIdx].name,portrait.name);ctx.restore();
  });
  $("winner-overlay").hidden=false;$("btn-pause").disabled=true;
  if(!sim.recorded){
    sim.recorded=true;
    const key=GameSession.encode(sim.runConfig);
    if(!timeout && !sim.runConfig.counted){
      sim.runConfig.counted=true;
      persist({race:key,winner:sim.runConfig.roster[sim.racers.indexOf(winner)],seconds:finishSeconds,at:Date.now(),won});
    }
    if(!timeout){tone(523,.14);tone(659,.14,.12);tone(784,.3,.24);}
  }
  renderCup();
  $("btn-again").focus({preventScroll:true});
  announce($("winner-name").textContent+" "+$("winner-sub").textContent);
}
function setCamera(followYou){
  state.followYou=followYou;if(state.sim)state.sim.followYou=followYou;
  $("camera-leader").classList.toggle("on",!followYou);$("camera-you").classList.toggle("on",followYou);
  $("camera-leader").setAttribute("aria-pressed",String(!followYou));$("camera-you").setAttribute("aria-pressed",String(followYou));
  if(state.sim){frameCamera();drawCurrent();}
  announce(followYou?"Camera follows your racer.":"Camera follows the leader.");
}
function frameCamera(){
  const sim=state.sim,active=sim.racers.filter(r=>r.active);
  const selected=sim.racers[sim.youIdx];
  const target=(sim.complete&&sim.winner)||(sim.followYou&&selected?.active&&selected)||active.sort((a,b)=>progress(sim,a)-progress(sim,b))[0]||sim.winner;
  if(target)sim.cameraY=Math.max(0,Math.min((sim.worldH||sim.geo.imgH)-sim.viewportH,target.y-sim.viewportH*.42));
}
async function shareRace(){
  const key=GameSession.encode(state.lastRun);if(!key)return;
  const runId=state.runId;
  const stillCurrent=()=>state.runId===runId&&state.screen==="race"&&state.phase==="finished";
  const url=new URL(location.href);url.search="";url.hash="";url.searchParams.set("race",key);
  const link=url.href;
  $("share-link").value=link;
  try{await navigator.clipboard.writeText(link);if(stillCurrent())$("share-status").textContent="Race link copied. Same seed, same grid.";}
  catch{if(stillCurrent()){$("share-link").hidden=false;$("share-link").focus();$("share-link").select();$("share-status").textContent="Copy this link to replay the same race.";}}
}
document.querySelectorAll("[data-nav]").forEach(el=>el.addEventListener("click",()=>showScreen(el.dataset.nav)));
$("btn-play").addEventListener("click",()=>showScreen("mode"));
$("btn-quick").addEventListener("click",startSelected);
document.querySelectorAll("[data-format]").forEach(el=>el.addEventListener("click",()=>{state.format=el.dataset.format;updateSetup();}));
document.querySelectorAll("[data-speed]").forEach(el=>el.addEventListener("click",()=>setSpeed(Number(el.dataset.speed))));
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
$("btn-mode-next").addEventListener("click",startSelected);
$("btn-again").addEventListener("click",nextRun);
$("btn-replay").addEventListener("click",()=>startSim(true));
$("btn-newracer").addEventListener("click",()=>showScreen("mode"));
$("btn-restart").addEventListener("click",()=>startSim(true));
$("btn-pause").addEventListener("click",()=>state.paused?resumeRace():pauseRace());
$("btn-resume").addEventListener("click",resumeRace);
$("camera-leader").addEventListener("click",()=>setCamera(false));
$("camera-you").addEventListener("click",()=>setCamera(true));
$("btn-share").addEventListener("click",shareRace);
$("btn-sound").addEventListener("click",()=>{state.sound=!state.sound;if(!state.sound)silence();updateSoundButton();persist();tone(620,.1);});
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
window.addEventListener("storage",event=>{
  if(event.key!==null&&event.key!==STORAGE_KEY)return;
  refreshProgress();updateSession();
  if(state.screen==="menu")renderHistory();
});
window.addEventListener("resize",fitCanvas,{passive:true});
for(const racer of RACER_POOL){
  const portrait=new Image();racerPortraits.set(racer.name,portrait);
  portrait.src="assets/racers/"+racer.name.toLowerCase()+".png";
  portrait.onload=()=>{if(state.screen==="race"&&state.sim)drawCurrent();};
}
buildRacerGrid();buildArenaCards();updateSetup();updateSession();updateSoundButton();renderHistory();
const sharedValue=new URLSearchParams(location.search).get("race");
if(sharedValue){
  const shared=GameSession.decode(sharedValue);
  if(shared){openExternalRace(shared);announce("Shared race loaded. Same seed and starting grid.");}
  else {
    const message="This race link is invalid or from an older version. Choose a new race.";
    $("link-notice").textContent=message;$("link-notice").hidden=false;announce(message);
  }
}

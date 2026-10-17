"use strict";

// Seeded race links and cup scoring are independent of the DOM and clock.
// Bump this version when a physics change makes old race links incompatible.
const GameSession = (() => {
  const VERSION = 2;
  function validate(input) {
    if (!input || typeof input !== "object") return null;
    const {seed, roster, youIdx, mode, arenaSize, arena} = input;
    if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) return null;
    if (!Array.isArray(roster) || roster.length < 2 || roster.length > 8 ||
        roster.some(i => !Number.isInteger(i) || i < 0 || i >= RACER_POOL.length) ||
        new Set(roster).size !== roster.length || !roster.includes(youIdx)) return null;
    if (!["race", "drop"].includes(mode) || !["s", "m", "l"].includes(arenaSize)) return null;
    if (!(mode === "race" ? MAZE_ARENAS : DROP_ARENAS).some(a => a.id === arena)) return null;
    const finishTarget = input.finishTarget ?? 1;
    if (![1, Math.min(3, roster.length)].includes(finishTarget)) return null;
    return {seed, roster:[...roster], youIdx, mode, arenaSize, arena, finishTarget};
  }
  function encode(input) {
    const c = validate(input);
    if (!c) return null;
    return [VERSION,c.mode,c.arena,c.arenaSize,c.seed.toString(16),c.youIdx,c.roster.join("."),c.finishTarget].join("~");
  }
  function decode(value) {
    if (typeof value !== "string" || value.length > 180) return null;
    const p = value.split("~");
    if (p.length !== 8 || p[0] !== String(VERSION) || !/^[0-9a-f]{1,8}$/.test(p[4]) ||
        !/^\d{1,2}$/.test(p[5]) || !/^\d{1,2}(\.\d{1,2}){1,7}$/.test(p[6]) || !/^[1-3]$/.test(p[7])) return null;
    return validate({mode:p[1],arena:p[2],arenaSize:p[3],seed:parseInt(p[4],16),youIdx:Number(p[5]),
      roster:p[6].split(".").map(Number),finishTarget:Number(p[7])});
  }
  function makeCup(input) {
    const config = validate(input);
    if (!config) throw new Error("Invalid cup setup");
    const rng = mulberry32(config.seed ^ 0x739a4d21);
    const alternatives = (config.mode === "race" ? MAZE_ARENAS : DROP_ARENAS).map(a => a.id).filter(id => id !== config.arena);
    for (let i=alternatives.length-1;i>0;i--) { const j=Math.floor(rng()*(i+1)); [alternatives[i],alternatives[j]]=[alternatives[j],alternatives[i]]; }
    const arenas = [config.arena,...alternatives.slice(0,2)];
    const rounds = arenas.map((arena,i) => ({...config, arena, seed:i===0?config.seed:Math.floor(rng()*4294967296),
      roster:[...config.roster.slice(i),...config.roster.slice(0,i)], finishTarget:Math.min(3,config.roster.length)}));
    return {id:encode(config),round:0,rounds,results:[null,null,null],scores:RACER_POOL.map(()=>0)};
  }
  function scoreRound(cup, round, finishOrder) {
    if (!Number.isInteger(round) || !cup?.rounds?.[round] || cup.results[round] !== null) return false;
    const config=cup.rounds[round], seen=new Set();
    const finishers=finishOrder.filter(i=>Number.isInteger(i)&&i>=0&&i<config.roster.length&&!seen.has(i)&&seen.add(i)).slice(0,config.finishTarget);
    const points=finishers.map((i,place)=>({racer:config.roster[i],points:[5,3,1][place]}));
    cup.results[round]=points;
    for (const result of points) cup.scores[result.racer]+=result.points;
    return true;
  }
  function cupLeaders(cup) {
    const top=Math.max(...cup.scores);
    return top>0?cup.rounds[0].roster.filter(i=>cup.scores[i]===top):[];
  }
  function history(input) {
    if (!Array.isArray(input)) return [];
    const seen=new Set();
    return input.flatMap(entry=>{
      const config=decode(entry?.race);
      if (!config || !config.roster.includes(entry.winner) || !Number.isFinite(entry.seconds) ||
          entry.seconds<=0 || entry.seconds>120 || !Number.isFinite(entry.at) || seen.has(entry.race)) return [];
      seen.add(entry.race);
      return [{race:entry.race,winner:entry.winner,seconds:entry.seconds,at:entry.at}];
    }).sort((a,b)=>b.at-a.at).slice(0,20);
  }
  function progress(input, result=null) {
    const recent=history(input?.history);
    const races=Number.isSafeInteger(input?.races)&&input.races>=0?input.races:0;
    const wins=Number.isSafeInteger(input?.wins)&&input.wins>=0?Math.min(input.wins,races):0;
    const keys=Array.isArray(input?.countedRuns)?input.countedRuns.filter(key=>decode(key)):[];
    const next={races,wins,history:recent,countedRuns:[...new Set([...keys,...recent.slice().reverse().map(entry=>entry.race)])].slice(-200)};
    const entry=result&&typeof result.won==="boolean"?history([result])[0]:null;
    if(entry&&!next.countedRuns.includes(entry.race)){
      next.races=Math.min(Number.MAX_SAFE_INTEGER,next.races+1);
      next.wins=Math.min(next.races,next.wins+(result.won?1:0));
      next.countedRuns=[...next.countedRuns,entry.race].slice(-200);
      next.history=history([entry,...next.history]);
    }
    return next;
  }
  return Object.freeze({VERSION,validate,encode,decode,makeCup,scoreRound,cupLeaders,history,progress});
})();

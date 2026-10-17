
"use strict";

/* =========================================================================
   Seeded RNG (mulberry32) — one stream per race, plus one per racer so a
   racer's own "confusion" dice rolls don't perturb any other racer's.
   ========================================================================= */
function mulberry32(seed){
  let a = seed >>> 0;
  return function(){
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function makeRng(seed){
  const f = mulberry32(seed);
  return {
    random: f,
    int: (n) => Math.floor(f() * n),
    range: (a,b) => a + f() * (b - a),
    choice: (arr) => arr[Math.floor(f() * arr.length)],
  };
}

/* =========================================================================
   Racer roster — ported from race_sim.py RACER_POOL.
   ========================================================================= */
const RACER_POOL = [
  {name:"Blacky", color:[40,40,46],   weight:1.05, confusion:0.08},
  {name:"Sunny",  color:[250,205,45], weight:0.92, confusion:0.10},
  {name:"Cocoa",  color:[122,82,48],  weight:1.10, confusion:0.07},
  {name:"Pine",   color:[35,112,72],  weight:1.00, confusion:0.09},
  {name:"Tango",  color:[235,120,35], weight:0.95, confusion:0.12},
  {name:"Ghost",  color:[218,218,224],weight:0.88, confusion:0.11},
  {name:"Sky",    color:[55,140,225], weight:1.00, confusion:0.09},
  {name:"Rosy",   color:[232,72,150], weight:0.90, confusion:0.13},
  {name:"Cherry", color:[216,46,56],  weight:1.02, confusion:0.08},
  {name:"Minty",  color:[70,210,172], weight:0.94, confusion:0.10},
  {name:"Grape",  color:[142,82,202], weight:0.98, confusion:0.11},
  {name:"Coral",  color:[255,132,112],weight:0.90, confusion:0.14},
  {name:"Lime",   color:[172,220,52], weight:0.93, confusion:0.12},
  {name:"Slate",  color:[102,112,132],weight:1.12, confusion:0.06},
  {name:"Amber",  color:[236,166,42], weight:0.96, confusion:0.10},
  {name:"Ruby",   color:[190,32,72],  weight:1.08, confusion:0.07},
];
const rgb = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;
const darker = (c, amt=55) => `rgb(${Math.max(0,c[0]-amt)},${Math.max(0,c[1]-amt)},${Math.max(0,c[2]-amt)})`;
const lighten = (c, amt) => `rgb(${Math.round(c[0]+(255-c[0])*amt)},${Math.round(c[1]+(255-c[1])*amt)},${Math.round(c[2]+(255-c[2])*amt)})`;

const racerPortraits = new Map();
function drawRacerFace(ctx, size, color, angle=0, isYou=false, name=""){
  const portrait = racerPortraits.get(name);
  if(portrait && portrait.complete && portrait.naturalWidth){
    ctx.save();
    ctx.translate(size/2,size/2); ctx.rotate(angle);
    ctx.drawImage(portrait,-size/2,-size/2,size,size);
    ctx.restore();
    if(isYou){
      ctx.save(); ctx.beginPath(); ctx.arc(size*.84,size*.16,size*.095,0,Math.PI*2);
      ctx.fillStyle="#67e8f9"; ctx.fill(); ctx.strokeStyle="#0f172a"; ctx.lineWidth=2; ctx.stroke();
      ctx.restore();
    }
    return;
  }
  const cx = size/2, cy = size/2, r = size*0.44;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(angle);
  ctx.translate(-cx, -cy);

  const grad = ctx.createRadialGradient(cx-r*0.38, cy-r*0.42, r*0.08, cx, cy, r*1.05);
  grad.addColorStop(0, lighten(color, 0.7));
  grad.addColorStop(0.5, rgb(color));
  grad.addColorStop(1, darker(color, 60));
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI*2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.lineWidth = Math.max(1.5, size*0.03);
  ctx.strokeStyle = darker(color, 85);
  ctx.stroke();

  // faint rotating seam so spin from collisions still reads visually
  ctx.beginPath();
  ctx.strokeStyle = `${darker(color, 35)}`;
  ctx.globalAlpha = 0.35;
  ctx.lineWidth = Math.max(1, size*0.02);
  ctx.arc(cx, cy, r*0.78, 0.15*Math.PI, 0.85*Math.PI);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // glossy specular highlight (view-fixed, not rotated with the marble)
  ctx.restore();
  ctx.save();
  const hlx = cx - r*0.38, hly = cy - r*0.42;
  const hl = ctx.createRadialGradient(hlx, hly, 0, hlx, hly, r*0.55);
  hl.addColorStop(0, "rgba(255,255,255,0.65)");
  hl.addColorStop(1, "rgba(255,255,255,0)");
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI*2);
  ctx.clip();
  ctx.fillStyle = hl;
  ctx.fillRect(0, 0, size, size);
  ctx.restore();

  if (isYou){
    ctx.save();
    ctx.fillStyle = "#0a84ff";
    ctx.strokeStyle = "#08111d";
    ctx.lineWidth = Math.max(1, size*0.02);
    const bx = size*0.82, by = size*0.16, r2 = size*0.11;
    ctx.beginPath();
    for(let i=0;i<5;i++){
      const a1 = -Math.PI/2 + i*(2*Math.PI/5);
      const a2 = a1 + Math.PI/5;
      const x1 = bx + Math.cos(a1)*r2, y1 = by + Math.sin(a1)*r2;
      const x2 = bx + Math.cos(a2)*r2*0.45, y2 = by + Math.sin(a2)*r2*0.45;
      i===0? ctx.moveTo(x1,y1) : ctx.lineTo(x1,y1);
      ctx.lineTo(x2,y2);
    }
    ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
  }
}

/* =========================================================================
   Maze generation — DFS spanning tree + loops + rooms + BFS distance field.
   Ported from generate_maze / add_loops / carve_rooms / bfs_distance_field.
   ========================================================================= */
function generateMaze(cols, rows, rng){
  const openRight = Array.from({length:rows}, ()=>new Array(Math.max(0,cols-1)).fill(false));
  const openDown  = Array.from({length:Math.max(0,rows-1)}, ()=>new Array(cols).fill(false));
  const visited   = Array.from({length:rows}, ()=>new Array(cols).fill(false));
  const start = [0, rng.int(cols)];
  const stack = [start];
  visited[start[0]][start[1]] = true;
  while(stack.length){
    const [r,c] = stack[stack.length-1];
    const nb = [];
    if (c>0 && !visited[r][c-1]) nb.push(["L",r,c-1]);
    if (c<cols-1 && !visited[r][c+1]) nb.push(["R",r,c+1]);
    if (r>0 && !visited[r-1][c]) nb.push(["U",r-1,c]);
    if (r<rows-1 && !visited[r+1][c]) nb.push(["D",r+1,c]);
    if (!nb.length){ stack.pop(); continue; }
    const [dir,nr,nc] = nb[rng.int(nb.length)];
    visited[nr][nc] = true;
    if (dir==="L") openRight[r][c-1] = true;
    else if (dir==="R") openRight[r][c] = true;
    else if (dir==="U") openDown[r-1][c] = true;
    else openDown[r][c] = true;
    stack.push([nr,nc]);
  }
  return {openRight, openDown};
}
function addLoops(openRight, openDown, cols, rows, rng, p=0.12){
  for(let r=0;r<rows;r++) for(let c=0;c<cols-1;c++)
    if (!openRight[r][c] && rng.random()<p) openRight[r][c]=true;
  for(let r=0;r<rows-1;r++) for(let c=0;c<cols;c++)
    if (!openDown[r][c] && rng.random()<p) openDown[r][c]=true;
}
function carveRooms(openRight, openDown, cols, rows, rng){
  const roomCount = Math.max(2, Math.floor((cols*rows)/45));
  for(let i=0;i<roomCount;i++){
    const rw = 2 + rng.int(2), rh = 2 + rng.int(2);
    if (cols<=rw || rows<=rh) continue;
    const c0 = cols-rw-1>0 ? rng.int(cols-rw-1) : 0;
    const r0 = rows-rh-1>0 ? rng.int(rows-rh-1) : 0;
    for(let r=r0;r<r0+rh;r++) for(let c=c0;c<c0+rw-1;c++) openRight[r][c]=true;
    for(let r=r0;r<r0+rh-1;r++) for(let c=c0;c<c0+rw;c++) openDown[r][c]=true;
  }
}
function bfsDistanceField(openRight, openDown, cols, rows, finishCell){
  const dist = Array.from({length:rows}, ()=>new Array(cols).fill(null));
  const [fr,fc] = finishCell;
  dist[fr][fc] = 0;
  const q = [[fr,fc]]; let qi = 0;
  while(qi<q.length){
    const [r,c] = q[qi++];
    const d = dist[r][c];
    if (c>0 && openRight[r][c-1] && dist[r][c-1]===null){ dist[r][c-1]=d+1; q.push([r,c-1]); }
    if (c<cols-1 && openRight[r][c] && dist[r][c+1]===null){ dist[r][c+1]=d+1; q.push([r,c+1]); }
    if (r>0 && openDown[r-1][c] && dist[r-1][c]===null){ dist[r-1][c]=d+1; q.push([r-1,c]); }
    if (r<rows-1 && openDown[r][c] && dist[r+1][c]===null){ dist[r+1][c]=d+1; q.push([r+1,c]); }
  }
  return dist;
}
function openNeighbors(r,c,openRight,openDown,cols,rows){
  const out = [];
  if (c>0 && openRight[r][c-1]) out.push([r,c-1]);
  if (c<cols-1 && openRight[r][c]) out.push([r,c+1]);
  if (r>0 && openDown[r-1][c]) out.push([r-1,c]);
  if (r<rows-1 && openDown[r][c]) out.push([r+1,c]);
  return out;
}

/* =========================================================================
   Geometry
   ========================================================================= */
function makeGeo(w, cols, rows){
  const borderW = w*0.05;
  const cell = (w - 2*borderW)/cols;
  const wallThickness = cell*0.16;
  const racerRadius = (cell - wallThickness)*0.30;
  const topBorder = borderW;
  const finishDepth = cell*1.3;
  const bottomBorder = borderW;
  const imgH = topBorder + rows*cell + finishDepth + bottomBorder;
  return {
    cols, rows, w, borderW, cell, wallThickness, racerRadius, topBorder, finishDepth, bottomBorder, imgH,
    cellLeft:(c)=>borderW + c*cell,
    cellTop:(r)=>topBorder + r*cell,
    cellCenter(r,c){ return [this.cellLeft(c)+cell/2, this.cellTop(r)+cell/2]; },
    finishZoneCenter(finishCol){
      const x = this.cellLeft(finishCol)+cell/2;
      const y = topBorder + rows*cell + finishDepth/2;
      return [x,y];
    }
  };
}
function buildWallSegments(geo, openRight, openDown, finishCol){
  const {cols, rows, cell} = geo;
  const left = geo.borderW, right = geo.w-geo.borderW;
  const top = geo.topBorder, bottom = geo.topBorder + rows*cell;
  const zoneBottom = bottom + geo.finishDepth;
  const segs = [[left,top,right,top]];
  const fx0 = geo.cellLeft(finishCol), fx1 = fx0+cell;
  if (fx0>left) segs.push([left,bottom,fx0,bottom]);
  if (fx1<right) segs.push([fx1,bottom,right,bottom]);
  segs.push([left,bottom,left,zoneBottom]);
  segs.push([right,bottom,right,zoneBottom]);
  segs.push([left,zoneBottom,right,zoneBottom]);
  segs.push([left,top,left,bottom]);
  segs.push([right,top,right,bottom]);
  for(let r=0;r<rows;r++) for(let c=0;c<cols-1;c++)
    if (!openRight[r][c]){ const x=geo.cellLeft(c+1); segs.push([x,geo.cellTop(r),x,geo.cellTop(r)+cell]); }
  for(let r=0;r<rows-1;r++) for(let c=0;c<cols;c++)
    if (!openDown[r][c]){ const y=geo.cellTop(r+1); segs.push([geo.cellLeft(c),y,geo.cellLeft(c)+cell,y]); }
  return segs;
}

/* =========================================================================
   Simulation — circle-body physics (collision is circle-based for numeric
   robustness; racers are still drawn as rotated squares, with spin driven
   by an angular-velocity approximation from tangential collision impulse,
   for the same "reads as real hits" look as the video pipeline's square
   pymunk bodies without needing full polygon collision in the browser).
   ========================================================================= */
const PHYSICS_HZ = 120;
const DT = 1/PHYSICS_HZ;
const ARENA_PRESETS = { s:{cols:6, rowsBase:12}, m:{cols:7, rowsBase:15}, l:{cols:8, rowsBase:19} };
const MAZE_ARENAS = [
  {id:"classic", name:"Neon Labyrinth", description:"Tight turns, hidden shortcuts, close finishes.", accent:"#57d9ff", icon:"◈"},
  {id:"open_rooms", name:"Garden Circuit", description:"Open chambers with room to overtake.", accent:"#53e1b7", icon:"▦"},
  {id:"switchback", name:"Amber Switchback", description:"Sweeping lanes and alternating hairpin turns.", accent:"#ffc368", icon:"⇄"},
  {id:"crossroads", name:"Violet Crossroads", description:"Fast central lanes meet branching routes.", accent:"#b89aff", icon:"✣"},
];

function buildMazeLayout(cols, rows, rng, kind){
  if(kind === "switchback"){
    // Two-cell-wide lanes join at alternating ends. Every cell has a path
    // to every other cell; the last band remains open to any finish column.
    const openRight=Array.from({length:rows},()=>Array(cols-1).fill(true));
    const reverse=rng.int(2);
    const openDown=Array.from({length:rows-1},(_,r)=>Array.from({length:cols},(_,c)=>
      r%2===0 || ((Math.floor(r/2)+reverse)%2===0 ? c<2 : c>=cols-2)));
    return {openRight,openDown};
  }
  const maze=generateMaze(cols,rows,rng);
  const {openRight,openDown}=maze;
  addLoops(openRight,openDown,cols,rows,rng,kind==="open_rooms"?.20:.12);
  carveRooms(openRight,openDown,cols,rows,rng);
  if(kind==="open_rooms"){
    for(let r=2;r<rows-2;r+=5){
      const c0=rng.int(Math.max(1,cols-3));
      for(let rr=r;rr<Math.min(rows-1,r+3);rr++){
        for(let c=c0;c<Math.min(cols-1,c0+3);c++) openRight[rr][c]=true;
        if(rr<r+2) for(let c=c0;c<Math.min(cols,c0+4);c++) openDown[rr][c]=true;
      }
    }
  }
  if(kind==="crossroads"){
    const mid=Math.floor(cols/2);
    for(let r=0;r<rows-1;r++) for(const c of [mid-1,mid]) openDown[r][c]=true;
    for(let r=3;r<rows;r+=5){
      for(let c=0;c<cols-1;c++) openRight[r][c]=true;
      if(r+1<rows) for(let c=0;c<cols-1;c++) openRight[r+1][c]=true;
    }
  }
  return maze;
}

function buildRace(seed, roster, arenaSize, arenaKind="classic"){
  if(!MAZE_ARENAS.some(arena=>arena.id===arenaKind)) arenaKind="classic";
  const rng = makeRng(seed);
  const preset = ARENA_PRESETS[arenaSize] || ARENA_PRESETS.m;
  const n = roster.length;
  const cols = preset.cols;
  const rows = Math.max(10, Math.min(22, preset.rowsBase + Math.floor((n-6)/2)));

  // Keep all 32 seed bits: floating multiplication loses low bits for large seeds.
  const mazeRng = makeRng(Math.imul(seed,2654435761) >>> 0);
  const {openRight, openDown} = buildMazeLayout(cols, rows, mazeRng, arenaKind);
  const finishCol = mazeRng.int(cols);
  const finishCell = [rows-1, finishCol];
  const distField = bfsDistanceField(openRight, openDown, cols, rows, finishCell);
  const candidates = [];
  for(let r=0;r<Math.max(2,Math.ceil(n/cols));r++) for(let c=0;c<cols;c++) candidates.push([r,c]);
  candidates.sort((a,b)=>distField[a[0]][a[1]]-distField[b[0]][b[1]] || a[0]-b[0] || a[1]-b[1]);
  let spawnCells=candidates.slice(0,n), bestSpread=Infinity, bestDepth=Infinity;
  for(let i=0;i<=candidates.length-n;i++){
    const group=candidates.slice(i,i+n);
    const spread=distField[group[n-1][0]][group[n-1][1]]-distField[group[0][0]][group[0][1]];
    const depth=group.reduce((sum,p)=>sum+p[0],0);
    if(spread<bestSpread || (spread===bestSpread && depth<bestDepth)){
      spawnCells=group; bestSpread=spread; bestDepth=depth;
    }
  }
  const startRng=makeRng((seed^0x51f15e)>>>0);
  for(let i=spawnCells.length-1;i>0;i--){const j=startRng.int(i+1); [spawnCells[i],spawnCells[j]]=[spawnCells[j],spawnCells[i]];}

  const stageW = 900; // logical px, canvas scales to container via devicePixelRatio
  const geo = makeGeo(stageW, cols, rows);
  const walls = buildWallSegments(geo, openRight, openDown, finishCol);
  const [fzx, fzy] = geo.finishZoneCenter(finishCol);

  const racers = roster.map((r,i)=>{
    const [sr,sc] = spawnCells[i];
    const [cx,cy] = geo.cellCenter(sr,sc);
    const prng = makeRng((seed + i*97 + 13) >>> 0);
    return {
      ...r, idx:i,
      x: cx + prng.range(-6,6), y: cy + prng.range(-6,6),
      vx:0, vy:0, angle: prng.range(0, Math.PI*2), angularVel:0,
      lastCell:[sr,sc], target:[cx,cy],
      finished:false, active:true, finishStep:null,
      recoveryUntil:0, rng:prng,
      stuckCheckPos:null, stuckCounter:0,
      progressLastDist:null, progressStall:0,
    };
  });

  function recomputeTarget(rc){
    const [r,c] = rc.lastCell;
    if (r===finishCell[0] && c===finishCell[1]){ rc.target=[fzx,fzy]; return false; }
    const cands = openNeighbors(r,c,openRight,openDown,cols,rows);
    if (!cands.length) return false;
    let best = Infinity;
    for (const [nr,nc] of cands) if (distField[nr][nc]<best) best = distField[nr][nc];
    const bestCands = cands.filter(([nr,nc])=>distField[nr][nc]===best);
    let choice;
    if (cands.length>1 && rc.rng.random()<rc.confusion) choice = cands[rc.rng.int(cands.length)];
    else choice = bestCands[rc.rng.int(bestCands.length)];
    rc.target = geo.cellCenter(choice[0], choice[1]);
    return cands.length>1;
  }
  racers.forEach(recomputeTarget);

  return {
    seed, arenaKind, geo, walls, racers, finishCell, finishCol, fzx, fzy, cols, rows,
    openRight, openDown, distField,
    spawnCells, viewportH:Math.min(1180,geo.imgH), cameraY:0, followYou:false,
    recomputeTarget,
    step:0, winner:null, finishedCount:0, finishOrder:[], finishTarget:1, complete:false, bumps:[],
  };
}

const MAX_SPEED_FACTOR = 1/0.42;
const STEER_GAIN = 7.5;
const JITTER_HZ_SCALE = 3.0;
const REPEL_RADIUS_CELLS = 1.6;
const REPEL_STRENGTH = 1200.0;
const RECOVERY_STEPS = Math.round(0.30*PHYSICS_HZ);
const RECOVERY_MIN = 0.12;
const JUNCTION_HESITATE_STEPS = Math.round(0.15*PHYSICS_HZ);
const STUCK_CHECK_STEPS = Math.round(0.5*PHYSICS_HZ);
const PROGRESS_CHECK_STEPS = Math.round(1.2*PHYSICS_HZ);

function wallBlocks(race, from, to, radius=0){
  const pad = race.geo.wallThickness/2 + radius;
  return race.walls.some(([x1,y1,x2,y2])=>{
    if(Math.max(from[0],to[0])<Math.min(x1,x2)-pad || Math.min(from[0],to[0])>Math.max(x1,x2)+pad ||
       Math.max(from[1],to[1])<Math.min(y1,y2)-pad || Math.min(from[1],to[1])>Math.max(y1,y2)+pad) return false;
    let lo=0, hi=1;
    const mins=[Math.min(x1,x2)-pad, Math.min(y1,y2)-pad];
    const maxs=[Math.max(x1,x2)+pad, Math.max(y1,y2)+pad];
    for(let k=0;k<2;k++){
      const delta=to[k]-from[k];
      if(Math.abs(delta)<1e-9){ if(from[k]<mins[k]||from[k]>maxs[k]) return false; }
      else {
        let a=(mins[k]-from[k])/delta, b=(maxs[k]-from[k])/delta;
        if(a>b) [a,b]=[b,a];
        lo=Math.max(lo,a); hi=Math.min(hi,b);
        if(lo>hi) return false;
      }
    }
    return true;
  });
}

function updateRaceCamera(sim, focusY, worldH){
  const maxY=Math.max(0,worldH-sim.viewportH);
  const target=Math.max(0,Math.min(maxY,focusY-sim.viewportH*.42));
  const smoothed=sim.complete ? target : sim.cameraY+(target-sim.cameraY)*.045;
  // Fast drops can outrun smoothing in a short landscape viewport. Keep
  // the followed sprite inside the frame while retaining smooth tracking.
  const radius=sim.geo?.racerRadius??sim.racerRadius??0;
  const margin=Math.min(sim.viewportH/2,Math.max(sim.viewportH*.12,radius*1.4));
  const framed=Math.max(focusY-sim.viewportH+margin,Math.min(focusY-margin,smoothed));
  sim.cameraY=Math.max(0,Math.min(maxY,framed));
}

function recordFinishCrossings(sim, active, previousY, radius, lineY){
  const centerLine=lineY-radius;
  const crossings=active.filter(r=>r.y>=centerLine).map(r=>{
    const start=previousY.get(r), travelled=r.y-start;
    const fraction=start>=centerLine?0:Math.max(0,Math.min(1,(centerLine-start)/travelled));
    return {r,fraction};
  });
  // Interpolate within this physics step; roster order only breaks exact ties.
  crossings.sort((a,b)=>a.fraction-b.fraction || a.r.idx-b.r.idx);
  for(const {r,fraction} of crossings){
    r.finished=true; r.active=false; r.finishStep=sim.step-1+fraction;
    sim.finishOrder.push(r.idx);
    sim.finishedCount++;
    if(!sim.winner) sim.winner=r;
    sim.resultReason="finish";
  }
  const target=Math.min(sim.racers.length,Math.max(1,Math.floor(sim.finishTarget)||1));
  sim.complete=sim.finishedCount>=target;
}

function drawSelectedRacerIndicator(ctx,sim,youIdx,width,viewportH,cameraY,radius){
  const selected=sim.racers[youIdx];
  if(!selected) return;
  const above=selected.y+radius<cameraY, below=selected.y-radius>cameraY+viewportH;
  if(!above&&!below) return;
  const font=Math.max(14,width*.022), badgeW=font*10.5, badgeH=font*2.1;
  const x=Math.max(badgeW/2+8,Math.min(width-badgeW/2-8,selected.x));
  const y=above?badgeH/2+10:viewportH-badgeH/2-10;
  ctx.save();
  ctx.beginPath();ctx.roundRect(x-badgeW/2,y-badgeH/2,badgeW,badgeH,10);
  ctx.fillStyle="rgba(8,18,32,.94)";ctx.fill();ctx.strokeStyle="#67e8f9";ctx.lineWidth=2;ctx.stroke();
  ctx.fillStyle="#e9f8ff";ctx.textAlign="center";ctx.textBaseline="middle";
  ctx.font=`700 ${font}px system-ui,sans-serif`;
  ctx.fillText(`${above?"↑":"↓"} YOU · ${selected.name}`,x,y);
  ctx.restore();
}

function recordTrails(sim){
  if(sim.step%6!==0) return;
  for(const racer of sim.racers){
    racer.trail ||= [];
    racer.trail.push([racer.x,racer.y]);
    if(racer.trail.length>12) racer.trail.shift();
  }
}

function drawTrails(ctx,sim,radius,youIdx){
  ctx.save(); ctx.lineCap="round"; ctx.lineJoin="round";
  for(const racer of sim.racers){
    if(!racer.trail || racer.trail.length<2) continue;
    ctx.beginPath();
    racer.trail.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));
    ctx.strokeStyle=rgb(racer.color); ctx.globalAlpha=racer.idx===youIdx?.40:.16;
    ctx.lineWidth=radius*(racer.idx===youIdx?.55:.28); ctx.stroke();
  }
  ctx.restore();
}

function navigationTarget(race, rc){
  const {geo}=race;
  rc.motionHistory ||= [];
  if(race.step%30===0){
    rc.motionHistory.push([rc.x,rc.y]);
    if(rc.motionHistory.length>7) rc.motionHistory.shift();
    if(rc.motionHistory.length===7 && race.step>=(rc.escapeUntil||0)){
      const span=Math.max(...[0,1].map(k=>Math.max(...rc.motionHistory.map(p=>p[k]))-Math.min(...rc.motionHistory.map(p=>p[k]))));
      if(span<geo.racerRadius*1.5){
        const choices=openNeighbors(...rc.lastCell,race.openRight,race.openDown,race.cols,race.rows);
        const others=race.racers.filter(r=>r!==rc&&r.active);
        const score=cell=>{
          const p=geo.cellCenter(...cell);
          const room=Math.min(geo.cell*3,...others.map(r=>Math.hypot(p[0]-r.x,p[1]-r.y)));
          return room+Math.min(geo.cell,Math.hypot(p[0]-rc.target[0],p[1]-rc.target[1]))*.5;
        };
        choices.sort((a,b)=>score(b)-score(a));
        if(choices.length){
          rc.escapeTarget=geo.cellCenter(...choices[0]);
          rc.escapeUntil=race.step+102;
          const dx=rc.escapeTarget[0]-rc.x,dy=rc.escapeTarget[1]-rc.y,dist=Math.hypot(dx,dy)||1;
          rc.vx+=dx/dist*geo.cell*.9; rc.vy+=dy/dist*geo.cell*.9;
          rc.motionHistory=[];
        }
      }
    }
  }
  const target=race.step<(rc.escapeUntil||0)?rc.escapeTarget:rc.target;
  return wallBlocks(race,[rc.x,rc.y],target,geo.racerRadius*.85)?geo.cellCenter(...rc.lastCell):target;
}

function stepRace(race, tSec){
  if(race.complete) return;
  const {geo, racers, walls} = race;
  race.step++;
  const step = race.step;
  const MAX_SPEED = geo.cell*MAX_SPEED_FACTOR;
  const SLOWDOWN_RADIUS = geo.cell*0.55;
  const REPEL_RADIUS = geo.cell*REPEL_RADIUS_CELLS;
  const REPEL_GATE = MAX_SPEED*0.25;

  const active = racers.filter(r=>r.active);
  const previousY = new Map(active.map(r=>[r,r.y]));
  const repel = new Map(active.map(r=>[r,[0,0]]));
  for(let a=0;a<active.length;a++) for(let b=a+1;b<active.length;b++){
    const ra=active[a], rb=active[b];
    const dx=ra.x-rb.x, dy=ra.y-rb.y;
    const d=Math.hypot(dx,dy);
    if (d>0 && d<REPEL_RADIUS){
      const nx=dx/d, ny=dy/d;
      const closing = -((ra.vx-rb.vx)*nx + (ra.vy-rb.vy)*ny);
      if (closing>REPEL_GATE) continue;
      if (wallBlocks(race,[ra.x,ra.y],[rb.x,rb.y])) continue;
      const strength = REPEL_STRENGTH*(1-d/REPEL_RADIUS);
      const fa = repel.get(ra), fb = repel.get(rb);
      fa[0]+=nx*strength; fa[1]+=ny*strength;
      fb[0]-=nx*strength; fb[1]-=ny*strength;
    }
  }

  for (const rc of active){
    const [rr,cc] = [
      Math.min(race.rows-1, Math.max(0, Math.floor((rc.y-geo.topBorder)/geo.cell))),
      Math.min(race.cols-1, Math.max(0, Math.floor((rc.x-geo.borderW)/geo.cell))),
    ];
    if ((rr!==rc.lastCell[0] || cc!==rc.lastCell[1]) && rc.y < geo.topBorder+race.rows*geo.cell){
      rc.lastCell=[rr,cc];
      if (race.recomputeTarget(rc)) rc.recoveryUntil = Math.max(rc.recoveryUntil, step+JUNCTION_HESITATE_STEPS);
    }

    const [tx,ty] = navigationTarget(race, rc);
    const dx=tx-rc.x, dy=ty-rc.y;
    const dist = Math.hypot(dx,dy)||1;
    const speedScale = Math.min(1, Math.max(0.35, dist/SLOWDOWN_RADIUS));
    const speedMult = 1 + (1-rc.weight)*0.6;
    const steerMult = 1 - (rc.weight-1)*0.5;
    const desiredVx = dx/dist*MAX_SPEED*speedMult*speedScale;
    const desiredVy = dy/dist*MAX_SPEED*speedMult*speedScale;
    let steerGain = STEER_GAIN*steerMult;
    if (step < rc.recoveryUntil){
      const remaining = (rc.recoveryUntil-step)/RECOVERY_STEPS;
      steerGain *= RECOVERY_MIN + (1-RECOVERY_MIN)*(1-remaining);
    }
    const steerX = (desiredVx-rc.vx)*steerGain;
    const steerY = (desiredVy-rc.vy)*steerGain;
    const jitterAng = Math.sin(tSec*JITTER_HZ_SCALE + rc.idx*1.7) * rc.rng.range(0.5,1.0);
    const jitterMag = rc.weight*3.2;
    const [rfx,rfy] = repel.get(rc);
    const fx = rc.weight*steerX + Math.cos(jitterAng)*jitterMag + rfx;
    const fy = rc.weight*steerY + Math.sin(jitterAng)*jitterMag + rfy;
    rc.vx += fx*DT/rc.weight;
    rc.vy += fy*DT/rc.weight;
    rc.vx *= Math.pow(0.996,DT); rc.vy *= Math.pow(0.996,DT);
  }

  // integrate + wall collisions
  for (const rc of active){
    rc.x += rc.vx*DT; rc.y += rc.vy*DT;
    for (const [x1,y1,x2,y2] of walls){
      const collisionPad=geo.racerRadius+geo.wallThickness/2;
      if(rc.x<Math.min(x1,x2)-collisionPad || rc.x>Math.max(x1,x2)+collisionPad ||
         rc.y<Math.min(y1,y2)-collisionPad || rc.y>Math.max(y1,y2)+collisionPad) continue;
      const wdx=x2-x1, wdy=y2-y1;
      const len2 = wdx*wdx+wdy*wdy || 1;
      let t = ((rc.x-x1)*wdx + (rc.y-y1)*wdy)/len2;
      t = Math.max(0, Math.min(1, t));
      const px = x1+t*wdx, py = y1+t*wdy;
      const dx = rc.x-px, dy = rc.y-py;
      const d = Math.hypot(dx,dy);
      const minD = geo.racerRadius + geo.wallThickness/2;
      if (d < minD && d>0.0001){
        const nx=dx/d, ny=dy/d;
        const overlap = minD-d;
        rc.x += nx*overlap; rc.y += ny*overlap;
        const vn = rc.vx*nx+rc.vy*ny;
        if (vn<0){
          rc.vx -= (1+0.42)*vn*nx;
          rc.vy -= (1+0.42)*vn*ny;
          const tangential = -rc.vx*ny+rc.vy*nx;
          rc.angularVel += tangential*0.012;
          if (Math.abs(vn)>1.2 && race.bumps.length<220)
            race.bumps.push({x:rc.x,y:rc.y,born:tSec,kind:"wall",intensity:Math.min(1,Math.abs(vn)/260)});
        }
      }
    }
  }
  // racer-racer collisions
  for(let a=0;a<active.length;a++) for(let b=a+1;b<active.length;b++){
    const ra=active[a], rb=active[b];
    const dx=rb.x-ra.x, dy=rb.y-ra.y;
    const d=Math.hypot(dx,dy);
    const minD = geo.racerRadius*2*0.92;
    if (d<minD && d>0.0001){
      const nx=dx/d, ny=dy/d;
      const overlap=(minD-d)/2;
      ra.x-=nx*overlap; ra.y-=ny*overlap; rb.x+=nx*overlap; rb.y+=ny*overlap;
      const rvx=rb.vx-ra.vx, rvy=rb.vy-ra.vy;
      const velAlongNormal = rvx*nx+rvy*ny;
      if (velAlongNormal<0){
        const e=0.92;
        const jImp = -(1+e)*velAlongNormal / (1/ra.weight+1/rb.weight);
        const ix=jImp*nx, iy=jImp*ny;
        ra.vx-=ix/ra.weight; ra.vy-=iy/ra.weight;
        rb.vx+=ix/rb.weight; rb.vy+=iy/rb.weight;
        const impulse = Math.abs(jImp);
        ra.angularVel -= impulse*0.01/ra.weight;
        rb.angularVel += impulse*0.01/rb.weight;
        if (impulse>3 && race.bumps.length<220)
          race.bumps.push({x:(ra.x+rb.x)/2,y:(ra.y+rb.y)/2,born:tSec,kind:"racer",intensity:Math.min(1,impulse/60)});
        if (impulse>1.5){
          const until = step+RECOVERY_STEPS;
          ra.recoveryUntil=Math.max(ra.recoveryUntil,until);
          rb.recoveryUntil=Math.max(rb.recoveryUntil,until);
        }
      }
    }
  }

  for (const rc of active){
    rc.angle += rc.angularVel*DT;
    rc.angularVel *= 0.94;
  }
  recordFinishCrossings(race,active,previousY,geo.racerRadius,geo.topBorder+race.rows*geo.cell+geo.finishDepth*.45);

  // stuck / progress-stall recovery
  if (step % STUCK_CHECK_STEPS === 0){
    for (const rc of racers){
      if (!rc.active) continue;
      const prev = rc.stuckCheckPos;
      rc.stuckCheckPos = [rc.x, rc.y];
      if (!prev) continue;
      const moved = Math.hypot(rc.x-prev[0], rc.y-prev[1]);
      if (moved < geo.racerRadius*0.7) rc.stuckCounter++; else rc.stuckCounter=0;
      if (rc.stuckCounter>=3){
        const [tx,ty]=rc.target;
        const dx=tx-rc.x, dy=ty-rc.y, dd=Math.hypot(dx,dy)||1;
        const nudge = MAX_SPEED*rc.weight*0.9;
        rc.vx += dx/dd*nudge/rc.weight; rc.vy += dy/dd*nudge/rc.weight;
        rc.recoveryUntil=0; rc.stuckCounter=0;
      }
    }
  }
  if (step % PROGRESS_CHECK_STEPS === 0){
    for (const rc of racers){
      if (!rc.active) continue;
      const [r,c]=rc.lastCell;
      const curDist = race.distField[r][c];
      if (curDist==null) continue;
      const prevDist = rc.progressLastDist;
      rc.progressLastDist = curDist;
      if (prevDist!=null && curDist>=prevDist) rc.progressStall++; else rc.progressStall=0;
      if (rc.progressStall>=2){
        const [tx,ty]=rc.target;
        const dx=tx-rc.x, dy=ty-rc.y, dd=Math.hypot(dx,dy)||1;
        const ndx=dx/dd, ndy=dy/dd;
        const side = rc.rng.random()<0.5?-1:1;
        const sdx=-ndy*side, sdy=ndx*side;
        const nudge = MAX_SPEED*rc.weight*1.4;
        rc.vx += (ndx*0.6+sdx*0.7)*nudge/rc.weight;
        rc.vy += (ndy*0.6+sdy*0.7)*nudge/rc.weight;
        rc.recoveryUntil=0; rc.progressStall=0;
      }
    }
  }
  recordTrails(race);
  const contenders=racers.filter(r=>r.active), pool=contenders.length?contenders:racers;
  const selected=racers[race.youIdx];
  const focus=(race.complete&&race.winner) || (race.followYou&&selected?.active&&selected) ||
    pool.reduce((best,r)=>race.distField[r.lastCell[0]][r.lastCell[1]]<race.distField[best.lastCell[0]][best.lastCell[1]]?r:best,pool[0]);
  updateRaceCamera(race,focus.y,geo.imgH);
}

/* =========================================================================
   Rendering
   ========================================================================= */
function drawMazeBackground(ctx, race){
  const {geo, walls, cols, rows} = race;
  const palette=MAZE_ARENAS.find(arena=>arena.id===race.arenaKind)||MAZE_ARENAS[0];
  const accent=palette.accent;
  const gradient=ctx.createLinearGradient(0,0,geo.w,geo.imgH);
  gradient.addColorStop(0,"#182335"); gradient.addColorStop(1,"#0b1421");
  ctx.fillStyle = gradient;
  ctx.fillRect(0,0,geo.w,geo.imgH);
  // Low-contrast floor panels make the route readable without imitating walls.
  for(let r=0;r<rows;r++) for(let c=0;c<cols;c++){
    ctx.fillStyle=(r+c)%2?"rgba(255,255,255,.018)":"rgba(255,255,255,.035)";
    ctx.fillRect(geo.cellLeft(c)+5,geo.cellTop(r)+5,geo.cell-10,geo.cell-10);
    const [x,y]=geo.cellCenter(r,c);
    ctx.beginPath(); ctx.arc(x,y,2.1,0,Math.PI*2); ctx.fillStyle="rgba(181,205,230,.18)"; ctx.fill();
  }
  ctx.save(); ctx.strokeStyle=accent; ctx.lineWidth=2.5; ctx.setLineDash([6,8]);
  for(const [r,c] of race.spawnCells){
    const [x,y]=geo.cellCenter(r,c); ctx.beginPath(); ctx.arc(x,y,geo.racerRadius*1.18,0,Math.PI*2); ctx.stroke();
  }
  ctx.restore();
  ctx.lineCap="round"; ctx.lineJoin="round";
  const path=()=>{ctx.beginPath();for(const [x1,y1,x2,y2] of walls){ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);}};
  ctx.save(); ctx.translate(0,geo.wallThickness*.35); ctx.strokeStyle="rgba(0,0,0,.45)";ctx.lineWidth=geo.wallThickness*1.5;path();ctx.stroke();ctx.restore();
  ctx.strokeStyle="#455b73";ctx.lineWidth=geo.wallThickness;path();ctx.stroke();
  ctx.strokeStyle=accent;ctx.globalAlpha=.65;ctx.lineWidth=geo.wallThickness*.36;path();ctx.stroke();ctx.globalAlpha=1;
  const zy0=geo.topBorder+rows*geo.cell;
  drawFinishLine(ctx,geo.borderW,geo.w-geo.borderW,zy0+geo.finishDepth*.45,geo.cell/7,accent);
  ctx.fillStyle=accent;ctx.textAlign="center";ctx.textBaseline="middle";
  ctx.font=`700 ${Math.round(geo.cell*.22)}px system-ui,sans-serif`;
  ctx.fillText("FINISH",geo.w/2,zy0+geo.finishDepth*.77);
}

function drawFinishLine(ctx,left,right,y,tile,accent){
  ctx.save(); ctx.fillStyle=accent; ctx.globalAlpha=.12;
  ctx.fillRect(left,y-tile*3,right-left,tile*6); ctx.globalAlpha=1;
  for(let row=0;row<2;row++) for(let x=left,i=0;x<right;x+=tile,i++){
    ctx.fillStyle=(i+row)%2?"#152131":"#e9f8ff";
    ctx.fillRect(x,y-tile+row*tile,Math.min(tile,right-x),tile);
  }
  ctx.restore();
}

function drawRace(ctx, race, offscreen, tSec, youIdx){
  const {geo} = race;
  const viewportH=race.viewportH||geo.imgH, cameraY=race.cameraY||0;
  ctx.clearRect(0,0,geo.w,viewportH);
  ctx.drawImage(offscreen,0,cameraY,geo.w,viewportH,0,0,geo.w,viewportH);
  ctx.save(); ctx.translate(0,-cameraY);
  drawTrails(ctx,race,geo.racerRadius,youIdx);

  for (const b of race.bumps){
    const age = tSec-b.born;
    if (age>0.35) continue;
    const alpha = (1-age/0.35)*0.6*b.intensity;
    ctx.beginPath();
    ctx.fillStyle = b.kind==="wall" ? `rgba(255,159,10,${alpha})` : `rgba(255,69,58,${alpha})`;
    ctx.arc(b.x,b.y, geo.racerRadius*(0.6+age*2.2), 0, Math.PI*2);
    ctx.fill();
  }
  race.bumps = race.bumps.filter(b=>tSec-b.born<=0.35);

  const s = geo.racerRadius*2.35;
  for (const rc of race.racers){
    if (!rc.active && !rc.finished) continue;
    ctx.save();
    ctx.translate(rc.x-s/2, rc.y-s/2);
    ctx.shadowColor = "rgba(0,0,0,0.28)"; ctx.shadowBlur = 5; ctx.shadowOffsetY=2;
    drawRacerFace(ctx, s, rc.color, rc.angle, rc.idx===youIdx, rc.name);
    ctx.restore();
  }
  ctx.restore();
  drawSelectedRacerIndicator(ctx,race,youIdx,geo.w,viewportH,cameraY,geo.racerRadius);
}

/* =========================================================================
   Drop mode — gravity + staggered peg field + spinning blades. Ported from
   simulate_drop / _build_drop_pegs / _drop_peg_keep. Racer bodies are
   treated as circles (same simplification as Race mode) colliding with
   circular pegs and rotating blade segments.
   ========================================================================= */
const DROP_CANDY_COLORS = [
  [255,105,180],[70,220,90],[60,220,235],[255,220,40],[255,140,30],[185,90,240],
];
const DROP_OBSTACLE_COLORS = [[255,140,30],[255,255,255],[185,90,240]];
const DROP_ARENAS = [
  {id:"classic_plinko",name:"Skyfall Plinko",description:"A classic peg field with two spinning surprises.",accent:"#57d9ff",icon:"⠿"},
  {id:"chevron_funnel",name:"Golden Funnel",description:"Wide gates gather the field into close races.",accent:"#ffc368",icon:"▽"},
  {id:"blade_storm",name:"Blade Storm",description:"Four rotating gates. Every hit changes the lead.",accent:"#ff8e99",icon:"✳"},
  {id:"narrows_chute",name:"Mint Narrows",description:"Tapered sidewalls lead to a clear final sprint.",accent:"#53e1b7",icon:"⋈"},
  {id:"split_cascade",name:"Split Cascade",description:"Alternating side channels and three spinning gates.",accent:"#51dfd3",icon:"⑂"},
  {id:"orbit_run",name:"Orbit Run",description:"Open chambers around three orbital spinners.",accent:"#b89aff",icon:"◎"},
];
const DROP_ARENA_SPINNERS = {
  classic_plinko: [[0.34,0.55],[0.63,0.55]],
  chevron_funnel: [[0.50,0.30]],
  blade_storm: [[0.20,0.50],[0.42,0.42],[0.64,0.50],[0.86,0.42]],
  narrows_chute: [[0.55,0.34]],
  split_cascade: [[0.30,0.34],[0.58,0.34],[0.82,0.30]],
  orbit_run: [[0.25,0.42],[0.50,0.48],[0.75,0.42]],
};
// Full staggered peg gates between rotor chambers close the direct side
// bypass. These change real geometry; gravity and clock stay untouched.
const DROP_ARENA_GATES = {
  classic_plinko:[], chevron_funnel:[.18,.76],
  blade_storm:[.08,.32,.54,.76], narrows_chute:[.20,.80],
  split_cascade:[.12,.44,.70], orbit_run:[.12,.37,.62,.88],
};
const DROP_GRAVITY = 1600;
const DROP_PEG_E = 0.88, DROP_RACER_E = 0.85, DROP_WALL_E = 0.8;

function dropPegKeep(kind, rowI, x, cx, trackW, colSpacing, progress){
  if (kind==="classic_plinko") return true;
  if (kind==="blade_storm") return rowI%2===0;
  if (kind==="chevron_funnel"){
    const bandPeriod=8, phase=(rowI%bandPeriod)/bandPeriod;
    const triangle=1-Math.abs(1-2*phase);
    return Math.abs(x-cx) > trackW*(0.06+0.40*triangle);
  }
  if (kind==="narrows_chute"){
    if (progress>0.85) return false;
    const wallDist = trackW*(0.46-0.26*Math.min(1,progress));
    return Math.abs(Math.abs(x-cx)-wallDist) < colSpacing*0.9;
  }
  if(kind==="split_cascade"){
    const phase=Math.floor(rowI/3)%2;
    return (rowI%2===0 && Math.abs(x-cx)<colSpacing*.42) ||
      (phase===0 ? x<cx-trackW*.26 : x>cx+trackW*.26);
  }
  if(kind==="orbit_run") return rowI%4===0 || (rowI%2===0 && Math.abs(x-cx)>trackW*.22);
  return true;
}
function dropGateRows(kind,rowYs,topY,finishY,trackW,racerRadius,pegRadius){
  const clearance=pegRadius*1.8+racerRadius*2.5+pegRadius*.35;
  const safe=rowYs.map(y=>DROP_ARENA_SPINNERS[kind].every(([fraction,length])=>
    Math.abs(y-(topY+(finishY-topY)*fraction))>trackW*length/2+clearance));
  const pairs=[];
  for(let i=0;i<rowYs.length-1;i++) if(safe[i]&&safe[i+1]) pairs.push(i);
  const gates=new Map();
  for(const fraction of DROP_ARENA_GATES[kind]){
    const choices=pairs.filter(i=>!gates.has(i)&&!gates.has(i+1));
    if(!choices.length) break;
    const target=topY+(finishY-topY)*fraction;
    const start=choices.reduce((best,i)=>Math.abs((rowYs[i]+rowYs[i+1])/2-target)<
      Math.abs((rowYs[best]+rowYs[best+1])/2-target)?i:best);
    gates.set(start,0);gates.set(start+1,1);
  }
  return gates;
}
function buildDropPegs(kind, rng, left, right, topY, finishY, h, racerRadius, pegRadius){
  const trackW = right-left, cx=(left+right)/2;
  const rowSpacing = racerRadius*5.5, edgeOffset=racerRadius*.35;
  // Edge pegs attach to the rail, so they deflect inward instead of
  // creating an undersized slot that can wedge a falling body.
  const columns=Math.ceil((trackW-2*edgeOffset)/(racerRadius*5))+1;
  const colSpacing=(trackW-2*edgeOffset)/(columns-1);
  const yStart = topY+h*0.24, yEnd = finishY-h*0.14;
  const pegs = [];
  const rowYs=Array.from({length:Math.max(0,Math.ceil((yEnd-yStart)/rowSpacing))},(_,i)=>yStart+i*rowSpacing);
  const gates=dropGateRows(kind,rowYs,topY,finishY,trackW,racerRadius,pegRadius);
  const baseX=left+edgeOffset;
  for(let rowI=0;rowI<rowYs.length;rowI++){
    const y=rowYs[rowI];
    const progress = yEnd<=yStart ? 0 : (y-yStart)/(yEnd-yStart);
    const sparse=kind==="blade_storm"||kind==="orbit_run";
    const phase=gates.has(rowI)?gates.get(rowI):(sparse?Math.floor(rowI/2):rowI)%2;
    let x = baseX+phase*colSpacing/2;
    while (x <= right-edgeOffset+1e-6){
      if (gates.has(rowI)||dropPegKeep(kind,rowI,x,cx,trackW,colSpacing,progress)){
        const peg={
          x: x+rng.range(-pegRadius*0.35,pegRadius*0.35),
          y: y+rng.range(-pegRadius*0.35,pegRadius*0.35),
          color: DROP_OBSTACLE_COLORS[pegs.length%DROP_OBSTACLE_COLORS.length],
        };
        const clearance=pegRadius*1.8+racerRadius*2.5;
        if(DROP_ARENA_SPINNERS[kind].every(([frac,len])=>Math.hypot(peg.x-cx,peg.y-(topY+(finishY-topY)*frac))>=trackW*len/2+clearance)) pegs.push(peg);
      }
      x += colSpacing;
    }
  }
  return pegs;
}
function buildDrop(seed, roster, arenaKind="classic_plinko"){
  if(!DROP_ARENA_SPINNERS[arenaKind]) arenaKind="classic_plinko";
  const rng = makeRng(seed);
  const n = roster.length;
  const stageW = 560;
  const left = stageW*0.06, right = stageW-stageW*0.06;
  const trackW = right-left;
  const racerRadius = trackW*0.042;
  const pegRadius = racerRadius*0.5;
  const h = 900;
  const topY = h*0.16;
  const trackH = h*3.4;
  const finishY = topY+trackH;

  const pegRng = makeRng((seed*40503+7)>>>0);
  const pegs = buildDropPegs(arenaKind, pegRng, left, right, topY, finishY, h, racerRadius, pegRadius);
  const blades = (DROP_ARENA_SPINNERS[arenaKind]||[]).map(([frac,lenFrac],bi)=>({
    x:(left+right)/2, y: topY+trackH*frac, len: trackW*lenFrac,
    angle:0, angularVel: (bi%2===0?1:-1)*pegRng.range(1.4,2.2),
    color: DROP_OBSTACLE_COLORS[bi%DROP_OBSTACLE_COLORS.length],
  }));

  const spacing = trackW/(n+1);
  const racers = roster.map((r,i)=>({
    ...r, idx:i,
    x: left+spacing*(i+1)+rng.range(-8,8), y: topY+rng.range(-6,6),
    vx:0, vy:0, angle: rng.range(-0.3,0.3), angularVel:0,
    finished:false, active:true, finishStep:null, obstacleContacts:new Set(),
  }));

  return {
    seed, arenaKind, left, right, trackW, racerRadius, pegRadius, topY, trackH, finishY,
    pegs, blades, racers, step:0, winner:null, finishedCount:0, finishOrder:[], finishTarget:1, complete:false, bumps:[],
    stageW, worldH: finishY + h*0.15, cameraY:0, viewportH:820, followYou:false,
  };
}
function stepDrop(drop, tSec){
  if(drop.complete) return;
  drop.step++;
  const {racers, pegs, blades, left, right, racerRadius, pegRadius, finishY} = drop;
  const active=racers.filter(r=>r.active), previousY=new Map(active.map(r=>[r,r.y]));
  for (const b of blades) b.angle += b.angularVel*DT;

  for (const rc of racers){
    if (!rc.active) continue;
    rc.vy += DROP_GRAVITY*DT;
    rc.vx *= Math.pow(0.999,DT); rc.vy *= Math.pow(0.999,DT);
    rc.x += rc.vx*DT; rc.y += rc.vy*DT;

    if (rc.x-racerRadius < left){ rc.x=left+racerRadius; rc.vx=Math.abs(rc.vx)*DROP_WALL_E; }
    if (rc.x+racerRadius > right){ rc.x=right-racerRadius; rc.vx=-Math.abs(rc.vx)*DROP_WALL_E; }

    for (const p of pegs){
      const dx=rc.x-p.x, dy=rc.y-p.y, d=Math.hypot(dx,dy);
      const minD = racerRadius+pegRadius;
      if (d<minD && d>0.0001){
        const nx=dx/d, ny=dy/d;
        rc.x += nx*(minD-d); rc.y += ny*(minD-d);
        const vn = rc.vx*nx+rc.vy*ny;
        if (vn<0){
          rc.vx -= (1+DROP_PEG_E)*vn*nx;
          rc.vy -= (1+DROP_PEG_E)*vn*ny;
          rc.angularVel += (-rc.vx*ny+rc.vy*nx)*0.01;
          if(Math.abs(vn)>40) rc.obstacleContacts.add(p);
          if (Math.abs(vn)>40 && drop.bumps.length<220)
            drop.bumps.push({x:rc.x,y:rc.y,born:tSec,intensity:Math.min(1,Math.abs(vn)/500)});
        }
      }
    }
    for (const b of blades){
      const hx=Math.cos(b.angle)*b.len/2, hy=Math.sin(b.angle)*b.len/2;
      const x1=b.x-hx,y1=b.y-hy,x2=b.x+hx,y2=b.y+hy;
      const wdx=x2-x1, wdy=y2-y1, len2=wdx*wdx+wdy*wdy||1;
      let t=((rc.x-x1)*wdx+(rc.y-y1)*wdy)/len2; t=Math.max(0,Math.min(1,t));
      const px=x1+t*wdx, py=y1+t*wdy;
      const dx=rc.x-px, dy=rc.y-py, d=Math.hypot(dx,dy);
      const minD = racerRadius+pegRadius*0.8;
      if (d<minD && d>0.0001){
        const nx=dx/d, ny=dy/d;
        rc.x += nx*(minD-d); rc.y += ny*(minD-d);
        // A kinematic blade transfers its contact-point velocity.
        const bladeVx=-b.angularVel*(py-b.y), bladeVy=b.angularVel*(px-b.x);
        const vn = Math.min(0, (rc.vx-bladeVx)*nx+(rc.vy-bladeVy)*ny);
        rc.vx -= (1+DROP_PEG_E)*vn*nx;
        rc.vy -= (1+DROP_PEG_E)*vn*ny;
        if(Math.abs(vn)>40) rc.obstacleContacts.add(b);
        rc.angularVel += 6;
        if (drop.bumps.length<220) drop.bumps.push({x:rc.x,y:rc.y,born:tSec,intensity:0.8});
      }
    }
  }
  for (let a=0;a<racers.length;a++) for (let b2=a+1;b2<racers.length;b2++){
    const ra=racers[a], rb=racers[b2];
    if (!ra.active||!rb.active) continue;
    const dx=rb.x-ra.x, dy=rb.y-ra.y, d=Math.hypot(dx,dy);
    const minD = racerRadius*2*0.92;
    if (d<minD && d>0.0001){
      const nx=dx/d, ny=dy/d, overlap=(minD-d)/2;
      ra.x-=nx*overlap; ra.y-=ny*overlap; rb.x+=nx*overlap; rb.y+=ny*overlap;
      const rvx=rb.vx-ra.vx, rvy=rb.vy-ra.vy, van=rvx*nx+rvy*ny;
      if (van<0){
        const jImp=-(1+DROP_RACER_E)*van/(1/ra.weight+1/rb.weight);
        const ix=jImp*nx, iy=jImp*ny;
        ra.vx-=ix/ra.weight; ra.vy-=iy/ra.weight;
        rb.vx+=ix/rb.weight; rb.vy+=iy/rb.weight;
      }
    }
  }
  for (const rc of racers){
    if(!rc.active) continue;
    rc.angle += rc.angularVel*DT; rc.angularVel *= 0.95;
  }
  recordFinishCrossings(drop,active,previousY,racerRadius,finishY);
  const activeR = racers.filter(r=>r.active);
  const pool = activeR.length ? activeR : racers;
  const selected=racers[drop.youIdx];
  const followed=(drop.complete&&drop.winner) || (drop.followYou&&selected?.active&&selected);
  const focusY=followed ? followed.y : pool.reduce((m,r)=>Math.max(m,r.y),drop.topY);
  recordTrails(drop);
  updateRaceCamera(drop,focusY,drop.worldH);
}
function drawDropBackground(ctx, drop){
  const {stageW, worldH, left, right, pegs, finishY, pegRadius} = drop;
  const arena=DROP_ARENAS.find(arena=>arena.id===drop.arenaKind)||DROP_ARENAS[0];
  const accent=arena.accent;
  const grad = ctx.createLinearGradient(0,0,0,worldH);
  grad.addColorStop(0,"#17263c"); grad.addColorStop(1,"#0a1322");
  ctx.fillStyle=grad; ctx.fillRect(0,0,stageW,worldH);
  // Floor bands and quiet measuring marks help the player read vertical speed.
  for(let y=0;y<worldH;y+=180){
    ctx.fillStyle="rgba(255,255,255,.025)";ctx.fillRect(left,y,right-left,90);
    ctx.strokeStyle="rgba(171,203,229,.24)";ctx.lineWidth=2;ctx.beginPath();
    ctx.moveTo(left+10,y);ctx.lineTo(left+20,y);ctx.moveTo(right-20,y);ctx.lineTo(right-10,y);ctx.stroke();
  }
  ctx.save();ctx.strokeStyle=accent;ctx.globalAlpha=.13;ctx.lineWidth=1.5;ctx.setLineDash([5,12]);
  for(let i=1;i<4;i++){const x=left+(right-left)*i/4;ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,worldH);ctx.stroke();}
  ctx.restore();
  for(const blade of drop.blades){
    const r=blade.len/2;
    ctx.save();ctx.translate(blade.x,blade.y);
    ctx.beginPath();ctx.arc(0,0,r+pegRadius*2.5,0,Math.PI*2);
    ctx.fillStyle=accent;ctx.globalAlpha=.04;ctx.fill();ctx.globalAlpha=.18;ctx.strokeStyle=accent;ctx.lineWidth=2;ctx.stroke();ctx.restore();
  }
  ctx.strokeStyle="#384d66";ctx.lineWidth=10;
  ctx.beginPath();ctx.moveTo(left,0);ctx.lineTo(left,worldH);ctx.moveTo(right,0);ctx.lineTo(right,worldH);ctx.stroke();
  ctx.strokeStyle=accent;ctx.lineWidth=3;ctx.stroke();
  for (const p of pegs){
    ctx.beginPath();ctx.arc(p.x,p.y+4,pegRadius+2,0,Math.PI*2);ctx.fillStyle="rgba(0,0,0,.35)";ctx.fill();
    ctx.beginPath(); ctx.arc(p.x,p.y,pegRadius,0,Math.PI*2);
    ctx.fillStyle="#354d68"; ctx.fill();
    ctx.strokeStyle=accent; ctx.lineWidth=2.5; ctx.stroke();
    ctx.beginPath();ctx.arc(p.x-pegRadius*.2,p.y-pegRadius*.2,pegRadius*.23,0,Math.PI*2);ctx.fillStyle="#e0f5ff";ctx.fill();
  }
  ctx.fillStyle=accent;ctx.font="600 11px system-ui,sans-serif";ctx.textAlign="center";
  ctx.fillText("DROP ZONE",stageW/2,drop.topY-45);
  for(const racer of drop.racers){
    ctx.beginPath();ctx.arc(racer.x,racer.y,drop.racerRadius*1.15,0,Math.PI*2);
    ctx.strokeStyle="rgba(213,238,255,.24)";ctx.lineWidth=1.5;ctx.stroke();
  }
  drawFinishLine(ctx,left,right,finishY,16,accent);
  ctx.fillStyle=accent; ctx.font="700 16px system-ui,sans-serif"; ctx.textAlign="center";
  ctx.fillText("FINISH", (left+right)/2, finishY+46);
}
function drawDrop(ctx, drop, offscreen, tSec, youIdx){
  const {stageW, viewportH, cameraY} = drop;
  ctx.clearRect(0,0,stageW,viewportH);
  ctx.drawImage(offscreen, 0, cameraY, stageW, viewportH, 0, 0, stageW, viewportH);
  ctx.save();
  ctx.translate(0,-cameraY);
  drawTrails(ctx,drop,drop.racerRadius,youIdx);
  const arena=DROP_ARENAS.find(arena=>arena.id===drop.arenaKind)||DROP_ARENAS[0];
  for (const b of drop.blades){
    const hx=Math.cos(b.angle)*b.len/2, hy=Math.sin(b.angle)*b.len/2;
    ctx.strokeStyle="#07101c"; ctx.lineWidth=drop.pegRadius*2.3; ctx.lineCap="round";
    ctx.beginPath(); ctx.moveTo(b.x-hx,b.y-hy); ctx.lineTo(b.x+hx,b.y+hy); ctx.stroke();
    ctx.strokeStyle=arena.accent;ctx.lineWidth=drop.pegRadius*1.6;ctx.stroke();
    ctx.strokeStyle="rgba(255,255,255,.7)";ctx.lineWidth=2;ctx.stroke();
    ctx.beginPath(); ctx.arc(b.x,b.y,drop.pegRadius*1.05,0,Math.PI*2); ctx.fillStyle="#e5f5ff"; ctx.fill();
    ctx.beginPath();ctx.arc(b.x,b.y,drop.pegRadius*.45,0,Math.PI*2);ctx.fillStyle="#24374f";ctx.fill();
  }
  for (const bmp of drop.bumps){
    const age=tSec-bmp.born; if (age>0.3) continue;
    ctx.beginPath(); ctx.fillStyle=`rgba(255,255,255,${(1-age/0.3)*0.5*bmp.intensity})`;
    ctx.arc(bmp.x,bmp.y,drop.racerRadius*(0.6+age*2),0,Math.PI*2); ctx.fill();
  }
  drop.bumps = drop.bumps.filter(b=>tSec-b.born<=0.3);
  const s = drop.racerRadius*2.3;
  for (const rc of drop.racers){
    ctx.save(); ctx.translate(rc.x-s/2, rc.y-s/2);
    ctx.shadowColor="rgba(0,0,0,0.28)"; ctx.shadowBlur=5; ctx.shadowOffsetY=2;
    drawRacerFace(ctx, s, rc.color, rc.angle, rc.idx===youIdx, rc.name);
    ctx.restore();
  }
  ctx.restore();
  drawSelectedRacerIndicator(ctx,drop,youIdx,stageW,viewportH,cameraY,drop.racerRadius);
}

/* =========================================================================
   App / UI wiring
   ========================================================================= */

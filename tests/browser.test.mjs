import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const {chromium}=await import(process.env.MARBLE_PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'.audit-work','ui-v2');
let server;
async function localTestServer(){
  const directories=['web','assets'].map(name=>path.join(root,name)+path.sep);
  const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.svg':'image/svg+xml','.jpg':'image/jpeg'};
  server=http.createServer(async(request,response)=>{
    try{
      if(!['GET','HEAD'].includes(request.method)){response.writeHead(405);response.end();return;}
      let pathname=decodeURIComponent(new URL(request.url,'http://localhost').pathname);
      if(pathname==='/')pathname='/index.html';
      const filename=path.resolve(root,'.'+pathname);
      if(filename!==path.join(root,'index.html')&&!directories.some(directory=>filename.startsWith(directory))){
        response.writeHead(404);response.end();return;
      }
      const data=await fs.readFile(filename);
      response.writeHead(200,{'Content-Type':mime[path.extname(filename)]||'application/octet-stream','Cache-Control':'no-store'});
      response.end(request.method==='HEAD'?undefined:data);
    }catch{response.writeHead(404);response.end();}
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  return 'http://127.0.0.1:'+server.address().port;
}
const url=process.env.MARBLE_TEST_URL || await localTestServer();
await fs.mkdir(output,{recursive:true});
let browser;
const errors=[], results=[];

async function read(page){
  return page.evaluate(()=>({screen:state.screen,phase:state.phase,paused:state.paused,step:state.sim?.step,
    remaining:state.countdownRemaining,raf:state.raf,races:state.races,wins:state.wins,sound:state.sound,
    youIdx:state.youIdx,fieldSize:state.fieldSize,mode:state.mode,arenaSize:state.arenaSize,
    mazeArena:state.mazeArena,dropArena:state.dropArena,seed:state.sim?.seed,
    roster:state.sim?.racers.map(r=>r.name),winner:state.sim?.winner?.name,format:state.format,speed:state.speed,
    cupRound:state.cup?.round,history:state.history.length,finishTarget:state.sim?.finishTarget}));
}
async function noOverflow(page,label){
  const dimensions=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
  assert.ok(dimensions.document<=dimensions.viewport+1&&dimensions.body<=dimensions.viewport+1,`${label}: horizontal overflow ${JSON.stringify(dimensions)}`);
}
async function capture(page,label){
  await noOverflow(page,label);
  const smallTargets=await page.evaluate(()=>{
    if(!matchMedia('(pointer:coarse)').matches)return [];
    return Array.from(document.querySelectorAll('button')).flatMap(button=>{
      const r=button.getBoundingClientRect();
      return r.width>0&&r.height>0&&(r.width<43.5||r.height<43.5)?[{id:button.id||button.getAttribute('aria-label')||button.textContent.trim(),width:r.width,height:r.height}]:[];
    });
  });
  assert.deepEqual(smallTargets,[],`${label}: touch controls should provide 44px targets`);
  await page.screenshot({path:path.join(output,label+'.png'),fullPage:true,animations:'disabled'});
}
async function finish(page){
  return page.evaluate(()=>{
    if(state.raf!==null)cancelAnimationFrame(state.raf);
    state.raf=null;state.paused=false;state.phase='racing';
    const sim=state.sim,limit=sim.kind==='drop'?120*60:120*90;
    while(!sim.complete&&sim.step<limit)SIM_KINDS[sim.kind].step(sim,sim.step*DT);
    if(!sim.complete)finishAtTimeLimit(sim);
    showWinner(sim);
    return {seed:sim.seed,winner:sim.winner?.name,step:sim.step,roster:sim.racers.map(r=>r.name),positions:sim.racers.map(r=>[r.x,r.y]),finishOrder:[...sim.finishOrder],races:state.races};
  });
}
async function unchangedWhilePaused(page){
  const before=await read(page);
  assert.equal(before.paused,true);assert.equal(before.raf,null);
  await page.waitForTimeout(130);
  const after=await read(page);
  assert.equal(after.step,before.step);assert.equal(after.remaining,before.remaining);
}
async function resultControls(page){
  assert.equal(await page.locator('#winner-overlay').getAttribute('role'),'region');
  assert.notEqual(await page.locator('#winner-overlay').getAttribute('aria-modal'),'true');
  for(const id of ['btn-again','btn-replay','btn-newracer','btn-share']){
    const button=page.locator('#'+id);
    await button.focus();await button.scrollIntoViewIfNeeded();
    assert.equal(await button.isVisible(),true);
    const bounds=await button.evaluate(el=>{
      const b=el.getBoundingClientRect(),s=document.querySelector('#race-stage').getBoundingClientRect();
      return {button:{left:b.left,right:b.right,top:b.top,bottom:b.bottom},stage:{left:s.left,right:s.right,top:s.top,bottom:s.bottom}};
    });
    const {button:b,stage:s}=bounds;
    assert.ok(b.left>=s.left-1&&b.right<=s.right+1&&b.top>=s.top-1&&b.bottom<=s.bottom+1,`${id} must be reachable inside the race stage: ${JSON.stringify(bounds)}`);
  }
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>!document.querySelector('#winner-overlay').contains(document.activeElement)),true,'nonmodal results allow keyboard navigation to track controls');
  await page.locator('#btn-again').focus();
}

try{
  browser=await chromium.launch({headless:true,...(process.env.MARBLE_BROWSER_PATH?{executablePath:process.env.MARBLE_BROWSER_PATH}:{})});
  if(server){
    for(const route of ['/race_sim.py','/web/%2e%2e/race_sim.py','/assets/%2e%2e/race_sim.py']){
      const response=await fetch(url+route);
      assert.equal(response.status,404,'the test server must not expose files outside its public routes');
    }
  }
  for(const viewport of [{width:1440,height:1000},{width:390,height:844},{width:360,height:640},{width:844,height:390}].filter(v=>!process.env.MARBLE_TEST_VIEWPORT||`${v.width}x${v.height}`===process.env.MARBLE_TEST_VIEWPORT)){
    const label=`${viewport.width}x${viewport.height}`;
    const context=await browser.newContext({viewport,deviceScaleFactor:1,reducedMotion:'reduce',hasTouch:viewport.width!==1440});
    const page=await context.newPage();
    await page.addInitScript(()=>{
      const original=crypto.getRandomValues.bind(crypto),seeds=[137,41,7,314];
      let index=0;
      Object.defineProperty(crypto,'getRandomValues',{configurable:true,value(array){
        if(array instanceof Uint32Array&&array.length===1){array[0]=seeds[index++%seeds.length];return array;}
        return original(array);
      }});
    });
    page.on('pageerror',error=>errors.push({viewport:label,message:error.message}));
    page.setDefaultTimeout(8000);
    try{
      await page.goto(url,{waitUntil:'networkidle'});
      await page.waitForFunction(()=>typeof state!=='undefined'&&document.querySelectorAll('.racer-card').length===16);
      await capture(page,label+'-menu');
      await page.locator('#btn-quick').click();
      assert.equal((await read(page)).screen,'race','Quick race opens the track directly');
      assert.equal((await read(page)).phase,'countdown');
      await page.locator('#screen-race [data-nav="mode"]').click();
      await page.locator('.brand').click();

      await page.locator('#btn-sound').focus();await page.keyboard.press('Enter');
      assert.equal((await read(page)).sound,true);
      assert.equal(await page.locator('#btn-sound').getAttribute('aria-pressed'),'true');
      await page.locator('#btn-help').focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('#help-dialog').evaluate(el=>el.open),true);
      assert.equal(await page.evaluate(()=>document.querySelector('#help-dialog').contains(document.activeElement)),true);
      for(let i=0;i<8;i++){
        await page.keyboard.press('Tab');
        const focus=await page.evaluate(()=>({inside:document.querySelector('#help-dialog').contains(document.activeElement),tag:document.activeElement.tagName,id:document.activeElement.id}));
        // Native modal dialogs may cycle through browser chrome, represented
        // by BODY; background page controls must remain inert.
        assert.ok(focus.inside||focus.tag==='BODY','modal help must not focus background controls: '+JSON.stringify(focus));
      }
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#help-dialog').evaluate(el=>el.open),false);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'btn-help','closing help restores its trigger');
      await page.locator('#btn-play').click();
      assert.equal((await read(page)).screen,'mode');
      assert.equal(await page.locator('.racer-card').count(),16);
      assert.equal(await page.locator('#arena-choices-race .arena-card').count(),4);
      assert.equal(await page.locator('#arena-choices-drop .arena-card').count(),6);
      const catalog=await page.evaluate(()=>RACER_IDENTITIES);
      assert.equal(Object.keys(catalog).length,16,'all original racers have a character identity');
      assert.equal(new Set(Object.values(catalog).map(identity=>identity.kind)).size,16,'every racer has its own object identity');
      await page.waitForFunction(()=>Array.from(document.querySelectorAll('.racer-card img')).every(img=>img.complete&&img.naturalWidth>0));
      for(let i=0;i<16;i++){
        const card=page.locator(`[data-racer="${i}"].racer-card`);
        await card.click();
        assert.equal((await read(page)).youIdx,i);
        const name=await card.locator('.racer-name').textContent(),identity=catalog[name];
        assert.ok(identity&&identity.description.length>10,`${name} needs a meaningful identity`);
        assert.equal(await card.locator('.racer-kind').textContent(),identity.label);
        assert.ok((await card.getAttribute('aria-label')).includes(identity.label));
        assert.equal(await page.locator('#selected-kind').textContent(),identity.label);
        assert.equal(await page.locator('#selected-description').textContent(),identity.description);
        await page.waitForFunction(()=>document.querySelector('#selected-portrait').complete&&document.querySelector('#selected-portrait').naturalWidth>0);
        assert.equal(await card.locator('.racer-kind').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true,`${name}'s identity label must fit its card`);
      }
      await page.locator('[data-racer="6"].racer-card').click();
      for(const id of ['classic','open_rooms','switchback','crossroads']){
        await page.locator(`#arena-choices-race [data-arena="${id}"]`).click();
        assert.equal((await read(page)).mazeArena,id);
      }
      for(const size of ['s','m','l']){
        await page.locator(`[data-size="${size}"]`).click();
        assert.equal((await read(page)).arenaSize,size);
      }
      while(!(await page.locator('#field-minus').isDisabled()))await page.locator('#field-minus').click();
      assert.equal((await read(page)).fieldSize,2);
      while(!(await page.locator('#field-plus').isDisabled()))await page.locator('#field-plus').click();
      assert.equal((await read(page)).fieldSize,8);
      for(let i=0;i<4;i++)await page.locator('#field-minus').click();
      await capture(page,label+'-setup-maze');
      await page.locator('[data-mode="drop"]').click();
      assert.equal(await page.locator('#arena-box-race').isVisible(),false);
      for(const id of ['classic_plinko','chevron_funnel','blade_storm','narrows_chute','split_cascade','orbit_run']){
        await page.locator(`#arena-choices-drop [data-arena="${id}"]`).click();
        assert.equal((await read(page)).dropArena,id);
      }
      await capture(page,label+'-setup-drop');
      await page.locator('[data-mode="race"]').click();
      await page.locator('#btn-mode-next').click();
      const firstStart=await read(page);
      assert.equal(firstStart.phase,'countdown');assert.equal(firstStart.races,0);
      await page.keyboard.press('Escape');
      await unchangedWhilePaused(page);
      assert.equal(await page.locator('#pause-overlay').isVisible(),true);
      await page.keyboard.press('Enter');
      await page.waitForFunction(()=>state.phase==='racing'&&state.sim.step>2);
      assert.equal(await page.locator('#countdown').isVisible(),false);
      await page.locator('#main').focus();await page.keyboard.press('Space');
      await unchangedWhilePaused(page);
      await page.locator('#camera-you').click();
      assert.equal(await page.locator('#camera-you').getAttribute('aria-pressed'),'true');
      assert.equal(await page.evaluate(()=>state.sim.followYou),true);
      for(const speed of ['.5','2','1']){
        await page.locator(`[data-speed="${speed}"]`).click();
        assert.equal((await read(page)).speed,Number(speed));
        assert.equal(await page.locator(`[data-speed="${speed}"]`).getAttribute('aria-pressed'),'true');
        await unchangedWhilePaused(page);
      }
      assert.equal(await page.locator('#your-progress').isVisible(),true);
      assert.match(await page.locator('#your-progress-label').textContent(),/Sky/);
      assert.ok((await page.locator('#race-event').textContent()).length>0);
      await capture(page,label+'-paused');
      await page.locator('#btn-resume').click();
      await page.waitForFunction(()=>state.sim.step>30);
      await capture(page,label+'-race');
      await page.locator('#btn-restart').click();
      const restarted=await read(page);
      assert.equal(restarted.seed,firstStart.seed);assert.deepEqual(restarted.roster,firstStart.roster);
      assert.equal(restarted.races,0);
      const result=await finish(page);
      assert.equal(result.races,1,'unfinished restart still counts its eventual first finish');
      assert.equal(await page.locator('#winner-overlay').isVisible(),true);
      assert.ok((await page.locator('#winner-name').textContent()).includes(result.winner));
      assert.equal(await page.locator('#winner-identity').textContent(),catalog[result.winner].label);
      assert.equal(await page.locator('.standing-identity').count(),4);
      assert.equal(await page.locator('#btn-pause').isDisabled(),true);
      assert.equal(await page.locator('#standings-status').textContent(),'FINAL');
      await resultControls(page);
      await capture(page,label+'-result');
      await page.evaluate(()=>showWinner(state.sim));
      assert.equal((await read(page)).races,1,'the same finish is counted once');
      await page.locator('#btn-replay').click();
      const replay=await finish(page);
      assert.deepEqual({...replay,races:0},{...result,races:0},'replay keeps seed, roster, winner, duration and final positions');
      assert.equal(replay.races,1,'replay does not add a duplicate result');

      await page.locator('#btn-again').click();
      await page.waitForFunction(()=>state.phase==='racing'&&state.sim.step>2);
      await page.locator('#btn-help').click();
      await unchangedWhilePaused(page);
      assert.equal(await page.locator('#help-dialog').evaluate(el=>el.open),true);
      await page.locator('#btn-help-play').click();
      assert.equal((await read(page)).paused,false);
      await page.locator('#screen-race [data-nav="mode"]').click();
      const stopped=await read(page);
      assert.equal(stopped.screen,'mode');assert.equal(stopped.raf,null);assert.equal(stopped.phase,'idle');
      await page.waitForTimeout(130);
      assert.equal((await read(page)).step,stopped.step,'back cancels the live animation loop');
      assert.equal((await read(page)).races,1,'abandoning an unfinished race does not count');

      await page.locator('[data-mode="drop"]').click();
      await page.locator('#btn-mode-next').click();
      await page.evaluate(()=>{
        if(state.raf!==null)cancelAnimationFrame(state.raf);state.raf=null;
        state.phase='racing';document.querySelector('#countdown').hidden=true;
        document.querySelector('#race-status').textContent='And they’re off. First across wins.';
        for(let i=0;i<100&&!state.sim.winner;i++)stepDrop(state.sim,state.sim.step*DT);
        updateStandings(true);drawCurrent();
      });
      await capture(page,label+'-drop');
      const dropResult=await finish(page);
      assert.equal(dropResult.races,2);
      await resultControls(page);
      // The fallback is usable without granting clipboard permission to tests.
      await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('Clipboard unavailable in this test');}}}));
      await page.locator('#btn-share').click();
      assert.equal(await page.locator('#share-link').isVisible(),true);
      assert.match(await page.locator('#share-status').textContent(),/Copy this link/);
      const sharedUrl=await page.locator('#share-link').inputValue();
      await page.locator('#share-link').scrollIntoViewIfNeeded();
      const linkBounds=await page.locator('#share-link').evaluate(el=>{
        const r=el.getBoundingClientRect(),s=document.querySelector('#race-stage').getBoundingClientRect();
        return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,stage:{left:s.left,right:s.right,top:s.top,bottom:s.bottom}};
      });
      assert.ok(linkBounds.left>=linkBounds.stage.left-1&&linkBounds.right<=linkBounds.stage.right+1&&linkBounds.top>=linkBounds.stage.top-1&&linkBounds.bottom<=linkBounds.stage.bottom+1,'share fallback remains reachable inside the result stage: '+JSON.stringify(linkBounds));
      await capture(page,label+'-share');
      await page.locator('#btn-replay').click();
      assert.deepEqual(await finish(page),dropResult,'drop replay is deterministic and counted once');
      await page.locator('#btn-newracer').click();
      await page.reload({waitUntil:'networkidle'});
      const restored=await read(page);
      assert.equal(restored.races,2);assert.equal(restored.sound,true);assert.equal(restored.youIdx,6);
      assert.equal(restored.fieldSize,4);assert.equal(restored.mode,'drop');assert.equal(restored.arenaSize,'l');
      assert.equal(restored.mazeArena,'crossroads');assert.equal(restored.dropArena,'orbit_run');
      assert.match(await page.locator('#session-label').textContent(),/^2 races/);
      await noOverflow(page,label+'-restored');
      assert.equal(await page.locator('#recent-list .history-race').count(),2);
      await page.locator('#btn-quick').click();
      const quick=await read(page);
      assert.equal(quick.mode,'drop');assert.equal(quick.fieldSize,4);assert.equal(quick.dropArena,'orbit_run');
      await page.locator('#screen-race [data-nav="mode"]').click();

      // A full eight-racer Cup checks real podium scoring, rotating grids,
      // replay idempotence, and narrow-screen score-strip wrapping.
      await page.locator('[data-format="cup"]').click();
      assert.equal((await read(page)).format,'cup');
      while(!(await page.locator('#field-plus').isDisabled()))await page.locator('#field-plus').click();
      await page.locator('#btn-mode-next').click();
      assert.equal(await page.locator('#cup-strip').isVisible(),true);
      assert.equal(await page.locator('#cup-scores .cup-score').count(),8);
      const cupRounds=await page.evaluate(()=>state.cup.rounds.map(round=>({...round})));
      assert.equal(new Set(cupRounds.map(round=>round.arena)).size,3);
      for(let round=0;round<3;round++){
        assert.equal((await read(page)).cupRound,round);
        assert.equal((await read(page)).finishTarget,3);
        const heat=await finish(page);
        assert.equal(heat.finishOrder.length,3,'Cup podium places require three real finishes');
        const finishTiming=await page.evaluate(()=>({winnerSeconds:state.sim.winner.finishStep*DT,stopSeconds:state.sim.step*DT,
          stored:state.history.find(entry=>entry.race===GameSession.encode(state.sim.runConfig))?.seconds}));
        assert.equal(await page.locator('#result-time').textContent(),'Round win: '+finishTiming.winnerSeconds.toFixed(2)+' seconds','result time belongs to the winner, not the third-place finish');
        assert.equal(finishTiming.stored,finishTiming.winnerSeconds,'history records the same actual winning time');
        assert.ok(finishTiming.winnerSeconds<=finishTiming.stopSeconds);
        const scoring=await page.evaluate(()=>({awards:state.cup.results[state.cup.round],scores:[...state.cup.scores],roster:state.lastRun.roster}));
        assert.deepEqual(scoring.awards,heat.finishOrder.map((index,place)=>({racer:scoring.roster[index],points:[5,3,1][place]})));
        assert.equal(scoring.scores.reduce((sum,n)=>sum+n,0),9*(round+1));
        assert.equal(await page.locator('#standings-status').textContent(),'FINAL');
        assert.equal(await page.locator('#result-score').isVisible(),true);
        await resultControls(page);
        await capture(page,label+'-cup-'+(round+1));
        await page.locator('[data-speed=".5"]').click();
        await page.locator('#btn-replay').click();
        await page.locator('[data-speed="2"]').click();
        assert.deepEqual(await finish(page),heat,'playback speed does not change deterministic heat results');
        assert.deepEqual(await page.evaluate(()=>state.cup.scores),scoring.scores,'replaying a Cup heat awards no duplicate points');
        if(round<2){assert.match(await page.locator('#btn-again').textContent(),/Next round/);await page.locator('#btn-again').click();}
      }
      assert.match(await page.locator('#btn-again').textContent(),/New Cup/);
      assert.equal(await page.locator('#result-eyebrow').textContent(),'CUP COMPLETE');
      assert.equal((await read(page)).races,5);
      const tiePortraits=await page.evaluate(()=>{
        const sim=state.sim,cup=state.cup,oldScores=[...cup.scores],oldPick=sim.runConfig.youIdx,oldYou=sim.youIdx;
        const champions=sim.runConfig.roster.filter(i=>RACER_POOL[i].name!==sim.winner.name).slice(0,2);
        cup.scores.fill(0);champions.forEach(i=>cup.scores[i]=8);
        sim.runConfig.youIdx=champions[0];sim.youIdx=sim.runConfig.roster.indexOf(champions[0]);
        const portraits=[],original=drawRacerFace;
        drawRacerFace=(ctx,size,color,angle,isYou,name)=>{
          if(ctx.canvas.id==='winner-swatch')portraits.push({name,isYou});
          return original(ctx,size,color,angle,isYou,name);
        };
        try{showWinner(sim);}finally{drawRacerFace=original;}
        const result={portraits,expected:GameSession.cupLeaders(cup).map(i=>({name:RACER_POOL[i].name,isYou:i===champions[0]})),title:document.querySelector('#winner-name').textContent};
        cup.scores=oldScores;sim.runConfig.youIdx=oldPick;sim.youIdx=oldYou;showWinner(sim);
        return result;
      });
      assert.equal(tiePortraits.title,'Shared Cup victory');
      assert.deepEqual(tiePortraits.portraits,tiePortraits.expected,'tied champions each receive their own portrait and only the selected champion is marked');
      await page.locator('#btn-share').click();
      const cupShare=await page.locator('#share-link').inputValue();
      assert.equal(await page.evaluate(link=>GameSession.decode(new URL(link).searchParams.get('race')).finishTarget,cupShare),3,'shared Cup heat preserves the podium finish target');
      const cupHeat=await finish(page);
      const sharedPage=await context.newPage();
      sharedPage.on('pageerror',error=>errors.push({viewport:label,message:error.message}));
      await sharedPage.goto(cupShare,{waitUntil:'networkidle'});
      assert.equal((await read(sharedPage)).finishTarget,3);
      assert.deepEqual(await finish(sharedPage),cupHeat,'shared heat reconstructs its complete podium and is counted once');
      await sharedPage.goto(sharedUrl,{waitUntil:'networkidle'});
      assert.equal((await read(sharedPage)).finishTarget,1);
      assert.deepEqual({...await finish(sharedPage),races:2},dropResult,'single-race links reconstruct the same exact finish');
      await sharedPage.goto(url+'?race=2~drop~orbit_run~m~not-a-seed',{waitUntil:'networkidle'});
      assert.equal((await read(sharedPage)).screen,'menu','malformed race links do not launch a simulation');
      assert.equal(await sharedPage.locator('#link-notice').isVisible(),true,'invalid race links show a visible explanation');
      assert.match(await sharedPage.locator('#link-notice').textContent(),/invalid|older|version/i);
      await sharedPage.close();

      // A real timeout must not manufacture a winner or increment statistics.
      await page.locator('#btn-newracer').click();
      await page.locator('[data-format="single"]').click();
      await page.locator('#btn-mode-next').click();
      const speedSteps=await page.evaluate(()=>[.5,1,2].map(speed=>{
        startSim(true);cancelAnimationFrame(state.raf);state.raf=null;
        state.phase='racing';state.lastTime=1000;state.accumulator=0;setSpeed(speed);
        loop(1050);if(state.raf!==null)cancelAnimationFrame(state.raf);state.raf=null;
        return state.sim.step;
      }));
      assert.ok(speedSteps[0]<speedSteps[1]&&speedSteps[1]<speedSteps[2],'playback speed scales simulation steps for the same wall-clock frame');
      await page.evaluate(()=>startSim(true));
      const beforeTimeout=await read(page);
      await page.evaluate(()=>{if(state.raf!==null)cancelAnimationFrame(state.raf);state.raf=null;state.sim.step=120*60;finishAtTimeLimit(state.sim);showWinner(state.sim);});
      const afterTimeout=await read(page);
      assert.equal(afterTimeout.winner,undefined);assert.equal(afterTimeout.races,beforeTimeout.races);assert.equal(afterTimeout.wins,beforeTimeout.wins);
      assert.match(await page.locator('#winner-sub').textContent(),/No win recorded/);
      assert.equal(await page.locator('#result-eyebrow').textContent(),'TIME’S UP');
      await page.locator('.brand').click();
      assert.equal(await page.locator('#recent-list .history-race').count(),5);
      await capture(page,label+'-history');
      await page.reload({waitUntil:'networkidle'});
      assert.equal((await read(page)).races,5);assert.equal((await read(page)).speed,2);
      assert.equal(await page.locator('#recent-list .history-race').count(),5);
      if(viewport.width===1440){
        const camera=await page.evaluate(()=>{
          state.mode='drop';state.format='cup';state.fieldSize=8;startSelected();
          cancelAnimationFrame(state.raf);state.raf=null;
          const sim=state.sim;
          while(sim.finishedCount===0&&sim.step<120*60)stepDrop(sim,sim.step*DT);
          if(sim.finishedCount===0)throw new Error('Camera regression seed needs a real finisher');
          sim.youIdx=sim.finishOrder[0];sim.followYou=true;
          // Separate the finished pick from the chase to expose an incorrect
          // fallback even when racers would naturally share the finish camera.
          sim.racers.filter(r=>r.active).forEach((r,i)=>{r.y=sim.viewportH*.6+i*10;});
          const leader=sim.racers.filter(r=>r.active).sort((a,b)=>progress(sim,a)-progress(sim,b))[0];
          frameCamera();
          return {complete:sim.complete,actual:sim.cameraY,expected:Math.max(0,Math.min(sim.worldH-sim.viewportH,leader.y-sim.viewportH*.42))};
        });
        assert.equal(camera.complete,false,'the podium race continues after the first finish');
        assert.equal(camera.actual,camera.expected,'a finished selected racer yields the camera to the active podium chase');
        await page.locator('.brand').click();
        const originalStorage=await page.evaluate(()=>localStorage.getItem(STORAGE_KEY));
        for(const [races,wins,expected] of [[Number.MAX_SAFE_INTEGER+1,3,[0,0]],[5,19,[5,5]],[-1,-2,[0,0]]]){
          await page.evaluate(values=>localStorage.setItem('marble-race-v2',JSON.stringify(values)),{races,wins});
          await page.reload({waitUntil:'networkidle'});
          const restoredStats=await read(page);
          assert.deepEqual([restoredStats.races,restoredStats.wins],expected,'persisted stats are safe integers with wins bounded by races');
        }
        await page.evaluate(value=>localStorage.setItem('marble-race-v2',value),originalStorage);
        await page.reload({waitUntil:'networkidle'});
      }
      results.push({viewport:label,status:'passed',mazeWinner:result.winner,dropWinner:dropResult.winner,stats:5});
      console.log(`PASS ${label}: quick start, identities, live controls, Cup podium, replay/share, history, timeout, persistence`);
    }catch(error){
      await page.screenshot({path:path.join(output,label+'-failure.png'),fullPage:true}).catch(()=>{});
      results.push({viewport:label,status:'failed',message:error.message});
      throw error;
    }finally{await context.close();}
  }
  assert.deepEqual(errors,[],'browser must not throw page errors');
}finally{
  await fs.writeFile(path.join(output,'browser-results.json'),JSON.stringify({url,results,errors},null,2)+'\n');
  await browser?.close();
  if(server)await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
}

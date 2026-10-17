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
    roster:state.sim?.racers.map(r=>r.name),winner:state.sim?.winner?.name}));
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
    while(!sim.winner&&sim.step<limit)SIM_KINDS[sim.kind].step(sim,sim.step*DT);
    if(!sim.winner)throw new Error(`Seed ${sim.seed} / ${sim.arenaKind} did not finish`);
    showWinner(sim);
    return {seed:sim.seed,winner:sim.winner.name,step:sim.step,roster:sim.racers.map(r=>r.name),positions:sim.racers.map(r=>[r.x,r.y]),races:state.races};
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
  for(const id of ['btn-again','btn-replay','btn-newracer']){
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
  assert.equal(await page.evaluate(()=>document.activeElement.id),'camera-leader','nonmodal results allow keyboard navigation to track controls');
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
  for(const viewport of [{width:1440,height:1000},{width:390,height:844},{width:360,height:640},{width:844,height:390}]){
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
      results.push({viewport:label,status:'passed',mazeWinner:result.winner,dropWinner:dropResult.winner,stats:restored.races});
      console.log(`PASS ${label}: setup, keyboard, live/pause, results, replay, stats, persistence`);
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

/* Read-only browser validation of the self-reading report, using Node built-ins. */
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const root=process.cwd();
const work=path.join(root,'.work/self-reading-check');
const previews=path.join(root,'paper/generated/report-previews');
fs.mkdirSync(work,{recursive:true});fs.mkdirSync(previews,{recursive:true});
const htmlPath=path.join(root,'paper/supervisor-briefing.html');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'paper/generated/briefing-manifest.json'),'utf8'));
const copy=path.join(work,'report.html');fs.copyFileSync(htmlPath,copy);
const digest=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const report={html_sha256:digest(htmlPath),manifest_sha256:digest(path.join(root,'paper/generated/briefing-manifest.json')),
  checker_sha256:digest(__filename),checks:{},views:[],externalRequests:[],exceptions:[],screenshot_sha256:{}};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const profile=path.join(work,'profile-'+Date.now());
const browser=spawn(process.env.BRIEFING_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--user-data-dir='+profile,'--remote-debugging-port=0','about:blank'],
  {windowsHide:true,stdio:'ignore'});
let socket;let sequence=0;const pending=new Map();
function assert(value,message){if(!value)throw new Error(message);}
function send(method,params={}){return new Promise((resolve,reject)=>{
  const id=++sequence;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout '+method));},8000);
  pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));
});}
async function evaluate(expression){const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
async function waitFor(expression){for(let i=0;i<100;i++){if(await evaluate(expression))return;await delay(50);}throw new Error('Condition not met: '+expression);}
async function inspect(selector,width,height,label){
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`);
  await evaluate('document.fonts.ready.then(()=>true)');await delay(100);
  const view=await evaluate(`(()=>{
    const e=document.querySelector(${JSON.stringify(selector)});const outside=[],overlaps=[];let minFont=Infinity;
    for(const svg of e.querySelectorAll('svg')){
      const v=svg.viewBox.baseVal,m=svg.getScreenCTM(),boxes=[];
      for(const t of svg.querySelectorAll('text')){
        const raw=t.getBBox(),relative=svg.getCTM().inverse().multiply(t.getCTM());
        const corners=[[raw.x,raw.y],[raw.x+raw.width,raw.y],[raw.x,raw.y+raw.height],[raw.x+raw.width,raw.y+raw.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(relative));
        const b={x:Math.min(...corners.map(p=>p.x)),y:Math.min(...corners.map(p=>p.y))};
        b.width=Math.max(...corners.map(p=>p.x))-b.x;b.height=Math.max(...corners.map(p=>p.y))-b.y;
        const tm=t.getScreenCTM();minFont=Math.min(minFont,parseFloat(getComputedStyle(t).fontSize)*Math.hypot(tm.a,tm.b));
        if(b.x<v.x-1||b.y<v.y-1||b.x+b.width>v.x+v.width+1||b.y+b.height>v.y+v.height+1)outside.push(t.textContent);
        boxes.push({text:t.textContent,x:b.x,y:b.y,w:b.width,h:b.height});
      }
      for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
        const a=boxes[i],b=boxes[j];
        if(Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)>2&&Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y)>2)overlaps.push([a.text,b.text]);
      }
    }
    return{selector:${JSON.stringify(selector)},width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,
      top:e.getBoundingClientRect().top,visible:getComputedStyle(e).display!=='none',minimumSvgFontPx:Number.isFinite(minFont)?minFont:null,
      svgTextOutside:outside,svgTextOverlaps:overlaps,clippedReadingText:[...e.querySelectorAll('.reading-notes,.exhibit-intro,.table-guide,.symbol-guide')].filter(x=>x.getBoundingClientRect().width>0&&x.scrollWidth>x.clientWidth+1).map(x=>x.className)};
  })()`);
  report.views.push(view);
  const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  const file=path.join(previews,`${width}x${height}-${label}.png`);fs.writeFileSync(file,Buffer.from(screenshot.data,'base64'));
  report.screenshot_sha256[path.relative(root,file).replaceAll('\\','/')]=digest(file);
  assert(view.documentWidth<=width,'Page has horizontal overflow');assert(view.visible,'Section hidden');assert(!view.clippedReadingText.length,'Reading guide text clipped: '+JSON.stringify(view.clippedReadingText));
  assert(view.svgTextOutside.length===0,'Clipped SVG text: '+JSON.stringify(view.svgTextOutside));
  assert(view.svgTextOverlaps.length===0,'Overlapping SVG text: '+JSON.stringify(view.svgTextOverlaps));
  return view;
}
(async()=>{try{
  const portFile=path.join(profile,'DevToolsActivePort');
  for(let i=0;i<100&&!fs.existsSync(portFile);i++){assert(browser.exitCode===null,'Chrome exited');await delay(100);}
  assert(fs.existsSync(portFile),'No Chrome debugger');
  const port=fs.readFileSync(portFile,'utf8').split('\n')[0].trim();
  const tabs=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  socket.addEventListener('message',event=>{const packet=JSON.parse(event.data);
    if(packet.id){const r=pending.get(packet.id);if(!r)return;clearTimeout(r.timer);pending.delete(packet.id);packet.error?r.reject(new Error(JSON.stringify(packet.error))):r.resolve(packet.result);}
    else if(packet.method==='Runtime.exceptionThrown')report.exceptions.push(packet.params);
    else if(packet.method==='Network.requestWillBeSent'&&/^https?:/.test(packet.params.request.url))report.externalRequests.push(packet.params.request.url);
  });
  report.browser=await send('Browser.getVersion');await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
  await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await send('Emulation.setDeviceMetricsOverride',{width:1366,height:768,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:pathToFileURL(copy).href});await waitFor(`document.readyState==='complete'&&document.querySelectorAll('[data-report-section]').length===7`);
  report.checks.noScriptsOrPresenterControls=await evaluate(`document.querySelectorAll('script,.stage-controls,.toolbar,.slide,dialog,[data-stage-from]').length===0`);
  report.checks.appendixOptional=await evaluate(`!document.querySelector('.case-appendix').open`);
  report.checks.allCoreContentVisible=await evaluate(`[...document.querySelectorAll('[data-report-section]')].every(e=>getComputedStyle(e).display!=='none'&&getComputedStyle(e).opacity==='1')`);
  report.checks.allMainFiguresVisible=await evaluate(`[...document.querySelectorAll('figure')].filter(e=>!e.closest('details')).length===${manifest.main_figure_ids.length}&&[...document.querySelectorAll('figure')].filter(e=>!e.closest('details')).every(e=>e.getBoundingClientRect().height>0)`);
  report.checks.contentsResolve=await evaluate(`[...document.querySelectorAll('.contents a')].every(a=>document.querySelector(a.getAttribute('href')))`);
  report.checks.numberedSevenChapterNavigation=await evaluate(`(()=>{const links=[...document.querySelectorAll('.contents a')];return links.length===7&&links.every((a,i)=>a.textContent.startsWith(i+'. '))})()`);
  report.checks.methodResultSeparation=await evaluate(`(()=>{const method={'model':'model','pid-visual-sample':'hotspots','visual-interface':'hotspots','supplement-unet':'hotspots','inspection-architecture':'fifo','supplement-crossed-design':'fifo'};const results=['supplement-estimator-training','supplement-ppo-training','supplement-estimation','supplement-heatmaps','supplement-process','supplement-methods','supplement-professions','supplement-contrasts','supplement-latency','supplement-scale'];return Object.entries(method).every(([name,section])=>document.querySelector('#figure-'+name).closest('section').id===section)&&results.every(name=>document.querySelector('#figure-'+name).closest('section').id==='comparison')})()`);
  report.checks.historicalPlotsInAppendix=await evaluate(`['estimated-temperature','offline-temperature','confirmations','outcome-costs'].every(name=>document.querySelector('#figure-'+name).closest('section').id==='appendix'&&!!document.querySelector('#figure-'+name).closest('details'))`);
  report.checks.noMixedHistoricalDenominatorInMethods=await evaluate(`['overview','model','hotspots','fifo'].every(name=>!document.querySelector('#'+name).textContent.includes('/89'))`);
  report.checks.noAnimations=await evaluate(`document.getAnimations().length===0&&[...document.querySelectorAll('*')].every(e=>getComputedStyle(e).animationName==='none'&&getComputedStyle(e).transitionDuration==='0s')`);
  report.checks.actualFifoQueue=await evaluate(`(()=>{const t=document.querySelector('[data-table="fifo-queue"]').textContent;return t.includes('450秒')&&t.includes('455秒')&&t.includes('0.0081')&&t.includes('0.0656')&&t.indexOf('机柜10')<t.indexOf('机柜8')})()`);
  report.checks.returnBudget=await evaluate(`(()=>{const t=document.querySelector('[data-table="return-budget"]').textContent;return ['525秒','540秒','545秒','20秒','5秒'].every(v=>t.includes(v))})()`);
  report.checks.completeHeatmaps=await evaluate(`['risk','temperature','estimated-temperature'].every(kind=>document.querySelectorAll('[data-kind="'+kind+'"][data-rack]').length===128)`);
  report.checks.originalRiskOverlay=await evaluate(`JSON.stringify([...document.querySelectorAll('[data-risk-positive]')].map(e=>Number(e.dataset.rack)))===JSON.stringify([64,67,70])`);
  report.checks.embeddedPidImages=await evaluate(`(()=>{const images=[...document.querySelectorAll('#figure-pid-visual-sample image')];return images.length===3&&images.every(e=>e.getAttribute('href').startsWith('data:image/png;base64,')&&e.getBoundingClientRect().height>100)})()`);
  report.checks.primaryOutcomeValues=await evaluate(`JSON.stringify([...document.querySelectorAll('[data-method]')].map(e=>[e.dataset.method,Number(e.dataset.count)]))===JSON.stringify([['tour',28],['fifo',70],['shuffled',25]])`);
  report.checks.allRegisteredRulesShown=await evaluate(`JSON.stringify([...document.querySelectorAll('[data-rule-sha]')].map(e=>Number(e.dataset.confirmed)))===JSON.stringify([28,33,59,43,30,60,47,60,49])`);
  report.checks.costThresholdsShown=await evaluate(`(()=>{const rows=[...document.querySelectorAll('[data-cost-key]')];return rows.length===3&&rows.every(e=>Number(e.dataset.value)>0&&Number(e.dataset.threshold)>0)&&document.querySelector('#figure-outcome-costs').textContent.includes('研究决策')})()`);
  report.checks.completeInspectionArchitecture=await evaluate(`(()=>{const t=document.querySelector('#figure-inspection-architecture').textContent;return ['公开观测','名义估计','两本任务账','执行边界与FIFO','执行检查与更新','离线评分'].every(v=>t.includes(v))})()`);
  report.checks.mentorRequestsAddressed=await evaluate(`(()=>{const t=document.body.textContent;return ['10 kV','380 V','CDU','E/G','RGB','RMSE','R²','48023-2026','48097-2026','2027-02-01','2027-03-01'].every(s=>t.includes(s))})()`);
  report.checks.summaryPrecedesFirstTable=await evaluate(`(()=>{const summary=document.querySelector('.project-summary'),table=document.querySelector('table');return !!summary&&(summary.compareDocumentPosition(table)&Node.DOCUMENT_POSITION_FOLLOWING)!==0&&summary.textContent.includes('155/210')&&document.querySelector('#overview').textContent.includes('1080')&&!summary.textContent.includes('/89')})()`);
  report.checks.engineeringForeground=await evaluate(`(()=>{const t=document.querySelector('#model').textContent;return ['0.035','20秒','95°C','161／145','1.809','2.82110','29.68462','128柜／16组'].every(v=>t.includes(v))&&document.querySelectorAll('#model .principle-box').length===1})()`);
  report.checks.actualComparisonTable=await evaluate(`(()=>{const table=document.querySelector('[data-table="method-comparison"]');return table.tBodies[0].rows.length===7&&table.querySelectorAll('[data-result-state="primary"]').length===3&&table.querySelectorAll('[data-result-state="development"]').length===2&&table.querySelectorAll('[data-result-state="not_run"]').length===2&&['0.310901','0.313052','60.23','58.14','未留帧','未计时'].every(v=>table.textContent.includes(v))})()`);
  report.checks.technicalDetailsInAppendix=await evaluate(`['registered-rules','rule-diagnosis','fifo-cycle','fifo-actions','original-paper-scores'].every(name=>!!document.querySelector('#figure-'+name).closest('details'))`);
  report.checks.noUnsupportedTrainingStatus=await evaluate(`![...document.querySelectorAll('[data-result-state="not_run"]')].some(e=>e.textContent.includes('正在训练')||e.textContent.includes('已完成'))`);
  report.checks.completeSupplementMethods=await evaluate(`['supplement-errors','supplement-tasks'].every(id=>{const rows=[...document.querySelectorAll('[data-table="'+id+'"] [data-supplement-method]')];return JSON.stringify(rows.map(e=>e.dataset.supplementMethod))===${JSON.stringify(JSON.stringify(['nominal_tour','nominal_fifo','nominal_greedy','nominal_ppo','cvae_fifo','cvae_greedy','cvae_ppo']))}&&rows.every(e=>!e.textContent.includes('待运行'))})`);
  report.checks.supplementEvidenceScope=await evaluate(`['1080个','12个独立种子块','34,560','8,640','295,777','720','60条唯一物理轨迹'].every(v=>document.body.textContent.includes(v))`);
  report.checks.noDuplicateElementIds=await evaluate(`(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return ids.length===new Set(ids).size})()`);
  report.checks.summaryExplainsEstimateTaskDifference=await evaluate(`(()=>{const t=document.querySelector('#overview').textContent;return ['确认率','同一观测流','温度估计是否准确','及时完成专业核查'].every(s=>t.includes(s))})()`);
  report.checks.visualDomainTransition=await evaluate(`(()=>{const t=document.querySelector('#figure-pid-visual-sample').nextElementSibling.textContent;return ['户外','10 kV','380 V','54 V','拟适配','机房图像适配','校准测温接入后'].every(s=>t.includes(s))})()`);
  report.checks.estimationTaskTimingExample=await evaluate(`(()=>{const t=document.querySelector('[data-table="estimation-confirmation-gap"]');return t.tBodies[0].rows.length===2&&['865→895秒','835→880秒','860→875秒','840→900秒'].every(s=>t.textContent.includes(s))})()`);
  report.checks.concreteRoadmap=await evaluate(`(()=>{const t=document.querySelector('#roadmap').textContent;return ['正式条款','机房图像','硬重访','RSI','512／1024柜'].every(v=>t.includes(v))})()`);
  report.checks.scopeNotesCollected=await evaluate(`document.querySelectorAll('.scope-note').length===2&&document.body.textContent.includes('显示外观')&&document.body.textContent.includes('元数据')`);
  report.checks.completeReadingGuides=await evaluate(`document.querySelectorAll('[data-guide-figure]').length===31&&document.querySelectorAll('[data-guide-table]').length===27&&document.querySelectorAll('#reading-symbols dl>div').length===6&&[...document.querySelectorAll('figure')].every(e=>e.querySelector('[data-guide-figure]')&&e.querySelectorAll('figcaption .reading-notes p').length===2)`);
  const regions=[['#reading-symbols','symbol-guide'],['#table-professional-risk','risk-table-guide'],['#figure-supplement-estimation figcaption','estimation-reading'],['#figure-supplement-contrasts figcaption','contrast-reading'],['.project-summary','summary'],['#overview','overview'],['#figure-model','model'],['#figure-pid-visual-sample','pid-sample'],
    ['#figure-visual-interface','visual-interface'],['#principle-control','control'],['#standards','standards'],['#scale','scale'],
    ['#principle-estimation','estimation-formula'],['#principle-risk','risk-formula'],['#principle-return','return-formula'],
    ['#fifo','fifo-flow'],['#figure-inspection-architecture','inspection-architecture'],['[data-table="task-contract"]','task-contract'],['#comparison','comparison'],
    ['#roadmap','roadmap']];
  for(const name of manifest.main_figure_ids.filter(name=>name.startsWith('supplement-')))regions.push(['#figure-'+name,name]);
  for(const name of ['errors','tasks','fixed-stream','contrasts','healthy','latency','scale','scale-cycles','training'])regions.push(['[data-table="supplement-'+name+'"]','supplement-table-'+name]);
  const appendixRegions=[['#figure-task-21 figcaption','timing-reading'],['#appendix','appendix'],['#figure-estimated-temperature','old-estimated-temperature'],['#figure-offline-temperature','old-offline-temperature'],
    ['#figure-confirmations','results'],['#figure-outcome-costs','outcome-costs'],['#figure-public-risk','alarm-map'],
    ['[data-table="fifo-queue"]','fifo-queue'],['#figure-fifo-actions','fifo-actions'],
    ['[data-table="fault-cases"]','fault-cases'],['#figure-paired-net','paired-net'],['#figure-registered-rules','registered-rules'],
    ['#figure-rule-diagnosis','rule-diagnosis'],['#figure-execution-chain','appendix-case'],['#figure-task-17','task-timelines'],['#figure-original-paper-scores','paper-comparison']];
  appendixRegions.push(['[data-table="method-comparison"]','method-comparison'],['#figure-supplement-seed-blocks','supplement-seed-blocks'],['[data-table="supplement-families"]','supplement-families'],['[data-table="supplement-seeds"]','supplement-seeds'],['[data-table="supplement-policy-training"]','supplement-policy-training'],['[data-table="estimation-confirmation-gap"]','estimation-confirmation-gap']);
  for(const [width,height] of [[1366,768],[1920,1080]]){
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    await evaluate('window.scrollTo(0,0)');await delay(100);
    const hero=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    const heroFile=path.join(previews,`${width}x${height}-entry.png`);fs.writeFileSync(heroFile,Buffer.from(hero.data,'base64'));
    report.screenshot_sha256[path.relative(root,heroFile).replaceAll('\\','/')]=digest(heroFile);
    for(const [selector,label] of regions)await inspect(selector,width,height,label);
    await evaluate(`document.querySelector('.case-appendix').open=true`);
    report.checks.appendixCalculationsReadable=await evaluate(`document.querySelectorAll('.principle-box').length===4&&[...document.querySelectorAll('.formula-scroll')].every(e=>e.getBoundingClientRect().height>30)&&document.querySelector('#principle-estimation').textContent.includes('800 kJ/K')&&document.querySelector('#principle-return').textContent.includes('完整')`);
    report.checks.allFaultCasesShown=await evaluate(`document.querySelector('[data-table="fault-cases"]').tBodies[0].rows.length===12`);
    for(const [selector,label] of appendixRegions)await inspect(selector,width,height,label);
    await evaluate(`document.querySelector('.case-appendix').open=false`);
  }
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  for(const [selector,label] of [['#reading-symbols','symbol-guide'],['#table-professional-risk','risk-table-guide'],['#figure-supplement-estimation figcaption','estimation-reading'],['.project-summary','summary'],['#overview','overview'],['#model','model'],['#figure-visual-interface','visual-interface'],['#hotspots','hotspots'],['#fifo','fifo'],['#comparison','comparison'],['#roadmap','roadmap']])await inspect(selector,390,844,label);
  await send('Emulation.setDeviceMetricsOverride',{width:710,height:1020,deviceScaleFactor:1,mobile:false});
  await send('Emulation.setEmulatedMedia',{media:'print'});
  report.checks.printAppendixVisible=await evaluate(`document.querySelector('#figure-execution-chain').getBoundingClientRect().height>0`);
  report.checks.printContentVisible=await evaluate(`[...document.querySelectorAll('[data-report-section]')].every(e=>getComputedStyle(e).display!=='none')&&getComputedStyle(document.querySelector('.contents')).display==='none'`);
  report.checks.printFormulaFits=await evaluate(`[...document.querySelectorAll('.formula-scroll')].every(e=>e.scrollWidth<=e.clientWidth+1)`);
  const pdf=await send('Page.printToPDF',{landscape:false,printBackground:true,preferCSSPageSize:true});
  const pdfFile=path.join(work,'report-print.pdf');fs.writeFileSync(pdfFile,Buffer.from(pdf.data,'base64'));report.print_pdf_sha256=digest(pdfFile);
  assert(Object.values(report.checks).every(Boolean),'Content check failed: '+JSON.stringify(report.checks));
  assert(!report.externalRequests.length&&!report.exceptions.length,'External dependency or browser error');
  assert(digest(htmlPath)===report.html_sha256,'HTML changed while checking');report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error);process.exitCode=1;}
finally{
  report.checked_at_utc=new Date().toISOString();
  fs.writeFileSync(path.join(root,'paper/generated/supervisor-report-verification.json'),JSON.stringify(report,null,2)+'\n');
  fs.writeFileSync(path.join(root,'paper/generated/briefing-browser-verification.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,error:report.error,checks:report.checks,viewCount:report.views.length,screenshotCount:Object.keys(report.screenshot_sha256).length},null,2));
  if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close');}catch{}socket.close();}
  if(browser.exitCode===null)browser.kill();
}})();

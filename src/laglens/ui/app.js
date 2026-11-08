'use strict';
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="laglens-token"]').content;
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (v,d=1) => v == null ? '—' : Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed = (v,d=1) => `${v>0?'+':v<0?'−':''}${fmt(Math.abs(v),d)}`;
let activeView='capture', records=[], preview=null, selectedRecord=null, status=null, pollBusy=false, compareData=null, toastTimer;

async function api(path,body){
  const options=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-LagLens-Token':token},body:JSON.stringify(body)};
  const response=await fetch(path,options);
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'The request failed.');
  return data;
}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true;},6500);}
function error(text){$('capture-error').textContent=text;$('capture-error').hidden=!text;}

function metrics(element,a){
  const values=[['Average FPS',a?.average_fps,'fps'],['1% low FPS',a?.low_1_fps,'fps'],['P99 frame time',a?.p99_ms,'ms'],['Stutter events',a?.stutter_count??null,'']];
  element.innerHTML=values.map(([label,value,unit],i)=>`<div class="metric"><span>${label}</span><strong>${fmt(value,i===3?0:1)}<small>${unit}</small></strong></div>`).join('');
}

function plot(element,points,threshold=null,height=220,limit=null){
  const size=Math.max(20,Math.min(320,points.length||20));
  const first=points.length?points[0].t:0,last=points.length?points.at(-1).t:1000;
  const span=Math.max(last-first,1);
  const values=Array(size).fill(null);
  for(const point of points){
    const bucket=Math.min(size-1,Math.floor((point.t-first)/span*(size-1)));
    values[bucket]=Math.max(values[bucket]??0,point.ms);
  }
  const labels=values.map((_,i)=>`${fmt((first+span*i/(size-1))/1000,1)}s`);
  const annotations=[];
  if(points.length){
    const peak=points.reduce((best,p)=>p.ms>best.ms?p:best,points[0]);
    if(threshold&&peak.ms>threshold){
      annotations.push({at:Math.min(size-1,Math.floor((peak.t-first)/span*(size-1))),label:`Peak ${fmt(peak.ms)} ms`,short:`${fmt(peak.ms,0)} ms`});
    }
  }
  const maxValue=limit??Math.max(40,...values.filter(v=>v!==null),threshold||0);
  // Equal-width time bins. Each bin keeps its maximum so narrow hitches remain visible.
  Charts.line(element,{labels,series:[{name:'Frame time',values}],height,format:v=>`${fmt(v)} ms`,tickFormat:v=>fmt(v,0),
    min:0,annotations,max:maxValue*1.08,
    reference:threshold?{value:threshold,label:`Threshold ${fmt(threshold)} ms`}:undefined,
    xAt:[0,Math.round((size-1)/4),Math.round((size-1)/2),Math.round((size-1)*3/4),size-1]});
}

function findings(element,items){
  element.innerHTML=items.length?items.map(f=>`<article class="finding"><h3>${escapeHtml(f.title)}<span class="confidence">${escapeHtml(f.confidence)}</span></h3><p>${escapeHtml(f.evidence)}</p><p class="next">${escapeHtml(f.next)}</p></article>`).join(''):'<article class="finding"><h3>Frame timing comes first</h3><p>A capture records the intervals between your game’s presented frames.</p></article><article class="finding"><h3>Context around the moment</h3><p>CPU, GPU-engine and memory samples help test explanations. Unavailable readings stay blank.</p></article><article class="finding"><h3>A result you can check</h3><p>Findings include their evidence and a next test. An unresolved cause is reported as unresolved.</p></article>';
}

async function refreshProcesses(){
  const previous=$('process').value;
  const entries=await api('/api/processes');
  $('process').innerHTML='<option value="">Choose a running game…</option>'+entries.map(p=>`<option value="${p.pid}">${escapeHtml(p.name)} · PID ${p.pid} · ${p.memory_mb.toLocaleString()} MB</option>`).join('');
  if(entries.some(p=>String(p.pid)===previous))$('process').value=previous;
}

function renderCapture(){
  const a=preview?.analysis||status?.analysis;
  const recording=Boolean(status?.capture);
  metrics($('capture-stats'),a);
  plot($('capture-chart'),a?.timeline||[],a?.threshold_ms,180);
  $('chart-empty').hidden=Boolean(a?.frame_count);
  $('capture-demo-notice').hidden=preview?.source!=='demo';
  $('start').hidden=recording;$('stop').hidden=!recording;
  $('mark').disabled=!recording;
  for(const name of ['process','target','duration','probe','refresh-processes'])$(name).disabled=recording;
  document.querySelector('.dot').classList.toggle('recording',recording);
  $('capture-status').textContent=recording?`Recording ${status.capture.process_name} · ${fmt(status.capture.elapsed_s,0)} / ${status.capture.duration_limit} sec`:preview?'Sample preview · Start recording to measure your game.':'Ready. Your recordings stay on this PC.';
  $('capture-chart-note').textContent=a?.frame_count?`${a.frame_count.toLocaleString()} presented frames · ${fmt(a.duration_s)} sec`:'Presented frames · milliseconds';
  error(status?.error||'');
  $('finding-count').textContent=a?.frame_count?`Threshold ${fmt(a.threshold_ms)} ms`:'Waiting for frames';
  findings($('capture-findings'),a?.findings||[]);
  const markers=status?.markers||[];
  $('markers').innerHTML=markers.length?markers.slice(-4).map((m,i)=>`<div class="marker-row"><span>At ${fmt(m.t/1000)}s</span>${m.saved_id?`<a class="text-button" href="#session/${m.saved_id}">Open moment →</a>`:`<span class="muted">${escapeHtml(m.state)}</span>`}</div>`).join(''):'<p class="empty-message">No moments marked in this session.</p>';
  const s=preview?.sensors?.at(-1)||status?.latest_sensor;
  const context=[['Busiest CPU core',s?`${fmt(s.cpu_peak_pct,0)}%`:'—'],['Game GPU 3D engine',s?.gpu_pct!=null?`${fmt(s.gpu_pct)}%`:'—'],['System RAM used',s?`${fmt(s.ram_pct)}%`:'—'],['Game memory',s?`${fmt(s.process_ram_mb/1024,2)} GB`:'—'],['Network probe',s?.ping_lost?'Timed out':s?.ping_ms!=null?`${fmt(s.ping_ms,0)} ms`:(recording&&status.capture.probe?'Waiting':'Off')]];
  $('sensors').innerHTML=context.map(([label,value])=>`<div><dt>${label}</dt><dd>${value}</dd></div>`).join('');
  if(recording)$('mark').title=status.capabilities.hotkey_note;
}

function date(value){return value?value.slice(0,16).replace('T',' '):'—';}
function sourceName(s){return {demo:'Illustrative sample',import:'CSV import',live:'Live recording',incident:'Marked moment'}[s]||s;}
async function loadLibrary(){
  records=await api('/api/sessions');
  if(!records.length){
    $('library-content').innerHTML='<div class="empty-state"><h2>Your first capture starts here.</h2><p>Record a running game or import a PresentMon CSV. Examples are available if you want to explore first.</p><a class="text-button" href="#capture">Go to capture →</a></div>';
  }else{
    $('library-content').innerHTML=`<table class="data-table"><thead><tr><th>Capture</th><th class="num">Length</th><th class="num">Average FPS</th><th class="num">Stutters</th><th></th></tr></thead><tbody>${records.map(r=>`<tr><td>${escapeHtml(r.name)}<small>${date(r.created_at)} · ${sourceName(r.source)}</small></td><td class="num" data-label="Length">${fmt(r.analysis.duration_s)}s</td><td class="num" data-label="FPS">${fmt(r.analysis.average_fps)}</td><td class="num" data-label="Stutters">${fmt(r.analysis.stutter_count,0)}</td><td><a class="text-button" href="#session/${r.id}">Open capture →</a></td></tr>`).join('')}</tbody></table>`;
  }
  const before=$('before').value,after=$('after').value;
  const options='<option value="">Choose a saved capture…</option>'+records.map(r=>`<option value="${r.id}">${escapeHtml(r.name)} · ${fmt(r.analysis.duration_s,0)}s</option>`).join('');
  $('before').innerHTML=options;$('after').innerHTML=options;
  if(records.some(r=>r.id===before))$('before').value=before;
  if(records.some(r=>r.id===after))$('after').value=after;
  $('compare-button').disabled=records.length<2;
}

async function openSession(id){
  selectedRecord=await api('/api/session/'+encodeURIComponent(id));
  const r=selectedRecord,a=r.analysis;
  $('session-title').textContent=r.name;
  $('session-subtitle').textContent=`${date(r.created_at)} · ${sourceName(r.source)} · ${a.frame_count.toLocaleString()} presented frames`;
  $('session-notice').hidden=r.source!=='demo';
  $('session-notice').textContent='Illustrative sample data. These numbers do not describe your PC.';
  metrics($('session-stats'),a);
  plot($('session-chart'),a.timeline,a.threshold_ms,260);
  $('session-threshold').textContent=`Stutter threshold: ${fmt(a.threshold_ms)} ms`;
  findings($('session-findings'),a.findings);
  $('session-event-count').textContent=`${a.stutter_count} events`;
  $('session-events').innerHTML=a.events.length?a.events.slice(0,7).map(e=>`<div class="event-row"><span class="num">${fmt(e.t/1000)}s</span><span class="num">${fmt(e.peak_ms)} ms</span><span class="muted">${e.frames} slow ${e.frames===1?'frame':'frames'}</span></div>`).join(''):'<p class="empty-message">No events crossed this capture’s threshold.</p>';
  if(a.events.length>7)$('session-events').innerHTML+=`<p class="meta">Showing 7 of ${a.events.length}. The full capture is included in JSON export.</p>`;
}

async function route(){
  const hash=location.hash.slice(1)||'capture',parts=hash.split('/');
  activeView=['capture','library','compare','guide','session'].includes(parts[0])?parts[0]:'capture';
  document.querySelectorAll('.view').forEach(view=>view.hidden=view.id!==activeView+'-view');
  document.querySelectorAll('[data-nav]').forEach(link=>{
    if(link.dataset.nav===activeView||(activeView==='session'&&link.dataset.nav==='library'))link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
  });
  try{
    if(['library','compare'].includes(activeView))await loadLibrary();
    if(activeView==='session'&&parts[1])await openSession(parts[1]);
    if(activeView==='capture')renderCapture();
  }catch(e){toast(e.message);}
}

async function sample(){
  try{
    const loaded=await api('/api/demo',{});
    await loadLibrary();
    const original=records.find(r=>r.source==='demo'&&r.name.includes('original'));
    const adjusted=records.find(r=>r.source==='demo'&&r.name.includes('adjusted'));
    if(original&&adjusted){$('before').value=original.id;$('after').value=adjusted.id;}
    if(activeView==='capture'){
      preview=await api('/api/session/'+(original?.id||loaded[0].id));renderCapture();
    }else if(activeView==='compare')await runCompare();
    toast('Illustrative examples loaded. They are not measurements of your PC.');
  }catch(e){toast(e.message);}
}

async function runCompare(){
  const before=$('before').value,after=$('after').value;
  if(!before||!after)return toast('Choose both a baseline and an after capture.');
  if(before===after)return toast('Choose two different captures.');
  try{
    const [comparison,a,b]=await Promise.all([api('/api/compare',{before,after}),api('/api/session/'+before),api('/api/session/'+after)]);
    compareData={a,b};$('comparison-empty').hidden=true;$('comparison').hidden=false;
    const warnings=['Repeat the same scene and route. One pair of runs does not establish causation.',...comparison.warnings];
    $('compare-warnings').textContent=warnings.join(' ');
    $('comparison-table').innerHTML=`<table class="data-table"><thead><tr><th>Metric</th><th class="num">Baseline</th><th class="num">After change</th><th class="num">Difference</th></tr></thead><tbody>${comparison.metrics.map(m=>`<tr><td>${m.label}</td><td class="num" data-label="Baseline">${fmt(m.before)} ${m.unit}</td><td class="num" data-label="After">${fmt(m.after)} ${m.unit}</td><td class="num ${m.direction==='same'?'':m.direction==='better'?'better':'worse'}" data-label="Change">${signed(m.delta)} ${m.unit}<small>${m.percent===null?'—':signed(m.percent)+'%'} vs baseline</small></td></tr>`).join('')}</tbody></table>`;
    const max=Math.max(40,...a.analysis.timeline.map(p=>p.ms),...b.analysis.timeline.map(p=>p.ms));
    plot($('before-chart'),a.analysis.timeline,null,220,max);plot($('after-chart'),b.analysis.timeline,null,220,max);
    $('comparison-statement').textContent=comparison.statement;
  }catch(e){toast(e.message);}
}

async function download(fmtType){
  if(!selectedRecord)return;
  try{
    if(window.pywebview?.api){
      const saved=await window.pywebview.api.save_report(selectedRecord.id,fmtType);
      toast('Saved: '+saved);
    }else{
      const link=document.createElement('a');link.href=`/export/${selectedRecord.id}.${fmtType}`;link.download=`LagLens-report.${fmtType}`;document.body.append(link);link.click();link.remove();
    }
  }catch(e){toast('Export failed: '+e.message);}
}

$('refresh-processes').addEventListener('click',()=>refreshProcesses().catch(e=>toast(e.message)));
$('start').addEventListener('click',async()=>{
  if(!$('process').value)return toast('Choose your game process first.');
  $('start').disabled=true;
  try{preview=null;status=await api('/api/start',{pid:Number($('process').value),target:Number($('target').value),duration:Number($('duration').value),probe:$('probe').checked});renderCapture();}
  catch(e){error(e.message);}finally{$('start').disabled=false;}
});
$('stop').addEventListener('click',async()=>{try{$('stop').disabled=true;status=await api('/api/stop',{});renderCapture();await loadLibrary();toast('Recording stopped. Capture saved if frames were received.');}catch(e){error(e.message);}finally{$('stop').disabled=false;}});
$('mark').addEventListener('click',async()=>{try{await api('/api/mark',{});toast('Moment marked. Collecting 5 seconds of recovery…');}catch(e){toast(e.message);}});
$('clear-preview').addEventListener('click',()=>{preview=null;renderCapture();});
document.querySelectorAll('.sample-action').forEach(button=>button.addEventListener('click',sample));
$('compare-button').addEventListener('click',runCompare);
$('import').addEventListener('click',()=>$('csv-file').click());
$('csv-file').addEventListener('change',async(event)=>{
  const file=event.target.files[0];if(!file)return;
  if(file.size>32*1024*1024){event.target.value='';return toast('Choose a CSV smaller than 32 MB.');}
  try{const record=await api('/api/import',{csv:await file.text(),name:file.name.replace(/\.csv$/i,''),target:Number($('target').value)});location.hash='session/'+record.id;}catch(e){toast(e.message);}finally{event.target.value='';}
});
for(const fmtType of ['svg','html','json'])$('export-'+fmtType).addEventListener('click',()=>download(fmtType));
window.addEventListener('hashchange',route);
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(activeView==='capture')renderCapture();else if(activeView==='session'&&selectedRecord)plot($('session-chart'),selectedRecord.analysis.timeline,selectedRecord.analysis.threshold_ms,260);else if(activeView==='compare'&&compareData){const max=Math.max(40,...compareData.a.analysis.timeline.map(p=>p.ms),...compareData.b.analysis.timeline.map(p=>p.ms));plot($('before-chart'),compareData.a.analysis.timeline,null,220,max);plot($('after-chart'),compareData.b.analysis.timeline,null,220,max);}},180);});

async function poll(){
  if(pollBusy)return;pollBusy=true;
  try{const wasRecording=Boolean(status?.capture);status=await api('/api/status');if(activeView==='capture')renderCapture();if(wasRecording&&!status.capture){await loadLibrary();if(!status.error)toast('Capture saved. Find it in Your captures.');}}
  catch(e){if(activeView==='capture')error('Connection lost. Keep LagLens running and reload this window.');}
  finally{pollBusy=false;}
}
async function init(){await document.fonts.ready;try{await Promise.all([refreshProcesses(),poll(),loadLibrary()]);await route();}catch(e){toast(e.message);}setInterval(poll,1000);}
init();

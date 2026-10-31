import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Window } from 'happy-dom';
import { initPlanner, safeExternalUrl, encodePcmWav } from '../src/ui/planner.ts';

const html = readFileSync(new URL('../index.html',import.meta.url),'utf8');
const turn = () => new Promise(resolve=>setTimeout(resolve,30));

function setup(handler: (url: string, init?: RequestInit)=>Promise<Response>) {
  const window = new Window({ url:'http://localhost:8080', settings:{disableJavaScriptFileLoading:true,disableCSSFileLoading:true,disableComputedStyleRendering:true} });
  window.document.write(html.replace(/<script[\s\S]*?<\/script>/g,''));
  Object.assign(globalThis,{window,document:window.document,HTMLElement:window.HTMLElement,HTMLButtonElement:window.HTMLButtonElement,DOMException:window.DOMException});
  Object.defineProperty(globalThis,'navigator',{value:window.navigator,configurable:true});
  globalThis.fetch = async (url,init) => String(url)==='/api/status'
    ? new Response(JSON.stringify({status:'ok',features:{language:true,voice:true,venues:true}}),{headers:{'content-type':'application/json'}})
    : handler(String(url),init);
  initPlanner();
  const submit=(query='run in HSR Layout')=>{
    (window.document.querySelector('#planner-query') as HTMLTextAreaElement).value=query;
    window.document.querySelector('[data-planner-form]')!.dispatchEvent(new window.Event('submit',{cancelable:true}));
  };
  return {window,submit,cleanup:()=>{window.dispatchEvent(new window.Event('pagehide')); window.happyDOM.abort();}};
}

function plan() {
  const assessment = {verdict:'Best available',aqi:{meaning:'Moderate air',advice:'Recheck conditions'},location:{maps_url:'https://www.google.com/maps/',precision_note:'Model grid'},warnings:[],reasons:['Complete hours'],checklist:['Recheck']};
  const window={start:'2026-11-01T08:00:00+05:30',end:'2026-11-01T09:00:00+05:30',us_aqi:80,max_aqi:80,pm2_5:20,rain_probability:0,temperature:25,score:90,aqi_category:'Moderate',assessment};
  const backup={...window,start:'2026-11-01T10:00:00+05:30',end:'2026-11-01T11:00:00+05:30',us_aqi:160,max_aqi:160,aqi_category:'Unhealthy',assessment:{...assessment,verdict:'Air remains adverse',aqi:{meaning:'Unhealthy air',advice:'Consider indoors'},warnings:['Pollution warning']}};
  return {status:'ok',plan_id:'random-token',expires_at:new Date(Date.now()+60000).toISOString(),location:{name:'Chosen park',latitude:12.9,longitude:77.6},timezone:'Asia/Kolkata',window,backups:[backup],assessment,source:'Open-Meteo',fetched_at:new Date().toISOString(),summary:'The full answer',venue:{status:'ok',name:'Chosen park',address:'Bengaluru',rating:4.2,rating_count:120,google_maps_uri:'https://maps.google.com',reviews:[{text:'<img src=x onerror=alert(1)>paths',author:'Visitor',author_url:'javascript:alert(2)',published_at:'2026-10-01'}]}};
}

test('provider content stays text and backup selection changes assessment and export', async ()=>{
  const calls:string[]=[];
  const env=setup(async url=>{
    calls.push(url);
    if(url==='/api/plan')return new Response(JSON.stringify(plan()),{headers:{'content-type':'application/json'}});
    return new Response('BEGIN:VCALENDAR',{headers:{'content-type':'text/calendar'}});
  });
  try {
    await turn();env.submit();await turn();
    const root=env.window.document.querySelector('[data-plan-results]')!;
    assert.match(root.textContent!,/Visitor/);
    assert.match(root.textContent!,/<img src=x/);
    assert.equal(root.querySelector('img[src=x]'),null);
    assert.equal(root.querySelector('a[href^="javascript:"]'),null);
    const buttons=[...root.querySelectorAll('button')];
    buttons.find(b=>b.textContent?.startsWith('Backup 1'))!.click();
    assert.match(root.querySelector('.planner__selected')!.textContent!,/Air remains adverse/);
    assert.match(root.querySelector('.planner__selected')!.textContent!,/160/);
    buttons.find(b=>b.textContent==='Save selected time')!.click();await turn();
    assert.ok(calls.includes('/api/calendar/random-token?place_index=0&window_index=1'));
  } finally {env.cleanup();}
});

test('failed refresh clears previous assessment and reports server error',async()=>{
  let count=0;
  const env=setup(async()=> ++count===1 ? new Response(JSON.stringify(plan())) : new Response(JSON.stringify({status:'error',error:'No complete window fits your limits'}),{status:422}));
  try {
    await turn();env.submit();await turn();
    assert.match(env.window.document.querySelector('[data-plan-results]')!.textContent!,/Chosen park/);
    env.submit('run in HSR with AQI at most 0');await turn();
    assert.equal(env.window.document.querySelector('[data-plan-results]')!.childElementCount,0);
    assert.match(env.window.document.querySelector('[data-plan-status]')!.textContent!,/No complete window/);
    assert.equal((env.window.document.querySelector('[data-plan-submit]') as HTMLButtonElement).disabled,false);
  } finally {env.cleanup();}
});

test('cancelled request cannot render after a newer result',async()=>{
  let release:(response:Response)=>void=()=>{};
  let count=0;
  const env=setup(async()=> ++count===1 ? new Promise<Response>(resolve=>{release=resolve;}) : new Response(JSON.stringify({...plan(),location:{name:'New place',latitude:12,longitude:77}})));
  try {
    await turn();env.submit();await turn();
    (env.window.document.querySelector('[data-plan-cancel]') as HTMLButtonElement).click();
    env.submit('run in New place');await turn();
    release(new Response(JSON.stringify(plan())));await turn();
    assert.match(env.window.document.querySelector('[data-plan-results]')!.textContent!,/New place/);
    assert.equal(env.window.document.querySelector('.planner__place h4')!.textContent,'New place');
  } finally {env.cleanup();}
});

test('microphone encoder produces valid mono PCM16 samples and duration cap',async()=>{
  const blob=encodePcmWav([new Float32Array([-2,-.5,0,.5,2,Number.NaN])],16000);
  const bytes=await blob.arrayBuffer();const data=new DataView(bytes);
  assert.equal(new TextDecoder().decode(bytes.slice(0,4)),'RIFF');
  assert.equal(data.getUint16(22,true),1);assert.equal(data.getUint32(24,true),16000);assert.equal(data.getUint16(34,true),16);
  assert.deepEqual([0,1,2,3,4,5].map(i=>data.getInt16(44+i*2,true)),[-32768,-16384,0,16384,32767,0]);
  assert.throws(()=>encodePcmWav([new Float32Array(16000*30+1)],16000));
  assert.throws(()=>encodePcmWav([],16000));
  assert.equal(safeExternalUrl('javascript:alert(1)'),null);
  assert.equal(safeExternalUrl('https://u:p@example.com'),null);
});

test('planner readiness resolves false when the planner mount is absent', async () => {
  const window = new Window({ url: 'http://localhost:8080' });
  window.document.write('<main></main>');
  Object.assign(globalThis, { window, document: window.document });
  try {
    const state = initPlanner();
    assert.equal(await state.ready, false);
  } finally {
    window.happyDOM.abort();
  }
});

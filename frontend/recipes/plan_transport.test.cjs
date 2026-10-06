// Synthetic transport regressions, not planner acceptance. Real jobs are tested separately.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const {webcrypto}=require('node:crypto');
const source=fs.readFileSync(process.env.SMAKO_TRANSPORT_SOURCE||'backend/app/static/complete-recipes.js','utf8');
const job='/api/plan-jobs/'+'a'.repeat(32), old='/api/plan-jobs/'+'b'.repeat(32);
const final={plan_id:'saved',revision:1,plan:{recipes:[],optimized_basket:{stores:[]}}};
const response=(data,status=201)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
function setup(fetch){
  const events=[],data=new Map(),window=new EventTarget(),document=new EventTarget();
  class CustomEvent extends Event{constructor(type,{detail}){super(type);this.detail=detail;}}
  window.addEventListener('smako:plan-transport',e=>events.push(e.detail));
  const context=vm.createContext({window,document,CustomEvent,crypto:webcrypto,fetch,Response,TypeError,SyntaxError,Error,DOMException,AbortController,performance,Date,
    setTimeout:(f,ms)=>setTimeout(f,Math.max(1,ms/1000)),clearTimeout,
    sessionStorage:{getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)}});
  vm.runInContext(source,context);
  return {api:window.SmakoRecipes,window,events};
}
test('lost accepted start response recovers through lookup, one POST only',async()=>{
  const urls=[];const {api}=setup(async(url,options)=>{urls.push([url,options.method]);if(options.method==='POST')throw new TypeError('connection reset');if(url.includes('plan-job-requests'))return response({status:'pending',status_url:job},202);return response(final);});
  const r=await api.jobRequest({scope:'public',url:'/api/plans',payload:{recipes:5}});
  assert.equal(r.status,201);assert.equal(urls.filter(x=>x[1]==='POST').length,1);assert.equal(urls.at(-1)[0],job);
  assert.equal(api.pendingJob('public').url,job); // Retained until result is rendered.
  api.forgetJob('public');assert.equal(api.pendingJob('public'),null);
});
test('bounded outage retains job and manual resume performs only GET',async()=>{
  let offline=true,calls=0;const {api}=setup(async()=>{calls++;if(offline)throw new TypeError('offline');return response(final);});
  const requestId=webcrypto.randomUUID();
  await assert.rejects(api.jobRequest({scope:'personal',url:'/api/plans',payload:{},requestId}),e=>e.reconnect===true);
  assert.equal(calls,8);assert.equal(api.pendingJob('personal').requestId,requestId);
  offline=false;assert.equal((await api.jobRequest({scope:'personal'})).status,201);
});
test('HTTP failures, HTML, malformed JSON and status schema are not network retries',async()=>{
  for(const [make,expected] of [
    [()=>response({detail:'expired'},401),401],[()=>response({detail:'forbidden'},403),403],
    [()=>response({detail:'missing'},404),404],[()=>response({detail:'invalid'},422),422],
    [()=>new Response('<html/>',{headers:{'Content-Type':'text/html'}}),'svarstyp'],
    [()=>new Response('{',{headers:{'Content-Type':'application/json'}}),'JSON'],
    [()=>response({status:'finished'},202),'planeringssvar'],[()=>response({}),'planeringsresultat']]){
    let calls=0;const {api}=setup(async()=>{calls++;return make();});
    const run=api.jobRequest({scope:'public',url:'/api/plans',payload:{}});
    if(typeof expected==='number')assert.equal((await run).status,expected);
    else await assert.rejects(run,new RegExp(expected));
    assert.equal(calls,1);
  }
});
test('server terminal 503 is preserved; transport 429 retries with no extra generation',async()=>{
  let calls=0;const {api}=setup(async()=>{calls++;return calls===1?response({detail:'limited'},429):response(final);});
  assert.equal((await api.jobRequest({scope:'public',url:'/api/plans',payload:{}})).status,201);assert.equal(calls,2);
  const other=setup(async()=>{const r=response({detail:'failed'},503);r.headers.set('X-Plan-Request-ID','original');return r;});
  assert.equal((await other.api.jobRequest({scope:'public',url:job})).status,503);
});
test('pagehide abort is explicit; pageshow reconnects same saved job',async()=>{
  let slow=true;const {api,window,events}=setup(async(url,options)=>{
    if(url==='/api/plans')return response({status:'pending',status_url:job},202);
    if(!slow)return response(final);
    return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(options.signal.reason),{once:true}));
  });
  const first=api.jobRequest({scope:'public',url:'/api/plans',payload:{}});
  await new Promise(r=>setTimeout(r,5));window.dispatchEvent(new Event('pagehide'));
  await assert.rejects(first,e=>e.lifecycle==='pagehide');assert.equal(api.pendingJob('public').url,job);
  slow=false;window.dispatchEvent(new Event('pageshow'));assert.equal((await api.jobRequest({scope:'public'})).status,201);
  assert.ok(events.some(e=>e.event==='abort'&&e.reason==='pagehide'));
});
test('replaced reader cannot return a late old response',async()=>{
  let release;const {api}=setup(async url=>url===old?new Promise(r=>{release=r;}):response(final));
  const first=api.jobRequest({scope:'public',url:old});
  const caught=first.catch(e=>e);
  const second=api.jobRequest({scope:'personal',url:job});
  assert.equal((await second).status,201);release(response(final));
  assert.equal((await caught).lifecycle,'replaced');
});

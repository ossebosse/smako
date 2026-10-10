// Executes the actual public controller functions with controlled transport.
// This is a focused regression, not a replacement for real browser/job tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2] || 'backend/app/static/app.js', 'utf8');
const extract = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
const runtime = extract('  async function loadPublicRuntimeStatus()', '  async function submitPlan(');
const apply = extract('  function applySavedPlan(', '  async function responseJson(');
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
function harness() {
  const calls = [], statuses = [];
  const ctx = vm.createContext({AbortController, console, calls, statuses,
    dom:{serviceRetryButton:{},appVersion:{}}, recipeControls:{enabled(){}},
    FRONTEND_VERSION:'test', first:(p, keys, fallback) => p[keys[0]] ?? fallback,
    boundedRequest: (controller, timeout, fn) => fn(controller.signal),
    fetch: (url, options) => { assert.equal(url, '/ready'); const d=deferred(); calls.push({...d,signal:options.signal}); return d.promise; },
    responseJson:r=>r.json(),
    applySavedRequestToForm(){},setSelectedMemberships(){},planFromEnvelope:p=>p,
    renderResults(){},window:{localStorage:{setItem(){}},SmakoRecipes:{forgetJob(){}}},
    lastPlanStorageKey:'test',debugMode:false,
  });
  vm.runInContext(`let plannerReady=false,readinessGeneration=0,readinessController=null,frontendBuildId,savedPlanRequest;
    function setPlannerReadiness(value){plannerReady=value;statuses.push(value);}
    ${runtime}\n${apply}`,ctx);
  return {ctx,calls,statuses,run:code=>vm.runInContext(code,ctx)};
}
const answer=(d,ready)=>d.resolve({ok:ready,json:async()=>({status:ready?'ready':'not_ready',features:{}})});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const h=harness();
  const first=h.run('loadPublicRuntimeStatus()'); h.calls[0].reject(new Error('controlled connection loss')); await first;
  assert.deepEqual(h.statuses,[false]);
  h.run('applySavedPlan({plan_id:"saved"},{updateUrl:false})');
  assert.equal(h.calls.length,2,'result delivery must retry a failed readiness probe');
  answer(h.calls[1],true); await flush(); assert.equal(h.statuses.at(-1),true);
  h.run('applySavedPlan({plan_id:"saved"},{updateUrl:false})');
  assert.equal(h.calls.length,2,'ready delivery does not start another probe');
  const stale=h.run('loadPublicRuntimeStatus()');
  const current=h.run('loadPublicRuntimeStatus()');
  assert.equal(h.calls[2].signal.aborted,true);
  answer(h.calls[3],true); await current; answer(h.calls[2],false); await stale;
  assert.equal(h.statuses.at(-1),true,'late 503 must not replace current readiness');
  const blocked=h.run('loadPublicRuntimeStatus()'); answer(h.calls[4],false); await blocked;
  assert.equal(h.statuses.at(-1),false,'a real current 503 remains blocking');
  const old=h.run('loadPublicRuntimeStatus()'); const fresh=h.run('loadPublicRuntimeStatus()');
  answer(h.calls[6],true); await fresh; h.calls[5].reject(new Error('late abort')); await old;
  assert.equal(h.statuses.at(-1),true,'old rejection cannot overwrite new state');
  console.log('PASS: delivery recovery, no extra generation, stale reply/rejection isolation, authoritative 503');
})().catch(error=>{console.error(error);process.exitCode=1;});

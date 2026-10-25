import assert from 'node:assert/strict';
const base=process.env.PREVIEW_ORIGIN||'http://terminal.local:4173';
let count=0;
for(const route of ['/','/guide','/portal','/account','/preview/checkout']){const r=await fetch(base+route);assert.equal(r.status,200,route);count++}
for(const scenario of ['active','canceling','pending','expired','canceled','unavailable']){const r=await fetch(base+'/api/preview/message',{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({scenario,message:'How does memory work?'})});assert.equal(r.status,['active','canceling'].includes(scenario)?200:403,scenario);count++}
assert.equal((await fetch(base+'/api/preview/message',{method:'POST',headers:{Origin:'https://other.invalid','Content-Type':'application/json'},body:JSON.stringify({scenario:'active',message:'hello'})})).status,403);count++;
for(const route of ['/api/interaction','/api/billing/checkout','/api/billing/manage','/api/billing/webhook']){assert.equal((await fetch(base+route,{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({paid:true,subject:'__legacy__',scenario:'active'})})).status,503);count++}
console.log(`${count} HTTP checks passed: pages, access states, cross-origin refusal, production routes fail closed.`);

import assert from 'node:assert/strict';
const base=process.env.PREVIEW_ORIGIN||'http://127.0.0.1:4173';
let count=0;
for(const route of ['/','/guide','/portal','/account','/preview/checkout']){const r=await fetch(base+route);assert.equal(r.status,200,route);if(route==='/portal'){const html=await r.text();assert.doesNotMatch(html,/Conversation preview|Start with a question|Example message/)}count++}
for(const scenario of ['active','canceling','pending','expired','canceled','unavailable']){const r=await fetch(base+'/api/preview/status?scenario='+scenario);assert.equal(r.status,200,scenario);const data=await r.json();assert.equal(data.state,scenario);assert.equal(data.allowed,['active','canceling'].includes(scenario));count++}
assert.equal((await fetch(base+'/api/preview/status?scenario=invented')).status,400);count++;
assert.equal((await fetch(base+'/api/preview/message',{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({scenario:'active',message:'hello'})})).status,404);count++;
for(const route of ['/api/interaction','/api/billing/checkout','/api/billing/manage','/api/billing/webhook']){assert.equal((await fetch(base+route,{method:'POST',headers:{Origin:base,'Content-Type':'application/json'},body:JSON.stringify({paid:true,subject:'__legacy__',scenario:'active'})})).status,503);count++}
console.log(`${count} HTTP checks passed: pages, access states, retired conversation route, production routes fail closed.`);

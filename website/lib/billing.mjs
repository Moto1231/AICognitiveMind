// Integration core, deliberately not connected to public routes in this preview.
// Use a durable transactional store and a provider adapter before enabling it.
// Stripe protocol: https://docs.stripe.com/webhooks#verify-manually
const enc=new TextEncoder();
export async function verifyStripeEvent(raw, signature, secret, now=Math.floor(Date.now()/1000)) {
 if(!secret || typeof raw!=='string' || raw.length>262144 || typeof signature!=='string')throw Error('invalid webhook');
 const parts=signature.split(',').map(x=>x.trim().split('='));
 const timestamps=parts.filter(p=>p[0]==='t');
 if(timestamps.length!==1 || !/^\d+$/.test(timestamps[0][1]))throw Error('invalid timestamp');
 const timestamp=Number(timestamps[0][1]);
 if(!Number.isSafeInteger(timestamp)||Math.abs(now-timestamp)>300)throw Error('stale webhook');
 const signatures=parts.filter(p=>p[0]==='v1'&&/^[a-f0-9]{64}$/.test(p[1])).map(p=>Uint8Array.from(p[1].match(/../g).map(x=>parseInt(x,16))));
 const key=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['verify']);
 let valid=false;
 for(const s of signatures){if(await crypto.subtle.verify('HMAC',key,s,enc.encode(`${timestamp}.${raw}`)))valid=true;}
 if(!valid)throw Error('invalid signature');
 const e=JSON.parse(raw);
 if(typeof e.id!=='string'||!e.id.startsWith('evt_')||typeof e.livemode!=='boolean'||!e.data?.object?.id)throw Error('invalid event');
 return e;
}
export async function applySubscriptionEvent({raw,signature,secret,store,provider,now,live=false}) {
 // Must be verified before any storage mutation or provider lookup.
 const event=await verifyStripeEvent(raw,signature,secret,now);
 if(event.livemode!==live)throw Error('mode mismatch');
 if(!['customer.subscription.created','customer.subscription.updated','customer.subscription.deleted'].includes(event.type))return {ignored:true};
 // Contract: transaction is durable and serializable, includes the event receipt
 // and the entitlement update atomically; a failure leaves no receipt behind.
 return store.transaction(async tx=>{
  if(await tx.hasEvent(event.id))return {duplicate:true};
  // Fetch current authoritative provider state: do not apply stale event snapshots.
  const current=await provider.readSubscription(event.data.object.id);
  if(current.subscriptionId!==event.data.object.id||current.livemode!==live)throw Error('subscription mismatch');
  const binding=await tx.findBinding(current.customerId,current.subscriptionId);
  if(!binding || binding.customerId!==current.customerId || binding.subscriptionId!==current.subscriptionId || !binding.subject || !binding.mindSubject || binding.mindSubject==='__legacy__')throw Error('unmapped account');
  // binding is created only after proof of Axiom account ownership and server-created
  // Checkout. No email matching or customer/subject from browser payloads.
  if(!Number.isFinite(current.paidThrough)||typeof current.paymentConfirmed!=='boolean')throw Error('invalid entitlement');
  await tx.putEntitlement(binding.subject,{...current,subject:binding.subject,mode:'verified'});
  await tx.recordEvent(event.id);
  return {applied:true};
 });
}
export async function authorizeMind({principal,store,now}) {
 const {entitlement}=await import('./access.mjs');
 if(!principal?.subject)return {allowed:false,reason:'unauthenticated'};
 const binding=await store.findBySubject(principal.subject);
 if(!binding?.mindSubject||binding.mindSubject==='__legacy__'||binding.subject!==principal.subject)return {allowed:false,reason:'unlinked'};
 const record=await store.readEntitlement(principal.subject);
 if(record?.customerId!==binding.customerId||record?.subscriptionId!==binding.subscriptionId)return {allowed:false,reason:'unavailable'};
 const result=entitlement(principal,record,now);
 return result.allowed?{...result,mindSubject:binding.mindSubject}:result;
}

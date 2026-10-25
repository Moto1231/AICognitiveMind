// Pure server-side policy. Demo fixtures are never production entitlements.
export function entitlement(principal, record, now=Math.floor(Date.now()/1000)) {
 if (!principal?.subject) return {allowed:false,reason:'unauthenticated'};
 if (!record || record.subject!==principal.subject || !record.customerId || !record.subscriptionId || record.mode!=='verified') return {allowed:false,reason:'unavailable'};
 if (record.status!=='active' || record.paymentConfirmed!==true) return {allowed:false,reason:record.status||'pending'};
 if (!Number.isFinite(record.paidThrough) || record.paidThrough<=now) return {allowed:false,reason:'expired'};
 return {allowed:true,reason:record.cancelAtPeriodEnd?'canceling':'active'};
}
export const sampleStates=['active','canceling','pending','expired','canceled','unavailable'];
export function previewState(state){
 if(!sampleStates.includes(state)) return null;
 const now=Math.floor(Date.now()/1000);
 const record={subject:'sample-only',customerId:'sample-customer',subscriptionId:'sample-subscription',mode:'verified',status:state==='pending'?'incomplete':state==='canceled'?'canceled':'active',paymentConfirmed:state!=='pending',paidThrough:state==='expired'?now-1:now+86400,cancelAtPeriodEnd:state==='canceling'};
 const result=entitlement({subject:'sample-only'},state==='unavailable'?null:record,now);
 const copy={active:['Active · sample','Sample access is available. No real subscription is connected.','Renewal shown for illustration only.'],canceling:['Cancellation scheduled · sample','Sample access remains open through the illustrated paid period.','No future renewal in this sample.'],pending:['Payment pending · sample','Access stays closed while payment confirmation is pending.','No real payment is in progress.'],expired:['Access expired · sample','The illustrated access period has ended. Interaction is closed.','No renewal has been confirmed.'],canceled:['Canceled · sample','The sample subscription has ended. Interaction is closed.','No future renewal in this sample.'],unavailable:['Temporarily unavailable · sample','Access cannot be verified right now. Please try again later.','Subscription status is not assumed.']}[state];
 return {state,title:copy[0],description:copy[1],renewal:copy[2],allowed:result.allowed};
}
export function sampleReply(message){const m=message.toLowerCase();if(m.includes('memor'))return 'Illustrative response: the Memory Steward decides what context to recall and what learning to preserve. Working context, journal experience and curated durable memories serve different roles. This example is not being committed to a Mind.';if(/separate|account|private|isolat/.test(m))return 'Illustrative response: an existing Axiom account selects its own Mind. Subscription access must preserve that account boundary. This sample has no connection to your Mind, memories or Administrator settings.';if(/model|engine|continu/.test(m))return 'Illustrative response: the reasoning engine can change while the persistent Mind retains its identity, memories and history. A supported host still needs to follow the interaction lifecycle and have functioning provider access.';return 'This is a prepared demonstration, not live reasoning. Try a question about memory, a model change or account separation. To interact with your real Mind, open the existing Axiom workspace.';}

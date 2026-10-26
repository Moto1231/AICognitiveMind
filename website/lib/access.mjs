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
 const copy={active:['Active · sample','Sample access is available. No real subscription is connected.','Renewal shown for illustration only.'],canceling:['Cancellation scheduled · sample','Sample access remains open through the illustrated paid period.','No future renewal in this sample.'],pending:['Payment pending · sample','Access stays closed while payment confirmation is pending.','No real payment is in progress.'],expired:['Access expired · sample','The illustrated access period has ended. Subscriber access is closed.','No renewal has been confirmed.'],canceled:['Canceled · sample','The sample subscription has ended. Subscriber access is closed.','No future renewal in this sample.'],unavailable:['Temporarily unavailable · sample','Access cannot be verified right now. Please try again later.','Subscription status is not assumed.']}[state];
 return {state,title:copy[0],description:copy[1],renewal:copy[2],allowed:result.allowed};
}

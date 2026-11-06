// Intentionally fail closed until verified account mapping, durable billing storage,
// provider configuration and production-service entitlement enforcement are integrated.
export async function POST(){return Response.json({message:"Subscriber access is not available yet. No changes were made."},{status:503,headers:{"Cache-Control":"no-store"}})}

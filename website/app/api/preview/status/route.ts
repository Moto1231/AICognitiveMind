import {previewState} from "../../../../lib/access.mjs";
export async function GET(request:Request){const s=previewState(new URL(request.url).searchParams.get('scenario')||'active');return Response.json(s||{message:'Unknown preview state.'},{status:s?200:400,headers:{'Cache-Control':'no-store'}})}

export function parseFrame(frame: string): {type:string;data:any}|null {
  const lines=frame.replace(/\r/g,'').split('\n');
  const type=lines.find(x=>x.startsWith('event:'))?.slice(6).trim();
  const data=lines.filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');
  return type && data ? {type,data:JSON.parse(data)} : null;
}
export async function readStream(response:Response,onEvent:(event:{type:string;data:any})=>void){
  if(!response.body) throw new Error('Streaming indisponível');
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
  try {while(true){const {value,done}=await reader.read();buffer+=decoder.decode(value,{stream:!done});
    let end;while((end=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,end);buffer=buffer.slice(end+2);const event=parseFrame(frame);if(event)onEvent(event);}
    if(done)break;
  }}finally{reader.releaseLock();}
}

import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseFrame,readStream} from '../src/stream.ts';
test('parses JSON and ignores empty heartbeat',()=>{assert.equal(parseFrame(': heartbeat'),null);assert.deepEqual(parseFrame('event: state\ndata: {"revision":2}'),{type:'state',data:{revision:2}});});
test('preserves UTF-8 and frames across arbitrary byte boundaries',async()=>{
 const bytes=new TextEncoder().encode('event: card\ndata: {"body":"Cartão — benefício"}\n\nevent: done\ndata: {"ok":true}\n\n');
 const stream=new ReadableStream({start(c){for(let i=0;i<bytes.length;i+=3)c.enqueue(bytes.slice(i,i+3));c.close();}});
 const events=[];await readStream(new Response(stream),x=>events.push(x));
 assert.equal(events[0].data.body,'Cartão — benefício');assert.equal(events[1].type,'done');
});

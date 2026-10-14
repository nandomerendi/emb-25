export type Role='customer'|'operator';
export interface Turn {role:Role;text:string;expected_intervention:boolean;expected_source:string|null}
export interface Scenario {id:string;name:string;description:string;split:string;turns:Turn[]}
export interface Source {id:string;title:string;body:string;reply:string;question:string;version:string;product:string;subject:string}
export interface Card {id:string;event_id:string;revision:number;kind:string;title:string;body:string;subject:string;why:string;sources:Source[];method:string;grounding:string;active:boolean;expires_at:number;feedback:string|null}
export interface Trace {event_id:string;sequence:number;role:Role;revision:number;decision:{emit:boolean;reason:string;explanation:string;priority:number};stages_ms:Record<string,number>;total_backend_ms:number;first_useful_ms:number|null;usage:{calls_started:number;input_tokens:number|null;output_tokens:number|null};generation_result?:string;generation_requested:boolean;retrieval?:{backend:string;cache_hit:boolean};status:string}
export interface Session {id:string;sequence:number;state:any;cards:Card[];audit:Trace[];config:any;presentations:any[]}

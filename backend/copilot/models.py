from typing import Literal
from pydantic import BaseModel, Field

class Config(BaseModel):
    approach: Literal['A', 'B', 'C'] = 'C'
    generation: Literal['demo', 'openai'] = 'demo'
    retrieval: Literal['bm25', 'hybrid', 'dense'] = 'hybrid'
    posture: Literal['proactive', 'reactive'] = 'proactive'
    min_confidence: float = Field(.7, ge=0, le=1)
    cooldown_seconds: float = Field(8, ge=0, le=120)
    dedup_seconds: float = Field(90, ge=0, le=600)
    expiry_seconds: float = Field(45, ge=1, le=300)
    operator_handling_seconds: float = Field(25, ge=0, le=120)
    use_state: bool = True
    use_suppression: bool = True

class Message(BaseModel):
    event_id: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    sequence: int = Field(ge=1)
    role: Literal['customer', 'operator']
    text: str = Field(min_length=1, max_length=3000)
    request_assist: bool = False

class Feedback(BaseModel):
    action: Literal['accepted', 'dismissed', 'helpful', 'not_helpful']
    reason: str = Field('', max_length=300)

class Presentation(BaseModel):
    event_id: str
    card_id: str
    elapsed_ms: float = Field(ge=0, le=600000)

class Review(BaseModel):
    relevant: bool
    grounded: bool
    useful: bool
    note: str = Field('', max_length=500)

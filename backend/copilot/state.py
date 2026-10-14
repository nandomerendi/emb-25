from dataclasses import dataclass, field, asdict
from .signals import normalize
import re

@dataclass
class InteractionState:
    revision: int = 0
    product: str | None = None
    subject: str | None = None
    intent: str = 'indefinida'
    journey: str = 'investigacao'
    resolved: bool = False
    complaint_open: bool = False
    pending_question: str | None = None
    operator_subject: str | None = None
    operator_at: float = -1e9
    recent: list = field(default_factory=list)
    sentiment_history: list = field(default_factory=list)
    signal_evidence: list = field(default_factory=list)

    def update(self, msg, sig, now, use_state=True):
        prior_subject = self.subject
        self.revision += 1
        self.recent = (self.recent + [{'role':msg.role,'text':msg.text,'event_id':msg.event_id}])[-8:]
        if not use_state:
            self.product = self.subject = self.operator_subject = None
            self.resolved = self.complaint_open = False
            self.pending_question = None
        if msg.role == 'operator' and not msg.request_assist:
            t = normalize(msg.text)
            if self.subject is None and sig.get('subject'):
                self.subject=sig['subject']
                self.product=sig.get('product')
            # A promise is handling, never proof of resolution. A greeting is neither.
            handling = bool(re.search(r'verificar|consultar|orient|beneficio|anuidade|aplicativo|comprovante|qual|quais|pode me|entendo', t))
            if handling and (sig.get('subject') or self.subject):
                self.operator_subject = sig.get('subject') or self.subject
                self.operator_at = now
            if '?' in msg.text:
                self.pending_question = msg.text
            return False
        explicit_new = sig.get('subject') and sig['subject'] != self.subject
        product_changed = sig.get('product') and self.product and sig['product'] != self.product
        if explicit_new or product_changed:
            self.subject = sig.get('subject')
            self.product = sig.get('product') or self.product
            self.resolved = False
            self.pending_question = None
            if self.operator_subject != self.subject:
                self.operator_subject = None
        self.product = sig.get('product') or self.product
        self.subject = sig.get('subject') or self.subject
        if sig['intent'] != 'indefinida': self.intent = sig['intent']
        self.journey = sig['journey']
        if sig['resolved']:
            self.resolved = True
            self.complaint_open = False
            self.journey = 'resolucao'
            self.pending_question = None
        elif sig['question'] or sig['cancel_risk'] or sig.get('objection') or sig['sentiment'] == 'negativo':
            self.resolved = False
        if sig['sentiment'] == 'negativo': self.complaint_open = True
        if sig['sentiment'] != 'nao_determinado':
            self.sentiment_history = (self.sentiment_history + [{'value':sig['sentiment'],'revision':self.revision,
                                                               'basis':'heuristica_textual'}])[-6:]
        self.signal_evidence = sig['evidence']
        return self.subject != prior_subject

    def public(self):
        result = asdict(self)
        result.pop('operator_at')
        result['sentiment_trend'] = 'evidencia_insuficiente'
        h = self.sentiment_history
        if len(h) >= 2:
            result['sentiment_trend'] = 'estavel' if h[-1]['value'] == h[-2]['value'] else ('melhorando' if h[-1]['value'] == 'positivo' else 'piorando')
        return result

"""Interruption policy. Numeric confidence is a tunable heuristic, never a probability."""
from dataclasses import dataclass
from .signals import normalize

@dataclass
class Decision:
    emit: bool
    reason: str
    kind: str = 'knowledge'
    priority: int = 30
    fingerprint: str = ''
    generate: bool = False
    expected_value: str = ''

def decide(msg,sig,state,config,history,now):
    if sig['injection']: return Decision(False,'unsafe_input')
    if config.posture == 'reactive' and not msg.request_assist: return Decision(False,'reactive_waiting_request')
    if msg.role == 'operator' and not msg.request_assist: return Decision(False,'operator_turn')
    subject = state.subject if config.use_state else sig.get('subject')
    product = state.product if config.use_state else sig.get('product')
    if config.approach != 'A' and (sig['resolved'] or (config.use_state and state.resolved)):
        return Decision(False,'resolved')
    if subject == 'seguranca': kind,priority='alert',100
    elif sig['cancel_risk']: kind,priority='alert',85
    elif sig.get('objection') or subject in ('reserva','insatisfacao'): kind,priority='guidance',60
    elif not subject: kind,priority='guidance',40
    elif any(w in normalize(msg.text) for w in ('artigo','regulamento','documento')): kind,priority='knowledge',30
    else: kind,priority='reply',50
    fingerprint = f'{product}:{subject}:{kind}:{sig["intent"]}'
    if config.approach != 'A':
        if sig['confidence']<config.min_confidence: return Decision(False,'low_confidence')
        if sig['intent']=='indefinida' and subject!='seguranca' and not msg.request_assist:
            return Decision(False,'context_only')
    if config.approach == 'C' and config.use_suppression and config.posture == 'proactive':
        if subject=='reserva' and state.complaint_open:
            return Decision(False,'commercial_during_complaint')
        for h in reversed(history):
            if h['fingerprint']==fingerprint and now-h['at']<config.dedup_seconds:
                return Decision(False,'dismissed' if h.get('dismissed') else 'duplicate')
        urgent = priority>=85
        if state.operator_subject==subject and now-state.operator_at<config.operator_handling_seconds:
            # Escalation can override a previous routine response, not an equivalent safety response.
            if not urgent or any(h['priority']>=priority and h['subject']==subject for h in history):
                return Decision(False,'operator_handling')
        recent = history[-1] if history else None
        if recent and now-recent['at']<config.cooldown_seconds and recent['subject']==subject and priority<=recent['priority']:
            return Decision(False,'cooldown')
    # A/B always request generation for candidate turns; C uses it for synthesis only.
    generate = config.approach in ('A','B') or (kind=='reply' and sig['question'])
    reason = 'requested' if msg.request_assist else 'eligible_opportunity'
    value = {'alert':'Evitar um próximo passo inadequado','guidance':'Ajudar a investigar antes de oferecer',
             'reply':'Poupar a busca e a redação','knowledge':'Disponibilizar uma fonte confiável'}[kind]
    return Decision(True,reason,kind,priority,fingerprint,generate,value)

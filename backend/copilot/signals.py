"""Small, inspectable lexical baseline. No claim of general NLU or calibrated confidence."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = json.loads((ROOT / 'data/ontology.json').read_text())

def normalize(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))

def redact(text: str) -> str:
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '[EMAIL]', text)
    text = re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', '[CPF]', text)
    return re.sub(r'(?<!\w)(?:\+?\d[\s().-]?){10,19}(?!\w)', '[NUMERO]', text)

def detect(text: str) -> dict:
    t = normalize(text)
    evidence, values = [], {}
    for dim, options in ONTOLOGY['dimensions'].items():
        for value, patterns in options.items():
            for pattern in patterns:
                m = re.search(pattern, t)
                if m:
                    # Simple local negation; evaluated as a known limited baseline.
                    prefix = t[max(0, m.start()-12):m.start()]
                    if dim == 'sentiment' and re.search(r'nao (estou |sou |estou tao )?$', prefix):
                        continue
                    values[dim] = value
                    evidence.append({'dimension': dim, 'value': value, 'kind':'observed',
                                     'quote':text[m.start():m.end()], 'method':'regex', 'score':.9})
                    break
    cancel = bool(re.search(r'cancelar|cancelamento|encerrar (o |meu )?cartao', t))
    if re.search(r'nao (quero |vou |pretendo |desejo )?(cancelar|encerrar)|sem cancelar', t):
        cancel = False
    soft_cancel = bool(re.search(r'nao sei se vale a pena continuar|pensando em sair|nao quero continuar', t))
    question = '?' in t or bool(re.search(r'\b(como|quais|qual|onde|quando|quero saber|me explique)\b', t))
    resolved = bool(re.search(r'\bresolvido\b|entendi[, ]+obrigad|era isso|ajudou bastante', t))
    if re.search(r'nao (foi |esta |ficou )?resolvido|ainda nao', t): resolved = False
    injection = bool(re.search(r'ignore (as |todas |suas )?(instrucoes|regras)|system prompt|revele.*(prompt|segredo)|isencao garantida|desconto garantido', t))
    if cancel: intent = 'cancelamento'
    elif soft_cancel: intent = 'avaliacao'
    elif values.get('subject') == 'reserva': intent = 'interesse'
    elif values.get('objection'): intent = 'avaliacao'
    elif values.get('sentiment') == 'negativo': intent = 'reclamacao'
    elif question: intent = 'duvida'
    else: intent = 'indefinida'
    if cancel and not values.get('subject'): values['subject'] = 'cancelamento'
    if values.get('subject') in ('anuidade','beneficios','cancelamento'):
        values.setdefault('product','cartao')
    if values.get('subject') in ('reserva','tarifa'): values.setdefault('product','conta')
    if intent == 'reclamacao' and not values.get('subject'): values['subject'] = 'insatisfacao'
    if soft_cancel or intent != 'indefinida':
        evidence.append({'dimension':'intent','value':intent,'kind':'inferred',
                         'quote':text[:200], 'method':'lexical_heuristic', 'score':.82 if soft_cancel else .85})
    score = .9 if values.get('subject') else (.72 if question or cancel else .35)
    return {**values, 'intent':intent, 'journey':'consideracao_permanencia' if intent in ('avaliacao','cancelamento') else 'investigacao',
            'cancel_risk': cancel or soft_cancel, 'explicit_cancel': cancel, 'question':question,
            'resolved':resolved, 'injection':injection, 'confidence':score, 'evidence':evidence,
            'sentiment':values.get('sentiment','nao_determinado')}

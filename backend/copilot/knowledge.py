"""BM25 + character TF-IDF RRF; optional local semantic encoder, explicitly labelled."""
from collections import Counter, OrderedDict
from math import log
import json, os, time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from .signals import ROOT, normalize
import re

STOP = set('a o as os de da do das dos e eu me meu minha um uma que qual quais como por para no na em muito estou esse essa isso'.split())
def tokens(t): return [x for x in re.findall(r'\w+', normalize(t)) if x not in STOP]

class Knowledge:
    def __init__(self):
        self.docs = [d for d in json.loads((ROOT/'data/knowledge.json').read_text()) if d['approved']]
        self.version = '|'.join(d['id']+d['version'] for d in self.docs)
        self.texts = [normalize(' '.join([d['title'], d['body'], *d['aliases']])) for d in self.docs]
        self.counts = [Counter(tokens(t)) for t in self.texts]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.avg = sum(self.lengths)/len(self.lengths)
        self.df = Counter(w for c in self.counts for w in c)
        self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5))
        self.matrix = self.vectorizer.fit_transform(self.texts)
        self.encoder = None
        self.vectors = None
        path = os.getenv('EMBEDDING_MODEL_PATH')
        if path:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer(path, local_files_only=True)
            self.vectors = self.encoder.encode(self.texts, normalize_embeddings=True)
        self.cache = OrderedDict()

    def search(self, query, subject=None, product=None, mode='hybrid', audience='operador'):
        key = (normalize(query),subject,product,mode,audience,self.version)
        now = time.monotonic()
        if key in self.cache:
            at, found = self.cache[key]
            if now-at < 300:
                self.cache.move_to_end(key)
                return found, {'cache_hit':True,'backend':self.backend(mode),'candidate_count':len(self.docs)}
        if mode == 'dense' and self.encoder is None:
            raise ValueError('Busca semântica exige EMBEDDING_MODEL_PATH local. O híbrido padrão é lexical + morfológico.')
        q = tokens(query)
        lexical = []
        n = len(self.docs)
        for c, length in zip(self.counts,self.lengths):
            score = 0.
            for w in q:
                df, tf = self.df.get(w,0), c.get(w,0)
                score += log(1+(n-df+.5)/(df+.5))*tf*2.5/(tf+1.5*(.25+.75*length/self.avg))
            lexical.append(score)
        if mode == 'bm25':
            semantic = [0.0]*n
        elif self.encoder:
            semantic = (self.vectors @ self.encoder.encode([normalize(query)],normalize_embeddings=True)[0]).tolist()
        else:
            semantic = (self.matrix @ self.vectorizer.transform([normalize(query)]).T).toarray().ravel().tolist()
        ranks = []
        for scores in (lexical, semantic):
            order = sorted(range(n),key=lambda i:scores[i],reverse=True)
            ranks.append({i:1/(60+r+1) if scores[i]>0 else 0 for r,i in enumerate(order)})
        candidates = []
        for i,d in enumerate(self.docs):
            if d['audience'] != audience: continue
            if product and d['product'] not in (product,'geral'): continue
            # Explicit scope is a hard filter, not an uncalibrated score bonus.
            if subject and d['subject'] != subject: continue
            raw = lexical[i] if mode=='bm25' else semantic[i] if mode=='dense' else ranks[0][i]+ranks[1][i]
            if raw > 0:
                candidates.append({**d,'retrieval_score':round(raw,5),'bm25':round(lexical[i],4),
                                   'vector_similarity':round(semantic[i],4)})
        found = sorted(candidates,key=lambda d:d['retrieval_score'],reverse=True)[:3]
        self.cache[key] = (now, found)
        while len(self.cache)>256: self.cache.popitem(last=False)
        return found, {'cache_hit':False,'backend':self.backend(mode),'candidate_count':n}

    def backend(self, mode):
        if mode == 'bm25': return 'bm25'
        return 'bm25+semantic_rrf' if self.encoder and mode=='hybrid' else 'semantic' if self.encoder else 'bm25+char_tfidf_rrf'

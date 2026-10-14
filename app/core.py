"""Dependency-free ranking and evidence validation primitives."""
import math
import re
from collections import Counter


def tokens(text):
    return re.findall(r"\w+", text.lower())


def chunks(text, size=160, overlap=30):
    words = text.split()
    result = []
    for start in range(0, len(words), size - overlap):
        result.append(' '.join(words[start:start + size]))
        if start + size >= len(words):
            break
    return result


def bm25(query, documents):
    corpus = [tokens(d) for d in documents]
    average = sum(map(len, corpus)) / max(len(corpus), 1) or 1
    df = Counter(t for doc in corpus for t in set(doc))
    scores = []
    for doc in corpus:
        counts = Counter(doc)
        score = 0.0
        for t in set(tokens(query)):
            frequency = counts[t]
            idf = math.log(1 + (len(corpus) - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * len(doc) / average))
        scores.append(score)
    return scores


def fuse(*rankings):
    scores = Counter()
    for ranking in rankings:
        for rank, key in enumerate(ranking, 1):
            scores[key] += 1 / (60 + rank)
    return sorted(scores, key=lambda key: (-scores[key], key))


def validate_claims(payload, sources):
    """Verify provenance and verbatim quotes, not semantic entailment."""
    valid = []
    lookup = {s['id']: s for s in sources}
    for claim in payload.get('claims', [])[:8]:
        if not isinstance(claim, dict):
            continue
        source_id, quote, statement = claim.get('source_id'), claim.get('quote'), claim.get('statement')
        if not all(isinstance(x, str) for x in (source_id, quote, statement)):
            continue
        if source_id not in lookup or len(quote.strip()) < 15 or not statement.strip():
            continue
        if ' '.join(quote.split()) not in ' '.join(lookup[source_id]['text'].split()):
            continue
        valid.append({'statement': statement, 'quote': quote, 'source_id': source_id})
    return valid

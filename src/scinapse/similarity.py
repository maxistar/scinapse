"""Abstract/title similarity: Token Factory embeddings if configured, TF-IDF fallback.

Ported from the prototype notebook's ``build_semantic`` (cell ``702c1c51``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class SimResult:
    matrix: np.ndarray          # cosine similarities, papers in `ids` order
    ids: list[str]              # s2 paper ids (state.papers order)
    method_version: str         # "embeddings:<model>" | "tfidf-cosine-v1"
    threshold: float            # raw-cosine threshold used for similar_to edges


def build_similarity(state, tf_client=None, embed_model: str = "") -> SimResult:
    ids = list(state.papers)
    docs = [f"{state.papers[p].title}. {state.papers[p].abstract}".strip()[:4000] for p in ids]
    used, M = "tfidf", None
    if tf_client is not None and embed_model:
        try:
            vecs = []
            for i in range(0, len(docs), 32):
                resp = tf_client.embeddings.create(model=embed_model, input=docs[i:i + 32])
                vecs.extend(d.embedding for d in resp.data)
            M = cosine_similarity(np.asarray(vecs, dtype=float))
            used = f"embeddings:{embed_model}"
        except Exception as e:
            print(f"    embeddings unavailable ({e}) -> TF-IDF fallback", flush=True)
            M = None
    if M is None:
        tfv = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
        M = cosine_similarity(tfv.fit_transform(docs))
        used = "tfidf-cosine-v1"
    threshold = 0.55 if used.startswith("embeddings") else 0.15  # TF-IDF cosines run lower
    n_abs = sum(1 for p in ids if state.papers[p].abstract)
    # seed similarity per paper (internal ordering signal, ported)
    seed_idx = [i for i, p in enumerate(ids) if state.papers[p].is_seed]
    if seed_idx:
        for i, pid in enumerate(ids):
            rec = state.papers[pid]
            if not rec.is_seed:
                rec.sem = round(float(max(M[i][j] for j in seed_idx)), 3)
    print(f"    similarity via {used} (threshold {threshold}); "
          f"{n_abs}/{len(ids)} papers have abstracts", flush=True)
    return SimResult(matrix=M, ids=ids, method_version=used, threshold=threshold)

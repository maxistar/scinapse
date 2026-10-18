"""Token Factory (Nebius) assessor — ONE JSON-mode chat call per node.

Produces the judgment fields the APIs cannot: the 4 relevance rubric
dimensions, methods extraction, a verbatim supporting quote, and the
abstract-based research-quality dimensions. Reliability ladder: JSON mode ->
one repair retry -> first-brace extraction -> honest degradation (null
dimensions, ``insufficient_evidence``). Responses are disk-cached, so reruns
are free and deterministic per model.
"""

from __future__ import annotations

import json
import re

from . import warnings as W
from .config import BuildConfig, nebius_api_key
from .discovery import GraphState, PaperRec, short_title
from .httpjson import Http
from .textutil import first_sentence, normalized_contains

TOKEN_FACTORY_BASE = "https://api.tokenfactory.nebius.com/v1/"

DIMENSIONS = ("research_question_alignment", "disease_setting_alignment",
              "method_alignment", "outcome_alignment")
RA_DIMS = ("methodological_rigor", "evidence_strength", "transparency")

PROMPT = """Research question: {question}

Paper: {title} ({year}, {journal})
Abstract: {abstract}

Connections found automatically from citation/author/similarity analysis:
{evidence}

You are scoring how relevant this paper is to the research question, using ONLY
the information above. Return ONLY a JSON object with exactly these keys:
- "methods": list of up to 5 short method/technique names used in the paper, taken from the abstract ([] if none are stated)
- "relevance_dimensions": object with these four keys, each a number 0.0-1.0 (or null if it cannot be judged from the abstract):
  - "research_question_alignment": how directly the paper addresses the research question
  - "disease_setting_alignment": how well the disease/model system matches the question's setting
  - "method_alignment": how well the methods match the methods implied by the question
  - "outcome_alignment": how well the measured outcomes match the question's outcomes of interest
- "relevance_reason": at most two sentences explaining the scores
- "uncertainties": list of short strings naming what remains unknown
- "supporting_quote": ONE sentence copied VERBATIM from the abstract that best supports the scores (empty string if there is no abstract)
- "research_assessment": object with keys "methodological_rigor", "evidence_strength", "transparency", each {{"assessment": one of "not_assessed"|"unknown"|"partial_evidence", "reason": one sentence}} — judge only what an abstract can support
- "assessment_summary": at most two sentences summarizing research quality signals visible in the abstract

No markdown, no commentary — only the JSON object."""


def make_client():
    key = nebius_api_key()
    if not key:
        return None
    from openai import OpenAI  # deferred: CLI check runs without the dep installed
    return OpenAI(base_url=TOKEN_FACTORY_BASE, api_key=key)


def extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        pass
    start, depth, in_str = text.find("{"), 0, False
    if start == -1:
        return {}
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if c == "\\":
                continue
            in_str = c != '"' if text[i - 1] != "\\" else in_str
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start:i + 1])
                    return obj if isinstance(obj, dict) else {}
                except json.JSONDecodeError:
                    return {}
    return {}


def _clamp(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return round(min(max(f, 0.0), 1.0), 2)


def _chat(client, model: str, prompt: str, *, repair: str | None = None) -> str:
    """Escalating ladder: JSON mode preferred, budget doubles on truncation.

    Reasoning models spend tokens before visible content, so a length-truncated
    reply is retried with a larger budget rather than returned half-finished.
    """
    messages = [{"role": "user", "content": prompt if repair is None else
                 prompt + "\n\nYour previous reply was not valid JSON: " + repair
                 + "\nReturn ONLY the corrected JSON object."}]
    for max_tokens in (2500, 6000):
        for extra in ({"response_format": {"type": "json_object"}}, {}):
            try:
                r = client.chat.completions.create(
                    model=model, temperature=0, max_tokens=max_tokens,
                    messages=messages, **extra)
                choice = r.choices[0]
                text = (choice.message.content or "").strip()
                if text and choice.finish_reason != "length":
                    return text
            except Exception:
                continue
    return ""


def _normalized_contains(quote: str, text: str) -> bool:
    return normalized_contains(quote, text)


def assess_one(cfg: BuildConfig, client, http: Http, rec: PaperRec) -> dict:
    prompt = PROMPT.format(
        question=cfg.question,
        title=rec.title,
        year=rec.year or "unknown year",
        journal=rec.source_name or rec.venue or "unknown venue",
        abstract=rec.abstract or "NOT AVAILABLE",
        evidence=" | ".join(rec.evidence_lines) or "none",
    )
    cache_key = http.cache_path("llm-assess", cfg.chat_model, prompt, suffix=".txt")
    raw = None
    if cache_key.exists():
        raw = cache_key.read_text(encoding="utf-8")
    else:
        try:
            raw = _chat(client, cfg.chat_model, prompt)
            if not raw.strip():
                return {"error": "llm returned an empty reply (reasoning budget exhausted?)"}
            if not extract_json(raw):
                raw = _chat(client, cfg.chat_model, prompt, repair=raw[:400])
            cache_key.write_text(raw, encoding="utf-8")
        except Exception as e:
            return {"error": f"llm call failed: {e}"}
    data = extract_json(raw)
    if not data:
        return {"error": "llm reply was not valid JSON"}

    dims_raw = data.get("relevance_dimensions") or {}
    dimensions = {k: _clamp(dims_raw.get(k)) for k in DIMENSIONS}

    ra_raw = data.get("research_assessment") or {}
    research = {}
    for name in RA_DIMS:
        d = ra_raw.get(name) or {}
        assessment = d.get("assessment") if isinstance(d, dict) else None
        if assessment not in ("not_assessed", "unknown", "partial_evidence"):
            assessment = "not_assessed"
        research[name] = {"assessment": assessment,
                          "reason": (d.get("reason") if isinstance(d, dict) else None)
                          or "Not assessed from the available information."}

    methods = [str(m)[:80] for m in (data.get("methods") or []) if str(m).strip()][:5]

    quote = str(data.get("supporting_quote") or "").strip()
    if quote and not _normalized_contains(quote, rec.abstract):
        quote = first_sentence(rec.abstract) if rec.abstract else ""
        rec_llm_warning = W.EVIDENCE_QUOTE_ADJUSTED
    else:
        rec_llm_warning = None

    return {
        "methods": methods,
        "dimensions": dimensions,
        "reason": str(data.get("relevance_reason") or "").strip(),
        "uncertainties": [str(u)[:300] for u in (data.get("uncertainties") or [])][:4],
        "quote": quote or None,
        "research_assessment": research,
        "summary": str(data.get("assessment_summary") or "").strip(),
        "_quote_warning": rec_llm_warning,
    }


def assess_all(state: GraphState, client, http: Http) -> None:
    if client is None:
        state.warnings.add(W.LLM_UNAVAILABLE)
        print("    Token Factory: off -> template assessments (relevance dimensions null)",
              flush=True)
        return
    cfg = state.cfg
    seeds = [r for r in state.papers.values() if r.is_seed]
    rest = sorted((r for r in state.papers.values() if not r.is_seed),
                  key=lambda r: (-(r.composite or 0), r.s2_id))
    targets = (seeds + rest)[:cfg.llm_limit]
    n_ok = 0
    for rec in targets:
        result = assess_one(cfg, client, http, rec)
        warning = result.pop("_quote_warning", None)
        if "error" in result:
            state.warnings.add(W.LLM_ASSESSMENT_FAILED, node_id=rec.s2_id,
                               message=result["error"])
            print(f"    ! assess {short_title(rec.title, 50)}: {result['error']}", flush=True)
            continue
        if warning:
            state.warnings.add(warning, node_id=rec.s2_id)
        rec.llm = result
        n_ok += 1
    print(f"    Token Factory: assessed {n_ok}/{len(targets)} nodes via {cfg.chat_model} (cached)",
          flush=True)
    # nodes beyond the limit or failed: llm stays None -> template path

# -*- coding: utf-8 -*-
"""Paper-profile LiveSearchVQA construction (open-ended v2/v3 pipeline).

The implementation keeps the paper's item-level guarantees while moving
rejections upstream:

L0  evidence-first generation + same-call closed-book self-check;
L1  independent image/article/question alignment gate and one cheap CB sample;
L2  three-model, multi-sample CB/OR panel with logical early stopping;
L3  deduplication and hard English/quantitative composition constraints.

The default certification profile is 3 models x 4 samples.  A lower sample
count can be selected only for debugging with ``LSVQA_CERT_SAMPLES``; the
chosen profile is recorded in every item and in the build statistics.
"""
import argparse
import difflib
import json
import math
import os
import random
import re
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ark_api  # noqa: E402
import qwen_api  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")

ANSWER_TYPES = {"entity", "numeric", "temporal", "location", "outcome"}
QUANT_TYPES = {"numeric", "temporal"}
CATEGORY_MAP = {
    "politics": "politics", "world": "politics", "important": "politics",
    "business": "business", "finance": "business",
    "sports": "sports", "football": "sports",
    "tech": "scitech", "technology": "scitech", "ai": "scitech",
    "science": "scitech", "space": "scitech",
    "health": "health", "environment": "environment",
    "entertainment": "culture", "movies": "culture", "culture": "culture",
    "general": "regional", "society": "regional", "regional": "regional",
    "education": "regional", "china": "regional", "military": "politics",
}

FRESH_HOURS = int(os.environ.get("LSVQA_FRESH_HOURS", "46"))
FUTURE_TOLERANCE_HOURS = 6
CERT_SAMPLES = max(1, int(os.environ.get("LSVQA_CERT_SAMPLES", "4")))
TARGET_ENGLISH_RATIO = float(os.environ.get("LSVQA_ENGLISH_RATIO", "0.85"))
TARGET_QUANT_RATIO = float(os.environ.get("LSVQA_QUANT_RATIO", "0.65"))
BUILD_DATE = os.environ.get("LSVQA_BUILD_DATE", "").strip() or \
    time.strftime("%Y-%m-%d")
QUESTION_SIM_THRESHOLD = 0.76
MATCH_SCORE_MIN = 3

PANEL = [
    {"id": "qwen3.5-flash", "provider": "qwen",
     "model": qwen_api.FAST_VISION_MODEL},
    {"id": "qwen3-vl-plus", "provider": "qwen",
     "model": qwen_api.VISION_MODEL},
    {"id": "doubao-seed-2.0-pro", "provider": "ark",
     "model": ark_api.MODEL},
]

GEN_PROMPT = r"""You construct ONE high-quality visual question answering item
for a benchmark of WEB-SEARCH agents. The article is less than 48 hours old.

ARTICLE METADATA
headline: {title}
source: {source}
source language: {language}
category: {category}
published: {pub_date}

ARTICLE BODY
<<<ARTICLE>>>
{text}
<<<END ARTICLE>>>

Follow this evidence-first procedure inside this same response:
1. Inspect the image and describe the concrete visible anchor (person, team,
   product, spacecraft, venue, ceremony, protest, match, chart, etc.). Reject
   logos, stock art, generic scenery, unrelated thumbnails, and images whose
   connection to this article/event is weak. Classify visual_anchor_type as
   event_scene, person, object, venue, or document.
2. BEFORE writing the question, locate one minimal VERBATIM sentence in the
   article containing the CENTRAL NEW FACT that triggered this article. Strongly
   prefer numbers:
   score, amount, percentage, count, date/time, vote, price, distance, ranking,
   capacity, measurement, or newly reported change. Copy the sentence exactly.
   Do NOT use historical background, biography, a previous match/launch, an old
   photo-caption fact, or a stable fact merely mentioned in a fresh article.
   The fact must be newly occurred, newly announced, or a newly reported result.
3. Write an English question whose referent can only be resolved from the
   image, but whose answer cannot be read from the image. The question must
   explicitly ask about the pictured EVENT: when/where it occurred, what
   quantified outcome was reported, or what newly announced result followed.
   Match the wording to what is actually visible: use "the event shown" only
   for a real event scene; use "the pictured person/team/product/vehicle" for a
   portrait or object. Never pretend a portrait or product shot depicts an event.
   Do not name the visually identifying entity in the question.
4. Never ask "what is the person doing", "who is shown", "what does the image
   show", or any image-only recognition question. Never ask stable background
   knowledge. The item must reward identifying the image and then searching the
   live web.
5. Answer in English with one short phrase (<= 8 tokens). The gold answer must
   be the shortest EXACT SUBSTRING of the evidence sentence that answers the
   question (preserve its number, unit, date, and wording). Set answer_type to
   numeric, temporal, location, outcome, or entity; prefer numeric/temporal.
6. SAME-CALL SELF-CHECK: without using the article sentence, try to answer from
   the image and old world knowledge. Put that attempt in closed_book_self_answer
   (exactly UNKNOWN if not confidently answerable). Mark requires_web_search and
   image_article_match truthfully.

Return one strict JSON object with exactly these fields:
{{
  "image_summary": "...",
  "visual_anchor": "...",
  "visual_anchor_type": "event_scene|person|object|venue|document",
  "event_fact": "...",
  "evidence": "exact verbatim article sentence",
  "question": "...",
  "answer": "...",
  "answer_type": "numeric|temporal|location|outcome|entity",
  "closed_book_self_answer": "UNKNOWN or short answer",
  "freshness_relation": "current_event|new_announcement|new_result",
  "requires_web_search": true,
  "image_article_match": true,
  "quality_rationale": "one concise sentence"
}}
If any condition fails, return {{"reject_reason": "..."}} instead."""

MATCH_PROMPT = r"""Independently audit a proposed live-news VQA item against
the attached image. Do not answer the question.

Article title: {title}
Article source: {source} ({language})
Article published: {pub_date}
Proposed question: {question}
Gold answer: {answer}
Verbatim evidence: {evidence}

Score each property from 0 (fails) to 4 (strong):
- image_article_match: the image plausibly depicts the same named entity or
  event as the article, not a generic/unrelated illustration;
- question_image_grounding: the image is genuinely needed to resolve the
  referent; removing it makes the question under-identified. IMPORTANT: do
  NOT penalize this score because the requested answer comes from the article
  rather than pixels—that is the intended benchmark design. Score 4 when the
  image supplies the identity of a person/product/team/event omitted from the
  question. Score 0 when the question already names the unique target/event
  and the image is merely decorative;
- event_specificity: the question asks an explicit when/where/quantified
  outcome/new result about the pictured event, not what is visibly happening;
- search_necessity: the answer is fresh external information not obtainable
  from pixels or stable background knowledge.
- fresh_fact_centrality: the evidence is a central newly occurred/announced/
  reported fact in this fresh article, NOT biography, historical background,
  an earlier match/launch, or a photo-caption detail;
- question_clarity: the English question is natural, specific, and unambiguous.

Also verify visual_claim_supported: if the image is a portrait/product/object,
the question must say "pictured person/product/object", not "the event shown".
Treat an article-author headshot, outlet logo, unrelated victory photo, generic
stock illustration, or decorative image as an image_article_match failure even
if the question can be awkwardly rewritten around it. The pictured referent must
be a genuine subject of the newly reported fact.

Return strict JSON only:
{{"image_article_match": 0, "question_image_grounding": 0,
  "event_specificity": 0, "search_necessity": 0,
  "fresh_fact_centrality": 0, "question_clarity": 0,
  "explicit_event_question": true, "image_only_answerable": false,
  "visual_claim_supported": true,
  "audit_note": "..."}}"""

GROUNDING_PROMPT = r"""Audit whether an image is NECESSARY to resolve the
referent of a proposed web-search VQA question. This is a logic task, not an
image-recognition task.

Question: {question}
What the image depicts: {image_summary}
Proposed visual anchor: {visual_anchor}

The answer is intentionally NOT visible in the image; do not penalize that.
Return image_resolves_omitted_subject=true exactly when removing the image
leaves a key person/product/team/vehicle/venue/event unnamed or ambiguous.
Also return omitted_subject_is_answer_target=true only when that omitted subject
is necessary to formulate a unique search for the requested answer. Merely
mentioning a pictured official while asking about an already named company,
bill, or event is decorative and must be false.

Examples:
- "What position did the pictured driver finish?" with no driver name: true;
  the image supplies the driver identity, even if a race is named.
- "What month is the race at the venue shown?" with no venue name: true.
- "How much did Disney stock fall, according to the pictured Disney CEO?":
  both fields false; Disney is already named and is the answer target.
- A named bill/film/company plus a decorative pictured official: false.

Return strict JSON only:
{{"image_resolves_omitted_subject": true,
  "omitted_subject_is_answer_target": true,
  "omitted_subject": "...", "grounding_reason": "<= 25 words"}}"""

CB_PROMPT = """Answer the question using only the attached image and your
pre-existing knowledge. You have no web search and no article. Return only a
short answer. If the event-specific answer is not known with high confidence,
return exactly UNKNOWN. Do not guess.\nQuestion: {question}"""

OR_PROMPT = """Use ONLY the verbatim evidence and attached image to answer the
question. Return only a short English answer, with no explanation.
Article title: {title}
Evidence: {evidence}
Question: {question}"""

JUDGE_PROMPT = """Decide whether the prediction is semantically equivalent to
the gold answer for this exact question. Check number, unit, scale, date, entity,
and location. A bare number is NOT equivalent when the gold answer's unit or
million/billion scale is necessary. Output exactly CORRECT or INCORRECT.
Question: {question}
Gold answer: {gold}
Prediction: {pred}"""

_print_lock = threading.Lock()
_stats_lock = threading.Lock()
_PUNCT_TABLE = str.maketrans("", "", string.punctuation + "“”‘’、，。")
_ARTICLES_RE = re.compile(r"\b(the|a|an)\b", re.I)
_VISUAL_REF_RE = re.compile(
    r"\b(pictured|shown|in (?:this|the) image|visible in|depicted|photographed)\b",
    re.I,
)
_EVENT_CUE_RE = re.compile(
    r"\b(event|match|game|race|launch|mission|meeting|summit|ceremony|"
    r"announcement|release|protest|trial|vote|election|deal|transaction|"
    r"incident|conference|tournament|performance|project|reported|reporting|"
    r"recorded|won|lost|scored|raised|cost|revenue|price|amount|how many|"
    r"how much|what date|what time|where did|percentage|percent|debut|"
    r"grand prix|season|series|championship|lawsuit|bill|sale|discount|"
    r"startup|program|probe|contract|episode|film|movie|album|tour|concert|"
    r"flood|storm|earthquake|wildfire|closure|layoff|funding|study)\b",
    re.I,
)
_BAD_QUESTION_RE = re.compile(
    r"\b(what (?:is|are|was|were).{0,25} doing|who (?:is|are|was|were) "
    r"(?:shown|pictured)|what does (?:this|the) image show|identify the "
    r"(?:person|object|logo|place)|what (?:is|are) visible|article written by "
    r"(?:the )?pictured|pictured (?:author|journalist|reporter))\b",
    re.I,
)
_BAD_AUDIT_NOTE_RE = re.compile(
    r"\b(not the (?:same|one described)|does not (?:match|depict)|"
    r"unrelated (?:to|image)|image (?:is|appears) (?:generic|irrelevant)|"
    r"only loosely related|decorative image|author headshot)\b",
    re.I,
)


def _bump(stats, key, amount=1):
    with _stats_lock:
        stats[key] = stats.get(key, 0) + amount


def _norm(value):
    value = str(value).lower().strip().translate(_PUNCT_TABLE)
    value = _ARTICLES_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def _nums(value):
    return re.findall(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))


def _fast_match(gold, pred):
    """Return True/False for clear cases and None for semantic judging."""
    g, p = _norm(gold), _norm(pred)
    if not p or p in {"unknown", "n/a", "cannot determine"}:
        return False
    if g == p:
        return True
    gn, pn = _nums(gold), _nums(pred)
    if gn or pn:
        if set(gn) != set(pn):
            return False
        scale = {"hundred", "thousand", "million", "billion", "trillion", "%",
                 "percent", "km", "kg", "miles", "dollars", "euros", "yuan"}
        gs, ps = set(g.split()) & scale, set(p.split()) & scale
        if gs != ps:
            return None
    if len(g) >= 4 and (g in p or p in g):
        return True
    return None


def _judge(question, gold, pred):
    prompt = JUDGE_PROMPT.format(question=question, gold=gold, pred=pred)
    out = qwen_api.call_text(prompt, model=qwen_api.TEXT_MODEL,
                             temperature=0.0, max_tokens=8)
    if not out:
        out = ark_api.call_text(prompt, temperature=0.0, max_tokens=8)
    if not out:
        raise RuntimeError("semantic judge unavailable")
    upper = out.upper()
    return "CORRECT" in upper and "INCORRECT" not in upper


def _is_correct(question, gold, pred):
    fast = _fast_match(gold, pred)
    return fast if fast is not None else _judge(question, gold, pred)


def _call_member(member, image_path, prompt, temperature, max_tokens=48):
    if member["provider"] == "qwen":
        return qwen_api.call_image(
            image_path, prompt, model=member["model"],
            temperature=temperature, max_tokens=max_tokens,
        ).strip()
    return ark_api.call_image(
        image_path, prompt, temperature=temperature, max_tokens=max_tokens
    ).strip()


def _parse_json(text):
    return ark_api._parse(text)


def _clean_ws(value):
    value = str(value).replace("\u00a0", " ")
    value = value.replace("“", '"').replace("”", '"')
    value = value.replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", value).strip().strip('"')


def _verbatim_evidence(article_text, evidence):
    return _clean_ws(evidence).lower() in _clean_ws(article_text).lower()


def _recover_verbatim(article_text, evidence):
    """Map a near-verbatim model quote back to the exact source sentence."""
    if _verbatim_evidence(article_text, evidence):
        return _clean_ws(evidence)
    target = _clean_ws(evidence)
    sentences = [s.strip() for s in re.split(
        r"(?<=[.!?。！？])\s+|\n+", article_text
    ) if len(s.strip()) >= 20]
    if not target or not sentences:
        return None
    scored = [(difflib.SequenceMatcher(None, target.lower(),
                                       _clean_ws(sentence).lower()).ratio(), sentence)
              for sentence in sentences]
    score, sentence = max(scored, key=lambda pair: pair[0])
    return _clean_ws(sentence) if score >= 0.78 else None


def _looks_english(text):
    letters = re.findall(r"[A-Za-z\u4e00-\u9fff]", str(text))
    if not letters:
        return False
    ascii_letters = sum(ch.isascii() for ch in letters)
    return ascii_letters / len(letters) >= 0.85


def _sanity(candidate, article):
    if not isinstance(candidate, dict) or candidate.get("reject_reason"):
        return False, "generator_reject"
    required = (
        "image_summary", "visual_anchor", "visual_anchor_type", "event_fact", "evidence",
        "question", "answer", "answer_type", "closed_book_self_answer",
        "freshness_relation", "requires_web_search", "image_article_match",
        "quality_rationale",
    )
    if any(not str(candidate.get(k, "")).strip() for k in required):
        return False, "missing_field"
    question = str(candidate["question"]).strip()
    answer = str(candidate["answer"]).strip()
    if candidate.get("answer_type") not in ANSWER_TYPES:
        return False, "answer_type"
    if candidate.get("visual_anchor_type") not in {
            "event_scene", "person", "object", "venue", "document"}:
        return False, "visual_anchor_type"
    if candidate.get("freshness_relation") not in {
            "current_event", "new_announcement", "new_result"}:
        return False, "historical_background"
    if len(answer.split()) > 8 or len(answer) > 80:
        return False, "answer_length"
    words = question.split()
    if len(words) < 10 or len(words) > 48 or not question.endswith("?"):
        return False, "question_form"
    if not _looks_english(question):
        return False, "question_language"
    if not _VISUAL_REF_RE.search(question):
        return False, "no_visual_referent"
    if not _EVENT_CUE_RE.search(question):
        return False, "no_event_cue"
    if _BAD_QUESTION_RE.search(question):
        return False, "image_only_question"
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", answer)]
    if candidate.get("answer_type") == "temporal" and years and \
            max(years) < datetime.now().year:
        return False, "historical_temporal_answer"
    question_years = [
        int(y) for y in re.findall(r"\b(20\d{2})\b", question)
    ]
    current_year = datetime.now().year
    if candidate.get("answer_type") == "temporal" and question_years and \
            max(question_years) < current_year:
        return False, "historical_temporal_question"
    if any(y < current_year for y in question_years) and re.search(
            r"\bas of (?:the )?.{0,30}\b20\d{2}\b", question, re.I):
        return False, "historical_question_context"
    if candidate.get("requires_web_search") is not True:
        return False, "self_search_not_required"
    if candidate.get("image_article_match") is not True:
        return False, "self_image_mismatch"
    if not _verbatim_evidence(article["text"], candidate["evidence"]):
        return False, "non_verbatim_evidence"
    answer_numbers = re.findall(r"\d+(?:\.\d+)?", answer)
    evidence_numbers = re.findall(
        r"\d+(?:\.\d+)?", str(candidate["evidence"])
    )
    if answer_numbers and not set(answer_numbers).issubset(set(evidence_numbers)):
        return False, "answer_number_absent_from_evidence"
    return True, ""


def _match_audit(article, image_path, candidate):
    prompt = MATCH_PROMPT.format(
        title=article["title"], source=article["source"],
        language=article.get("source_language", "unknown"),
        pub_date=article.get("pub_date", "unknown"),
        question=candidate["question"], answer=candidate["answer"],
        evidence=candidate["evidence"],
    )
    raw = qwen_api.call_image(
        image_path, prompt, model=qwen_api.FAST_VISION_MODEL,
        temperature=0.0, max_tokens=320, json_object=True,
    )
    audit = _parse_json(raw)
    if not isinstance(audit, dict):
        return None, ["parse_failure"]
    score_thresholds = {
        "image_article_match": 4,
        "question_image_grounding": 2,
        "event_specificity": MATCH_SCORE_MIN,
        "search_necessity": MATCH_SCORE_MIN,
        "fresh_fact_centrality": MATCH_SCORE_MIN,
        "question_clarity": MATCH_SCORE_MIN,
    }
    failures = []
    try:
        failures.extend(k for k, minimum in score_thresholds.items()
                        if int(audit.get(k, 0)) < minimum)
    except (TypeError, ValueError):
        failures.append("invalid_score")
    if audit.get("explicit_event_question") is not True:
        failures.append("explicit_event_question")
    if audit.get("image_only_answerable") is not False:
        failures.append("image_only_answerable")
    if audit.get("visual_claim_supported") is not True:
        failures.append("visual_claim_supported")
    if _BAD_AUDIT_NOTE_RE.search(str(audit.get("audit_note", ""))):
        failures.append("audit_note_mismatch")
    return audit, failures


def _grounding_audit(article, candidate):
    prompt = GROUNDING_PROMPT.format(
        question=candidate["question"],
        image_summary=candidate["image_summary"],
        visual_anchor=candidate["visual_anchor"],
    )
    samples = []
    for _ in range(2):
        raw = qwen_api.call_text(
            prompt, model=qwen_api.TEXT_MODEL, temperature=0.0,
            max_tokens=400, json_object=True,
        )
        audit = _parse_json(raw)
        if not isinstance(audit, dict):
            return None
        if audit.get("image_resolves_omitted_subject") is not True:
            return None
        if audit.get("omitted_subject_is_answer_target") is not True:
            return None
        if not str(audit.get("omitted_subject", "")).strip():
            return None
        samples.append(audit)
    return {
        "profile": "qwen-plus-all-2",
        "image_resolves_omitted_subject": True,
        "omitted_subject_is_answer_target": True,
        "omitted_subject": samples[0]["omitted_subject"],
        "samples": samples,
    }


def _certify_closed_book(image_path, question, answer, first_pred, stats):
    """P1: pass only when every model/sample fails. Stop at first success."""
    audit = {member["id"]: [] for member in PANEL}
    if first_pred:
        audit[PANEL[0]["id"]].append(first_pred[:100])
        if _is_correct(question, answer, first_pred):
            _bump(stats, "drop_l1_closed_book")
            return None
    for member_index, member in enumerate(PANEL):
        start = 1 if member_index == 0 and first_pred else 0
        for sample_index in range(start, CERT_SAMPLES):
            temperature = 0.25 + 0.15 * (sample_index % 3)
            pred = _call_member(
                member, image_path, CB_PROMPT.format(question=question),
                temperature=temperature,
            )
            if not pred:
                _bump(stats, "drop_cb_api_failure")
                return None
            audit[member["id"]].append(pred[:100])
            _bump(stats, "cb_panel_calls")
            if _is_correct(question, answer, pred):
                _bump(stats, "drop_closed_book")
                _bump(stats, "cb_early_stops")
                return None
    return audit


def _certify_oracle(image_path, title, question, answer, evidence, stats):
    """P2: pass only when every model/sample succeeds. Stop at first failure."""
    audit = {member["id"]: [] for member in PANEL}
    prompt = OR_PROMPT.format(title=title, evidence=evidence, question=question)
    for member in PANEL:
        for sample_index in range(CERT_SAMPLES):
            temperature = 0.0 if sample_index == 0 else 0.05 * sample_index
            pred = _call_member(
                member, image_path, prompt, temperature=temperature
            )
            audit[member["id"]].append(pred[:100])
            _bump(stats, "oracle_panel_calls")
            if not _is_correct(question, answer, pred):
                _bump(stats, "drop_oracle")
                _bump(stats, "drop_oracle_" + member["id"])
                _bump(stats, "oracle_early_stops")
                return None
    return audit


def _flat_preds(audit):
    return [f"{member}: {pred}" for member, preds in audit.items()
            for pred in preds]


def process_article(article, stats):
    image_path = os.path.join(DATA_DIR, article["image"])
    if not os.path.exists(image_path):
        return None
    prompt = GEN_PROMPT.format(
        title=article["title"], source=article["source"],
        language=article.get("source_language", "unknown"),
        category=article["category"], pub_date=article.get("pub_date") or "today",
        text=article["text"][:6000],
    )
    raw = ark_api.call_image(
        image_path, prompt, temperature=0.45, max_tokens=1400
    )
    candidate = _parse_json(raw)
    if isinstance(candidate, list):
        candidate = candidate[0] if candidate else None
    if isinstance(candidate, dict) and candidate.get("evidence"):
        recovered = _recover_verbatim(article["text"], candidate["evidence"])
        if recovered:
            candidate["evidence"] = recovered
    _bump(stats, "articles_generated")
    ok, reason = _sanity(candidate, article)
    if not ok:
        _bump(stats, f"drop_{reason}")
        return None
    _bump(stats, "generated_candidates")

    question = candidate["question"].strip()
    answer = str(candidate["answer"]).strip()
    self_pred = str(candidate["closed_book_self_answer"]).strip()
    if _is_correct(question, answer, self_pred):
        _bump(stats, "drop_l0_self_answerable")
        return None

    match_audit, match_failures = _match_audit(article, image_path, candidate)
    if match_failures:
        _bump(stats, "drop_image_question_mismatch")
        for failure in match_failures:
            _bump(stats, "drop_match_" + failure)
        return None
    grounding_audit = _grounding_audit(article, candidate)
    if grounding_audit is None:
        _bump(stats, "drop_referent_not_image_grounded")
        return None

    # L1 cheap n=1 screen; this prediction becomes sample 1 of the panel.
    first_pred = _call_member(
        PANEL[0], image_path, CB_PROMPT.format(question=question),
        temperature=0.2,
    )
    _bump(stats, "l1_calls")
    cb_audit = _certify_closed_book(
        image_path, question, answer, first_pred, stats
    )
    if cb_audit is None:
        return None
    or_audit = _certify_oracle(
        image_path, article["title"], question, answer,
        candidate["evidence"].strip(), stats,
    )
    if or_audit is None:
        return None

    _bump(stats, "certified")
    language = article.get("source_language") or (
        "en" if _looks_english(article.get("title", "")) else "other"
    )
    return {
        "id": f"{article['id']}-0",
        "article_id": article["id"],
        "image": article["image"],
        "question": question,
        "answer": answer,
        "answer_type": candidate["answer_type"],
        "is_quantitative": candidate["answer_type"] in QUANT_TYPES,
        "evidence": candidate["evidence"].strip(),
        "category": article["canonical_category"],
        "source_category": article["category"],
        "source": article["source"],
        "source_language": language,
        "article_url": article["url"],
        "article_title": article["title"],
        "pub_date": article.get("pub_date"),
        "crawl_time": article["crawl_time"],
        "build_date": BUILD_DATE,
        "image_summary": candidate["image_summary"],
        "visual_anchor": candidate["visual_anchor"],
        "visual_anchor_type": candidate["visual_anchor_type"],
        "event_fact": candidate["event_fact"],
        "freshness_relation": candidate["freshness_relation"],
        "l0_self_answer": self_pred,
        "image_match_audit": match_audit,
        "referent_grounding_audit": grounding_audit,
        "closed_book_preds": _flat_preds(cb_audit),
        "oracle_preds": _flat_preds(or_audit),
        "certification": {
            "profile": f"3-model-x-{CERT_SAMPLES}",
            "panel": [m["id"] for m in PANEL],
            "closed_book_logic": "all samples must be incorrect",
            "oracle_logic": "all samples must be correct",
            "closed_book": cb_audit,
            "oracle": or_audit,
        },
    }


def _q_tokens(question):
    return set(_norm(question).split())


def _interleave_category(articles):
    rng = random.Random(20260815)
    buckets = {}
    for article in articles:
        buckets.setdefault(article["canonical_category"], []).append(article)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    order = sorted(buckets, key=lambda c: (-len(buckets[c]), c))
    output = []
    for index in range(max((len(b) for b in buckets.values()), default=0)):
        for category in order:
            if index < len(buckets[category]):
                output.append(buckets[category][index])
    return output


def _within_freshness_window(record, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(record.get("pub_date") or "")
        age = now - dt.astimezone(timezone.utc)
    except Exception:
        return False
    return (-timedelta(hours=FUTURE_TOLERANCE_HOURS) <= age <=
            timedelta(hours=FRESH_HOURS))


def _fresh_articles(all_articles):
    now = datetime.now(timezone.utc)
    output = []
    for article in all_articles:
        if not _within_freshness_window(article, now=now):
            continue
        article = dict(article)
        article["canonical_category"] = CATEGORY_MAP.get(
            article.get("category", ""), "regional"
        )
        if not article.get("source_language"):
            article["source_language"] = (
                "en" if _looks_english(article.get("title", "")) else "other"
            )
        output.append(article)
    english = [a for a in output if a["source_language"] == "en"]
    fallback = [a for a in output if a["source_language"] != "en"]
    return _interleave_category(english) + _interleave_category(fallback)


def _atomic_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def build(target=200, workers=8, output_name="benchmark_v2.next.json",
          resume=True):
    article_path = os.path.join(DATA_DIR, "articles.json")
    with open(article_path, encoding="utf-8") as f:
        articles = _fresh_articles(json.load(f))
    english_articles = sum(a["source_language"] == "en" for a in articles)
    print(f"[fresh] {len(articles)} articles: {english_articles} English; "
          f"profile=3-model-x-{CERT_SAMPLES}")

    output_path = os.path.join(DATA_DIR, output_name)
    stats_path = os.path.join(
        DATA_DIR, os.path.splitext(output_name)[0].replace("benchmark", "stats") + ".json"
    )
    bench = []
    if resume and os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            bench = json.load(f)
        before = len(bench)
        now = datetime.now(timezone.utc)
        bench = [item for item in bench
                 if _within_freshness_window(item, now=now)]
        if len(bench) != before:
            print(f"[resume] removed {before-len(bench)} stale checkpoint items; "
                  f"{len(bench)} remain")
            _atomic_json(output_path, bench)
    elif not resume:
        for stale in (output_path, stats_path):
            if os.path.exists(stale):
                os.remove(stale)
    used_articles = {item["article_id"] for item in bench}
    articles = [a for a in articles if a["id"] not in used_articles]

    stats = {
        "build_date": BUILD_DATE,
        "target": target,
        "certification_profile": f"3-model-x-{CERT_SAMPLES}",
        "panel": [m["id"] for m in PANEL],
        "target_english_ratio": TARGET_ENGLISH_RATIO,
        "target_quantitative_ratio": TARGET_QUANT_RATIO,
        "fresh_articles": len(articles) + len(used_articles),
        "fresh_english_articles": english_articles,
        "resumed_items": len(bench),
    }
    accepted_tokens = [_q_tokens(item["question"]) for item in bench]
    cat_counts = {}
    for item in bench:
        cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1
    max_non_english = target - math.ceil(target * TARGET_ENGLISH_RATIO)
    max_non_quant = target - math.ceil(target * TARGET_QUANT_RATIO)
    category_soft_cap = max(35, math.ceil(target / 5))
    stop = threading.Event()
    admission_lock = threading.Lock()
    deferred = []
    t0 = time.time()

    def checkpoint():
        _atomic_json(output_path, bench)

    def try_admit(item, enforce_category=True):
        with admission_lock:
            if len(bench) >= target:
                stop.set()
                return False
            non_en = sum(q.get("source_language") != "en" for q in bench)
            non_quant = sum(not q.get("is_quantitative") for q in bench)
            if item.get("source_language") != "en" and non_en >= max_non_english:
                deferred.append((item, "language"))
                return False
            if not item.get("is_quantitative") and non_quant >= max_non_quant:
                deferred.append((item, "quantitative"))
                return False
            category = item["category"]
            if enforce_category and cat_counts.get(category, 0) >= category_soft_cap:
                deferred.append((item, "category"))
                return False
            tokens = _q_tokens(item["question"])
            for previous in accepted_tokens:
                similarity = len(tokens & previous) / max(1, len(tokens | previous))
                if similarity > QUESTION_SIM_THRESHOLD:
                    _bump(stats, "drop_duplicate_question")
                    return False
            bench.append(item)
            accepted_tokens.append(tokens)
            cat_counts[category] = cat_counts.get(category, 0) + 1
            _bump(stats, "admitted")
            if len(bench) % 5 == 0 or len(bench) == target:
                checkpoint()
            if len(bench) >= target:
                stop.set()
            print(f"[{len(bench):>3}/{target}] {item['source']:<14} "
                  f"{item['answer_type']:<8} {item['article_title'][:54]}")
            return True

    def worker(article):
        if stop.is_set():
            return
        try:
            item = process_article(article, stats)
            if item:
                try_admit(item, enforce_category=True)
        except Exception as exc:
            _bump(stats, "worker_errors")
            with _print_lock:
                print("[worker error]", article.get("source"), str(exc)[:180])

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, article) for article in articles]
        for future in as_completed(futures):
            future.result()
            if stop.is_set():
                break

    # Category is a soft balance objective. Language and quantitative ratios
    # remain hard and are never relaxed.
    if len(bench) < target:
        for item, reason in list(deferred):
            if reason == "category":
                try_admit(item, enforce_category=False)
            if len(bench) >= target:
                break

    checkpoint()
    english_count = sum(q.get("source_language") == "en" for q in bench)
    quant_count = sum(q.get("is_quantitative") for q in bench)
    stats.update({
        "elapsed_sec": round(time.time() - t0),
        "final_size": len(bench),
        "english_count": english_count,
        "english_ratio": round(english_count / max(1, len(bench)), 4),
        "quantitative_count": quant_count,
        "quantitative_ratio": round(quant_count / max(1, len(bench)), 4),
        "category_counts": cat_counts,
        "source_counts": {
            source: sum(q["source"] == source for q in bench)
            for source in sorted({q["source"] for q in bench})
        },
        "answer_type_counts": {
            kind: sum(q["answer_type"] == kind for q in bench)
            for kind in sorted(ANSWER_TYPES)
        },
    })
    _atomic_json(stats_path, stats)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("saved ->", output_path)
    return len(bench), output_path, stats_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", type=int, default=200)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", default="benchmark_v2.next.json")
    parser.add_argument("--fresh", action="store_true",
                        help="ignore an existing staging output")
    args = parser.parse_args()
    size, _, _ = build(
        target=args.target, workers=args.workers, output_name=args.output,
        resume=not args.fresh,
    )
    if size < args.target:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

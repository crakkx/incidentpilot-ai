"""RCA evaluation validators.

Each function takes an :class:`~app.evals.rca_dataset.RCAEvalCase` and a
:class:`~app.schemas.analysis.RCAReport` and returns a
:class:`DimensionResult` with a pass/fail decision, a 0–1 score, and a list
of human-readable failure messages.

Call :func:`validate_case` to run all seven validators in one shot and
receive a :class:`CaseValidationResult`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.evals.rca_dataset import (
    EvalEvidenceItem,
    RCAEvalCase,
)
from app.rag.embeddings import embed_texts
from app.schemas.analysis import RCAReport

# Cosine similarity threshold for semantic validators.
# Embeddings are L2-normalised, so dot-product == cosine similarity.
SEMANTIC_THRESHOLD: float = 0.78


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class DimensionResult:
    """Outcome of one validation dimension for a single eval case."""

    dimension: str
    """Name of the validator dimension (e.g. ``"observations"``)."""

    passed: bool
    """``True`` when the report satisfies all hard requirements."""

    score: float
    """Fractional quality score in the range [0.0, 1.0]."""

    issues: list[str] = field(default_factory=list)
    """Human-readable descriptions of each failure."""


@dataclass
class CaseValidationResult:
    """Aggregated result for a single eval case across all dimensions."""

    case_id: str
    dimensions: list[DimensionResult]

    @property
    def passed(self) -> bool:
        """``True`` only when every dimension passes."""
        return all(d.passed for d in self.dimensions)

    @property
    def overall_score(self) -> float:
        """Mean of per-dimension scores."""
        if not self.dimensions:
            return 0.0
        return sum(d.score for d in self.dimensions) / len(self.dimensions)

    def dimension(self, name: str) -> DimensionResult | None:
        """Return the result for a named dimension, or ``None``."""
        for d in self.dimensions:
            if d.name == name:
                return d
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_evidence_index(
    eval_evidence: list[EvalEvidenceItem],
) -> dict[str, EvalEvidenceItem]:
    """Return a ``{id: item}`` lookup from the eval case evidence list."""
    return {item.id: item for item in eval_evidence}


def _report_text(report: RCAReport) -> str:
    """Concatenate all searchable text in the report, lowercased."""
    parts: list[str] = [
        report.incident_summary,
        report.likely_root_cause,
    ]

    if report.root_cause is not None:
        parts.append(report.root_cause.immediate_mechanism)
        if report.root_cause.suspected_trigger:
            parts.append(report.root_cause.suspected_trigger)

    for obs in report.observations:
        parts.append(obs.concept)

    for ev in report.evidence:
        parts.append(ev.excerpt)
        parts.append(ev.explanation)

    for action in report.recommended_actions:
        parts.append(action)

    for info in report.missing_information:
        parts.append(info)

    return " ".join(parts).lower()


def _cosine(a: list[float], b: list[float]) -> float:
    """Dot-product of two L2-normalised vectors equals cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Stem-based token-overlap helpers
# ---------------------------------------------------------------------------

#: Function words that carry no semantic information for overlap matching.
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "if", "to", "by", "for", "in", "on",
    "at", "of", "with", "after", "before", "is", "are", "was", "were",
    "be", "been", "it", "its", "this", "that", "as", "all", "up", "out",
    "not", "do", "into", "over", "from", "we", "you", "he", "she", "they",
    "has", "have", "had", "will", "would", "should", "may", "can", "could",
    "per", "via", "vs", "etc",
})


def _stem_token(token: str) -> str:
    """Very light suffix-stripping so inflected forms compare equal.

    Examples::

        'rolling'  -> 'roll'
        'archiving' -> 'archiv'
        'traces'   -> 'trac'
        'renewing' -> 'renew'
    """
    # Ordered longest-first to avoid over-stripping.
    _SUFFIXES = (
        "ations", "ation", "ings", "ment", "ments", "ness",
        "tion", "tions", "ers", "ies", "ing", "est", "ful",
        "ous", "ive", "ize", "ise", "ary", "ery",
        "ed", "es", "er", "ly",
        "s",
    )
    min_stem = 4  # Don't strip so much that the stem becomes meaningless.
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= min_stem:
            token = token[: -len(suffix)]
            break
            
    if token.endswith("e") and len(token) > min_stem:
        token = token[:-1]
        
    return token


def _token_overlap_match(
    candidate_texts: list[str],
    reference_phrase: str,
) -> bool:
    """Return True when key stems from *reference_phrase* appear in any candidate.

    Matching rules
    --------------
    1. Tokenise both sides to ``\\w+`` words, lowercase.
    2. Discard tokens in :data:`_STOP_WORDS` or shorter than 3 chars.
    3. Stem each token with :func:`_stem_token`.
    4. Require **all** stems to appear when the phrase has ≤ 2 significant
       tokens; otherwise require at least ⌈N × 0.60⌉ to appear.

    This handles the common failure modes of the embedding approach:

    * Inflected forms  — "rolling back" ↔ "rollback" / "roll back"
    * Reversed order  — "Profile heap allocations" ↔ "heap profil"
    * Proximity gaps  — "Renew the expired service account token" ↔ "renew token"
    * Partial phrase  — "fallback payment provider" ↔ "fallback provider"
    """
    ref_stems: set[str] = {
        _stem_token(t)
        for t in re.findall(r"\w+", reference_phrase.lower())
        if t not in _STOP_WORDS and len(t) >= 3
    }
    if not ref_stems:
        return False  # Empty phrase — conservatively reject.

    # Build the union of all stemmed tokens across every candidate sentence.
    cand_stems: set[str] = set()
    for text in candidate_texts:
        for t in re.findall(r"\w+", text.lower()):
            if len(t) >= 3:
                cand_stems.add(_stem_token(t))

    overlap = len(ref_stems & cand_stems)
    n = len(ref_stems)
    # For short phrases every token must match; for longer phrases 60% suffices.
    required = n if n <= 2 else -(-n * 3 // 5)  # Ceiling division of n×0.6
    return overlap >= required


def _semantic_match(
    candidate_text: str,
    reference_phrases: list[str],
    threshold: float = SEMANTIC_THRESHOLD,
) -> tuple[bool, float]:
    """Return (matched, best_score) for a single candidate text.

    Three-tier matching in order of cost:
    1. Exact substring  — O(1), returns 1.0.
    2. Stem token overlap  — O(n), returns 0.90.  Handles inflected forms,
       word-order differences, and adjacency gaps.
    3. Semantic embedding  — O(embedding call), returns cosine similarity.
    """
    candidate_lower = candidate_text.lower()

    # Tier 1: exact substring.
    for phrase in reference_phrases:
        if phrase.lower() in candidate_lower:
            return True, 1.0

    if not reference_phrases:
        return False, 0.0

    # Tier 2: stem-based token overlap.
    for phrase in reference_phrases:
        if _token_overlap_match([candidate_text], phrase):
            return True, 0.90

    # Tier 3: semantic embedding.
    all_texts = [candidate_text] + reference_phrases
    try:
        vectors = embed_texts(all_texts)
    except Exception:
        return False, 0.0

    candidate_vec = vectors[0]
    ref_vecs = vectors[1:]

    best = max(_cosine(candidate_vec, rv) for rv in ref_vecs)
    return best >= threshold, best


def _semantic_match_any(
    candidate_texts: list[str],
    reference_phrases: list[str],
    threshold: float = SEMANTIC_THRESHOLD,
) -> tuple[bool, float]:
    """Return (matched, best_score) across *multiple* candidate texts.

    Embeds all candidates and reference phrases in one batch, then returns
    the best cosine similarity across all (candidate, reference) pairs.
    This is used by ``validate_actions`` so that each action sentence is
    scored individually rather than the whole blob, preventing score dilution.

    Three-tier matching in order of cost:
    1. Exact substring  — O(n), returns 1.0.
    2. Stem token overlap  — O(n), returns 0.90.
    3. Semantic embedding  — O(embedding call), returns cosine similarity.
    """
    if not candidate_texts or not reference_phrases:
        return False, 0.0

    # Tier 1: exact substring match on any candidate.
    for candidate in candidate_texts:
        candidate_lower = candidate.lower()
        for phrase in reference_phrases:
            if phrase.lower() in candidate_lower:
                return True, 1.0

    # Tier 2: stem token overlap across all candidates.
    for phrase in reference_phrases:
        if _token_overlap_match(candidate_texts, phrase):
            return True, 0.90

    # Tier 3: semantic embedding.
    all_texts = candidate_texts + reference_phrases
    try:
        vectors = embed_texts(all_texts)
    except Exception:
        return False, 0.0

    cand_vecs = vectors[: len(candidate_texts)]
    ref_vecs = vectors[len(candidate_texts) :]

    best = max(
        _cosine(cv, rv)
        for cv in cand_vecs
        for rv in ref_vecs
    )
    return best >= threshold, best


# ---------------------------------------------------------------------------
# 1. Observation validator
# ---------------------------------------------------------------------------


def validate_observations(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Check that every required observation concept appears in the report.

    A required observation is satisfied when at least one of the following
    is true:

    * A keyword from ``observation.keywords_any`` appears in the full report
      text (case-insensitive).
    * At least one ``acceptable_source_id`` is cited in ``report.evidence``.
    """
    required = [obs for obs in case.expectations.observations if obs.required]

    if not required:
        return DimensionResult(
            dimension="observations",
            passed=True,
            score=1.0,
        )

    all_text = _report_text(report)
    cited_source_ids = {ev.source_id for ev in report.evidence}

    issues: list[str] = []
    found = 0

    for obs in required:
        keyword_found = any(kw.lower() in all_text for kw in obs.keywords_any)

        source_cited = bool(
            obs.acceptable_source_ids
            and cited_source_ids.intersection(obs.acceptable_source_ids)
        )

        if keyword_found or source_cited:
            found += 1
        else:
            issues.append(
                f"Required observation '{obs.id}' ({obs.concept!r}) not found. "
                f"Expected one of keywords {obs.keywords_any} or source IDs "
                f"{obs.acceptable_source_ids} to be cited."
            )

    score = found / len(required)

    return DimensionResult(
        dimension="observations",
        passed=not issues,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 2. Root-cause validator
# ---------------------------------------------------------------------------


def validate_root_cause(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Validate that the mechanism, trigger, and confidence match expectations.

    Two-tier validation (Option C):

    * **Mechanism** — semantic similarity against ``immediate_mechanism_keywords_any``
      using the local sentence-transformer model.  Exact substring match is tried
      first (fast path).  Hard-fail when no phrase clears ``SEMANTIC_THRESHOLD``.
    * **Null root_cause handling** — when ``report.root_cause is None`` the
      validator checks whether the expectation keywords include uncertainty
      phrases ("unknown", "cannot determine", etc.).  If so, the null field
      itself is treated as a valid signal of insufficient evidence.
    * **Trigger keywords** — semantic scoring (soft-fail).
    * **Confidence** — exact match against ``acceptable_confidence`` (hard-fail).
    * **Structured distinction** — exact field presence check (soft-fail).
    """
    expectation = case.expectations.root_cause
    all_text = _report_text(report)
    issues: list[str] = []
    scores: list[float] = []

    # -- Mechanism: SEMANTIC (hard fail if below threshold) ------------------
    #
    # Special case: when root_cause is null, the model is explicitly signalling
    # that the cause is unknown/indeterminate.  If the expected keywords include
    # any uncertainty phrase, treat the null as a match.
    _UNCERTAINTY_PHRASES = {
        "unknown", "insufficient evidence", "cannot determine",
        "undetermined", "unclear", "not determined",
    }
    expected_kws = expectation.immediate_mechanism_keywords_any

    if report.root_cause is None and any(
        kw.lower() in _UNCERTAINTY_PHRASES for kw in expected_kws
    ):
        mechanism_found, mech_score = True, 1.0
    else:
        mechanism_found, mech_score = _semantic_match(
            all_text,
            expected_kws,
        )

    scores.append(mech_score)
    if not mechanism_found:
        issues.append(
            f"Root-cause mechanism not found (best semantic similarity "
            f"{mech_score:.2f} < {SEMANTIC_THRESHOLD}). "
            f"Expected one of: {expected_kws}"
        )

    # -- Trigger keywords: SEMANTIC (scored, not hard-fail) ------------------
    if expectation.suspected_trigger_keywords_any:
        trigger_found, trig_score = _semantic_match(
            all_text,
            expectation.suspected_trigger_keywords_any,
        )
        scores.append(trig_score)
        if not trigger_found:
            issues.append(
                f"Root-cause trigger not mentioned (best similarity "
                f"{trig_score:.2f} < {SEMANTIC_THRESHOLD}). "
                f"Expected one of: {expectation.suspected_trigger_keywords_any}"
            )

    # -- Confidence: EXACT (hard fail if wrong) ------------------------------
    confidence_ok = report.confidence in expectation.acceptable_confidence
    scores.append(1.0 if confidence_ok else 0.0)
    if not confidence_ok:
        issues.append(
            f"Confidence '{report.confidence}' not in acceptable values "
            f"{expectation.acceptable_confidence}."
        )

    # -- Structured distinction (scored only) --------------------------------
    if expectation.must_distinguish_mechanism_and_trigger:
        if report.root_cause is not None:
            has_both = bool(
                report.root_cause.immediate_mechanism.strip()
                and (report.root_cause.suspected_trigger or "").strip()
            )
            scores.append(1.0 if has_both else 0.5)
            if not has_both:
                issues.append(
                    "Report should distinguish immediate mechanism from "
                    "suspected trigger using the structured root_cause field."
                )
        else:
            scores.append(0.5)
            issues.append(
                "Structured root_cause field absent; mechanism/trigger "
                "distinction could not be verified."
            )

    score = sum(scores) / len(scores) if scores else 1.0
    hard_fail = not mechanism_found or not confidence_ok

    return DimensionResult(
        dimension="root_cause",
        passed=not hard_fail,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 3. Actions validator
# ---------------------------------------------------------------------------


def validate_actions(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Check that recommended actions cover all required keyword groups.

    Two-tier validation (Option C):

    * **Required keyword groups** — each action sentence is compared
      individually against each reference phrase using ``_semantic_match_any``.
      The group passes when *any* action sentence scores >= ``SEMANTIC_THRESHOLD``
      against *any* phrase in the group.  This prevents score dilution from
      comparing a long blob against short reference phrases.
    * **Forbidden keywords** — exact substring match only (objective rule).
    """
    expectation = case.expectations.actions
    # Keep individual sentences for per-sentence comparison.
    action_sentences: list[str] = list(report.recommended_actions)
    issues: list[str] = []
    scores: list[float] = []

    for group in expectation.required_keyword_groups:
        group_found, group_score = _semantic_match_any(action_sentences, group)
        scores.append(group_score)
        if not group_found:
            issues.append(
                f"Required action not covered (best similarity "
                f"{group_score:.2f} < {SEMANTIC_THRESHOLD}): {group}"
            )

    # Forbidden keywords remain exact-match (objective safety constraint).
    actions_lower = " ".join(action_sentences).lower()
    for kw in expectation.forbidden_keywords:
        if kw.lower() in actions_lower:
            scores.append(0.0)
            issues.append(
                f"Forbidden keyword found in recommended actions: '{kw}'"
            )

    if not scores:
        return DimensionResult(
            dimension="actions",
            passed=True,
            score=1.0,
        )

    score = sum(scores) / len(scores)

    return DimensionResult(
        dimension="actions",
        passed=not issues,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 4. Source-type validator
# ---------------------------------------------------------------------------


def validate_source_types(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Verify that each cited source_id has the correct source_type.

    Only source IDs that exist in the eval case evidence are checked; IDs
    outside the eval set are already caught by the evidence-grounding
    validator in the application itself.
    """
    evidence_index = _build_evidence_index(case.evidence)
    issues: list[str] = []
    checked = 0
    correct = 0

    for ev_item in report.evidence:
        expected_item = evidence_index.get(ev_item.source_id)

        if expected_item is None:
            continue  # Not an eval-case ID — covered elsewhere.

        checked += 1

        if ev_item.source_type != expected_item.source_type:
            issues.append(
                f"source_id '{ev_item.source_id}' cited as source_type "
                f"'{ev_item.source_type}' but eval case declares "
                f"'{expected_item.source_type}'."
            )
        else:
            correct += 1

    if checked == 0:
        return DimensionResult(
            dimension="source_types",
            passed=True,
            score=1.0,
        )

    score = correct / checked

    return DimensionResult(
        dimension="source_types",
        passed=not issues,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 5. Numeric validator
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _extract_numbers(text: str) -> list[float]:
    return [float(m) for m in _NUMBER_RE.findall(text)]


def validate_numeric_facts(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Check that each expected numeric fact value appears in the report.

    For each :class:`~app.evals.rca_dataset.NumericFactExpectation` the
    validator searches for a number within ``tolerance`` of the expected
    ``value`` in:

    1. Excerpts and explanations of evidence items that cite
       ``fact.source_id``.
    2. As a fallback, the full report text.
    """
    facts = case.expectations.numeric_facts

    if not facts:
        return DimensionResult(
            dimension="numeric_facts",
            passed=True,
            score=1.0,
        )

    # Build {source_id: [combined excerpt + explanation texts]}
    cited_texts: dict[str, list[str]] = {}
    for ev_item in report.evidence:
        cited_texts.setdefault(ev_item.source_id, []).append(
            f"{ev_item.excerpt} {ev_item.explanation}"
        )

    full_text = _report_text(report)
    issues: list[str] = []
    passed_count = 0

    for fact in facts:
        texts_to_search: list[str] = list(cited_texts.get(fact.source_id, []))
        texts_to_search.append(full_text)

        fact_found = False

        for text in texts_to_search:
            for num in _extract_numbers(text):
                if abs(num - fact.value) <= fact.tolerance:
                    fact_found = True
                    break
            if fact_found:
                break

        if fact_found:
            passed_count += 1
        else:
            unit_str = f" {fact.unit}" if fact.unit else ""
            issues.append(
                f"Numeric fact '{fact.id}': expected {fact.value}{unit_str} "
                f"(±{fact.tolerance}) for source '{fact.source_id}' "
                "not found in report text."
            )

    score = passed_count / len(facts)

    return DimensionResult(
        dimension="numeric_facts",
        passed=not issues,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 6. Temporal validator
# ---------------------------------------------------------------------------


def validate_temporal_facts(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Verify temporal relations between pairs of evidence sources.

    For each :class:`~app.evals.rca_dataset.TemporalFactExpectation` the
    validator checks that:

    1. Both source IDs are cited in ``report.evidence``.
    2. The timestamps in the eval case evidence satisfy the declared
       ``relation`` (``"before"`` / ``"after"`` / ``"overlaps"``) and
       optional ``max_gap_seconds``.
    """
    facts = case.expectations.temporal_facts

    if not facts:
        return DimensionResult(
            dimension="temporal_facts",
            passed=True,
            score=1.0,
        )

    evidence_index = _build_evidence_index(case.evidence)
    cited_ids = {ev.source_id for ev in report.evidence}
    issues: list[str] = []
    passed_count = 0

    for fact in facts:
        left_item = evidence_index.get(fact.left_source_id)
        right_item = evidence_index.get(fact.right_source_id)

        if left_item is None or right_item is None:
            issues.append(
                f"Temporal fact '{fact.id}': source ID "
                f"'{fact.left_source_id}' or '{fact.right_source_id}' "
                "not found in eval case evidence."
            )
            continue

        # Both sources must be cited so the model reasoned about them.
        left_cited = fact.left_source_id in cited_ids
        right_cited = fact.right_source_id in cited_ids
        if not left_cited or not right_cited:
            missing = [
                sid
                for sid, cited in (
                    (fact.left_source_id, left_cited),
                    (fact.right_source_id, right_cited),
                )
                if not cited
            ]
            issues.append(
                f"Temporal fact '{fact.id}': report did not cite "
                f"source(s) {missing} needed for temporal reasoning."
            )
            continue

        left_ts = left_item.timestamp
        right_ts = right_item.timestamp

        if left_ts is None or right_ts is None:
            # No timestamps to compare — grant credit if both are cited.
            passed_count += 1
            continue

        diff_seconds = (right_ts - left_ts).total_seconds()
        relation_ok = False

        if fact.relation == "before":
            relation_ok = diff_seconds > 0
            if relation_ok and fact.max_gap_seconds is not None:
                relation_ok = diff_seconds <= fact.max_gap_seconds

        elif fact.relation == "after":
            relation_ok = diff_seconds < 0
            if relation_ok and fact.max_gap_seconds is not None:
                relation_ok = abs(diff_seconds) <= fact.max_gap_seconds

        elif fact.relation == "overlaps":
            gap = fact.max_gap_seconds if fact.max_gap_seconds is not None else 3600
            relation_ok = abs(diff_seconds) <= gap

        if relation_ok:
            passed_count += 1
        else:
            issues.append(
                f"Temporal fact '{fact.id}': expected "
                f"'{fact.left_source_id}' {fact.relation} "
                f"'{fact.right_source_id}'. "
                f"Actual diff: {diff_seconds:.0f}s"
                + (
                    f" (max allowed: {fact.max_gap_seconds}s)."
                    if fact.max_gap_seconds is not None
                    else "."
                )
            )

    score = passed_count / len(facts) if facts else 1.0

    return DimensionResult(
        dimension="temporal_facts",
        passed=not issues,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# 7. Causal-language validator
# ---------------------------------------------------------------------------


def validate_causal_language(
    case: RCAEvalCase,
    report: RCAReport,
) -> DimensionResult:
    """Enforce deployment-causality policy and forbidden phrase/claim rules.

    Deployment-causality policies:

    * ``"forbidden"``       — no deployment causality phrases allowed.
    * ``"correlation_only"`` — strong causal claims about deployment forbidden.
    * ``"supported"`` / ``"confirmed"`` — at least one deployment evidence item
      must be cited.
    * ``"not_applicable"``  — no deployment-related checks.
    """
    policy = case.expectations.causal_language
    all_text = _report_text(report)
    issues: list[str] = []

    # -- Explicitly forbidden phrases from the case -------------------------
    for phrase in policy.forbidden_phrases:
        if phrase.lower() in all_text:
            issues.append(
                f"Forbidden phrase found in report: '{phrase}'"
            )

    # -- Forbidden claims from expectations ---------------------------------
    for claim in case.expectations.forbidden_claims:
        if claim.lower() in all_text:
            issues.append(
                f"Forbidden claim found in report: '{claim}'"
            )

    # -- Deployment causality policy ----------------------------------------
    dep_policy = policy.deployment_causality

    if dep_policy == "forbidden":
        _CAUSAL_DEP_PHRASES = [
            "deployment caused",
            "caused by the deployment",
            "caused by deployment",
            "deployment was the cause",
            "deployment was responsible",
            "deployment introduced the bug",
        ]
        for phrase in _CAUSAL_DEP_PHRASES:
            if phrase in all_text:
                issues.append(
                    f"Policy forbids deployment causality claims, "
                    f"but report contains: '{phrase}'"
                )

    elif dep_policy == "correlation_only":
        _STRONG_CAUSAL = [
            "deployment definitely caused",
            "deployment proved to cause",
            "deployment was responsible",
            "definitively caused by the deployment",
            "deployment caused the outage",
            "new release caused",
        ]
        for phrase in _STRONG_CAUSAL:
            if phrase in all_text:
                issues.append(
                    f"Policy allows correlation only, but report makes "
                    f"strong causal deployment claim: '{phrase}'"
                )

    elif dep_policy in ("supported", "confirmed"):
        deployment_cited = any(
            ev.source_type == "deployment" for ev in report.evidence
        )
        if not deployment_cited:
            issues.append(
                f"Policy requires deployment causality '{dep_policy}', "
                "but no deployment evidence was cited."
            )

    score = 1.0 if not issues else max(0.0, 1.0 - 0.2 * len(issues))

    return DimensionResult(
        dimension="causal_language",
        passed=not issues,
        score=score,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# Full-case entry point
# ---------------------------------------------------------------------------


def validate_case(
    case: RCAEvalCase,
    report: RCAReport,
) -> CaseValidationResult:
    """Run all seven validators for a single eval case.

    Returns a :class:`CaseValidationResult` whose ``passed`` property is
    ``True`` only when every dimension passes.
    """
    return CaseValidationResult(
        case_id=case.id,
        dimensions=[
            validate_observations(case, report),
            validate_root_cause(case, report),
            validate_actions(case, report),
            validate_source_types(case, report),
            validate_numeric_facts(case, report),
            validate_temporal_facts(case, report),
            validate_causal_language(case, report),
        ],
    )

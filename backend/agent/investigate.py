"""Investigation protocol §17. Classification can use Astra; verdicts are rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.belief import BeliefUpdate, lr_for, posterior_from
from agent import llm
from agent.memory import Memory
from agent.questions import candidate as question_candidate
from agent.templates import Template, instantiate, templates_for
from agent.verdict import Verdict, decide
from rcg.store import Edge, GraphStore


@dataclass
class HypothesisResult:
    id: str
    leaf: str
    cls: str
    claim: str
    prior: float
    posterior: float
    verdict: Verdict
    hypothesis_node_id: str
    verdict_node_id: str
    previous: dict[str, Any] | None = None
    updates: list[BeliefUpdate] = field(default_factory=list)
    question: dict[str, Any] | None = None


@dataclass
class Investigation:
    results: list[HypothesisResult]
    explained_share: float


def _classify(leaf: str, facts: list[str], use_llm: bool) -> list[Template]:
    options = templates_for(leaf)
    if not options:
        return []
    if use_llm and llm.available():
        catalog = [{"class": t.cls, "claim": t.claim} for t in options]
        try:
            picked = llm.complete_json(
                "Pick the two most plausible hypothesis classes for this café variance.\n"
                f"leaf={leaf}\nfacts={facts}\nclasses={catalog}\n"
                'Return {"classes": ["...", "..."]}'
            )
            names = set(picked.get("classes") or [])
            chosen = [t for t in options if t.cls in names]
            if chosen:
                return chosen[:3]
        except Exception:
            pass
    return options[:3]


def _label_support(fact: dict[str, Any], cls: str, use_llm: bool) -> str:
    if fact.get("support"):
        return fact["support"]
    if use_llm and llm.available():
        try:
            out = llm.complete_json(
                "Label how this evidence bears on the hypothesis. "
                "Choose exactly one of strong_for, weak_for, neutral, weak_against, strong_against.\n"
                f"hypothesis_class={cls}\nevidence={fact}\n"
                'Return {"support": "..."}'
            )
            if out.get("support") in {
                "strong_for",
                "weak_for",
                "neutral",
                "weak_against",
                "strong_against",
            }:
                return out["support"]
        except Exception:
            pass
    return "neutral"


def investigate_leaf(
    *,
    leaf: str,
    phi: float,
    store: GraphStore,
    period: str,
    run_id: str,
    memory: Memory,
    facts: list[dict[str, Any]],
    entity: str | None,
    use_llm: bool,
    budget_left: int,
) -> list[HypothesisResult]:
    templates = _classify(leaf, [str(f) for f in facts], use_llm)
    results: list[HypothesisResult] = []
    for i, template in enumerate(templates):
        if budget_left <= 0:
            break
        hid = f"h_{leaf}_{template.cls}_{period}"
        claim = instantiate(template, leaf=leaf, entity=entity)
        prior_mem = memory.prior_for(leaf, template.cls)
        previous = dict(prior_mem) if prior_mem else None
        prior = float(prior_mem["posterior"]) if prior_mem and "posterior" in prior_mem else template.prior
        h_node = store.add(
            type="hypothesis",
            period=period,
            run_id=run_id,
            label=f"{leaf}:{template.cls}",
            value={"class": template.cls, "claim": claim, "prior_belief": prior},
            unit=None,
            provenance="inferred",
            payload={"plan": template.internal},
        )
        if prior_mem and prior_mem.get("hypothesis_node") and store.has_node(prior_mem["hypothesis_node"]):
            store.write_edge(
                Edge(prior_mem["hypothesis_node"], h_node.id, "recurs_from", period, run_id)
            )
        ratios: list[float] = []
        updates: list[BeliefUpdate] = []
        tier2 = False
        strong_against = False
        for fact in facts:
            allowed = fact.get("classes")
            if allowed and template.cls not in allowed:
                continue
            # Driver-level observations (for example, "the bill increased")
            # establish the variance, not its cause. A fact must name the
            # hypothesis classes it discriminates before it can move belief.
            support = (
                _label_support(fact, template.cls, use_llm)
                if allowed or fact.get("applies_to_all_hypotheses")
                else "neutral"
            )
            temporal = bool(fact.get("temporal_only"))
            ratio, capped = lr_for(support, temporal_only=temporal)
            ev = store.add(
                type="evidence",
                period=period,
                run_id=run_id,
                label=fact.get("label") or "evidence",
                value=fact.get("extract") or fact.get("label"),
                unit=None,
                provenance="retrieved" if fact.get("source") == "tavily" else "deterministic",
                payload={
                    "tier": fact.get("tier", 1),
                    "temporal_only": temporal,
                    "source": fact.get("source", "internal"),
                },
            )
            store.write_edge(Edge(ev.id, h_node.id, "tests", period, run_id))
            lr_node = store.add(
                type="belief_update",
                period=period,
                run_id=run_id,
                label=f"{hid}:{ev.id}",
                value={"support": support, "likelihood_ratio": ratio},
                unit=None,
                provenance="inferred",
                payload={"temporal_cap_applied": capped},
                inputs=[h_node.id, ev.id],
            )
            updates.append(
                BeliefUpdate(hid, ev.id, support, ratio, capped, fact.get("note") or "")
            )
            ratios.append(ratio)
            if support in {"strong_for", "weak_for"} and fact.get("tier", 1) <= 2 and not temporal:
                tier2 = True
                store.write_edge(Edge(ev.id, h_node.id, "supports", period, run_id))
            if support == "strong_against" and fact.get("tier", 1) == 1:
                strong_against = True
            _ = lr_node
        posterior = posterior_from(prior, ratios or [1.0])
        prev_label = prior_mem.get("verdict") if prior_mem else None
        prev_post = prior_mem.get("posterior") if prior_mem else None
        verdict = decide(
            posterior=posterior,
            has_tier2_nontemporal=tier2,
            has_strong_against_internal=strong_against,
            previous=prev_label,
            previous_posterior=prev_post,
        )
        v_node = store.add(
            type="verdict",
            period=period,
            run_id=run_id,
            label=f"{hid}:verdict",
            value={"verdict": verdict.label, "posterior": round(posterior, 4), "rule": verdict.rule},
            unit=None,
            provenance="deterministic",
            inputs=[h_node.id],
        )
        if verdict.label == "supported":
            for upd in updates:
                if upd.support in {"strong_for", "weak_for"}:
                    store.write_edge(Edge(upd.evidence_id, v_node.id, "supports", period, run_id))
        question = None
        if verdict.label in {"unresolved", "weakening"} and template.owner_resolvable:
            question = question_candidate(
                hypothesis_id=hid,
                leaf=leaf,
                cls=template.cls,
                unexplained_dollars=phi,
                recurring=previous is not None,
            )
            if question:
                store.add(
                    type="question",
                    period=period,
                    run_id=run_id,
                    label=f"{hid}:q",
                    value=question,
                    unit="USD",
                    provenance="inferred",
                )
        result = HypothesisResult(
            id=hid,
            leaf=leaf,
            cls=template.cls,
            claim=claim,
            prior=prior,
            posterior=posterior,
            verdict=verdict,
            hypothesis_node_id=h_node.id,
            verdict_node_id=v_node.id,
            previous=previous,
            updates=updates,
            question=question,
        )
        results.append(result)
        memory.upsert_open(
            {
                "id": hid,
                "leaf": leaf,
                "class": template.cls,
                "posterior": posterior,
                "verdict": verdict.label,
                "first_seen": period,
                "hypothesis_node": h_node.id,
                "verdict_node": v_node.id,
            }
        )
        if verdict.label in {"supported", "rejected"}:
            memory.close(hid, verdict.label, period)
        budget_left -= 1
        _ = i
    return results


def investigate(
    ranking: list[Any],
    *,
    store: GraphStore,
    period: str,
    run_id: str,
    memory: Memory,
    facts_by_leaf: dict[str, list[dict[str, Any]]],
    entity_by_leaf: dict[str, str],
    total_abs_delta: float,
    use_llm: bool,
    max_leaves: int = 6,
) -> Investigation:
    results: list[HypothesisResult] = []
    explained = 0.0
    budget = 12
    for item in ranking[:max_leaves]:
        leaf = item.leaf
        explained += abs(item.dollar_impact)
        results.extend(
            investigate_leaf(
                leaf=leaf,
                phi=item.dollar_impact,
                store=store,
                period=period,
                run_id=run_id,
                memory=memory,
                facts=facts_by_leaf.get(leaf, [{"label": "internal_variance", "tier": 1, "support": "neutral"}]),
                entity=entity_by_leaf.get(leaf),
                use_llm=use_llm,
                budget_left=budget,
            )
        )
        budget = max(0, 12 - len(results))
        if total_abs_delta and explained / total_abs_delta >= 0.85:
            break
    share = explained / total_abs_delta if total_abs_delta else 0.0
    return Investigation(results=results, explained_share=share)

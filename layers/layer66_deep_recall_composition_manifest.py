"""Layer 66 — Deep Recall post-freeze composition manifest.

Layer 65 freezes the evidence set. The next step should not be another retrieval
pass; it should convert the frozen evidence into a compact, deterministic
composition contract so the answer cannot forget supported stages or reintroduce
filtered residue.

This layer reads only the frozen packet and emits a manifest of final source IDs,
requested parts, supported/thin parts, presentation anchors, conflicts/gaps and
key fidelity guards. It does not add, remove or mutate evidence.
Ordinary Recall is unchanged.
"""
from hashlib import sha256
import json


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})

        frozen = rhee.safe_text(plan.get("deep_recall_evidence_freeze")).lower()
        source_ids = []
        seen = set()
        for item in evidence:
            source = rhee.safe_text(item.get("source")).strip()
            if source and source not in seen:
                source_ids.append(source)
                seen.add(source)

        represented_parts = list(
            plan.get("deep_recall_presentation_represented_parts")
            or plan.get("deep_recall_final_represented_parts")
            or []
        )
        frozen_source_set = set(source_ids)
        raw_part_sources = dict(plan.get("deep_recall_final_component_sources") or {})
        part_sources = {}
        part_evidence = {}
        for part in represented_parts:
            sources = []
            seen_part_sources = set()
            bindings = []
            seen_bindings = set()

            # Layers 70–71 bind coverage against the final frozen packet, not
            # only Layer 38's earlier reconciliation. This includes any valid
            # late contradiction-rescue evidence added before Layer 65 froze it.
            for item in evidence:
                source = rhee.safe_text(item.get("source")).strip()
                text = rhee.safe_text(item.get("quote_source"))
                if not source or source not in frozen_source_set or not text:
                    continue
                try:
                    score = rhee.calculate_raw_score(
                        {"content": text, "role": item.get("role", "unknown")},
                        part,
                    )
                except Exception:
                    score = 0
                if score <= 0:
                    continue

                if source not in seen_part_sources and len(sources) < 40:
                    sources.append(source)
                    seen_part_sources.add(source)

                fingerprint = sha256(text.encode("utf-8")).hexdigest()
                binding_key = (source, fingerprint)
                if binding_key not in seen_bindings and len(bindings) < 60:
                    bindings.append({
                        "source": source,
                        "excerpt_sha256": fingerprint,
                    })
                    seen_bindings.add(binding_key)

            # Preserve Layer 38's source receipt as a bounded fallback if the
            # scorer is unavailable during manifest construction. There is no
            # quote-level fallback: Layer 71 must fail closed if the final frozen
            # excerpt binding could not be reconstructed.
            if not sources:
                for source in raw_part_sources.get(part, []) or []:
                    source = rhee.safe_text(source).strip()
                    if (
                        source
                        and source in frozen_source_set
                        and source not in seen_part_sources
                    ):
                        sources.append(source)
                        seen_part_sources.add(source)
                    if len(sources) >= 40:
                        break

            part_sources[part] = sources
            part_evidence[part] = bindings

        query_sha256 = sha256(
            rhee.safe_text(query).encode("utf-8")
        ).hexdigest()

        evidence_packet_sha256 = sha256(
            json.dumps(
                evidence,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        manifest = {
            "freeze_state": frozen or "missing",
            "source_count": len(source_ids),
            "question_parts": list(plan.get("deep_recall_presentation_question_parts") or plan.get("deep_recall_question_parts") or []),
            "represented_parts": represented_parts,
            "part_sources": part_sources,
            "part_evidence": part_evidence,
            "thin_parts": list(plan.get("deep_recall_presentation_thin_parts") or plan.get("deep_recall_final_thin_parts") or []),
            "stage_anchors": list(plan.get("deep_recall_presentation_stage_anchors") or [])[:40],
            "conflict_cue_sources": list(plan.get("deep_recall_final_conflict_cue_sources") or [])[:30],
            "conflict_rescue_added": int(plan.get("deep_recall_conflict_targeted_added", 0) or 0),
            "operational_removed": int(plan.get("deep_recall_operational_residue_removed_count", 0) or 0),
            "excerpt_recovery": rhee.safe_text(plan.get("deep_recall_excerpt_recovery", "unknown")),
            "readiness": rhee.safe_text(plan.get("deep_recall_evidence_freeze_final_readiness", "unknown")),
            "source_ids": source_ids[:120],
            "query_sha256": query_sha256,
            "evidence_packet_sha256": evidence_packet_sha256,
        }
        manifest_sha256 = sha256(
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        manifest["manifest_sha256"] = manifest_sha256

        output = dict(result)
        plan.update({
            "deep_recall_composition_manifest": "created",
            "deep_recall_composition_manifest_version": 5,
            "deep_recall_composition_manifest_data": manifest,
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL POST-FREEZE COMPOSITION MANIFEST",
            f"Freeze={manifest['freeze_state']}; readiness={manifest['readiness']}; final sources={manifest['source_count']}; "
            f"represented parts={len(manifest['represented_parts'])}; thin parts={len(manifest['thin_parts'])}; "
            f"operational sources removed={manifest['operational_removed']}.",
            "The evidence set is frozen. This manifest is the final composition checklist, not a retrieval instruction.",
            "Layer 77 fingerprints the exact ordered frozen evidence packet and this composition manifest; publication must fail closed if either fingerprint changes.",
            "Layer 78 binds this frozen contract to the exact Deep Recall query that created it; a different query requires a fresh contract.",
            "Answer Doug's CURRENT question using only the frozen evidence packet.",
            "Present every material represented requested part; qualify candidate/partial details; name each genuine thin part once.",
            "Preserve exact event identity, chronology, negation/polarity, speaker attribution, plan-vs-outcome status, numbers/units/currency and source provenance.",
            "Do not reintroduce any operational/stale assistant material that was structurally filtered before freeze.",
            "Do not let a closing interpretation replace omitted evidence-supported stages.",
            "Keep sources close to the claims they support. A represented-part coverage claim is valid only when the answer block cites an exact passage from one of that part's frozen supporting evidence excerpts.",
            "Finish when the current question has been fully answered. Do not append historical assistant responses or internal diagnostics.",
        ]

        anchors = manifest["stage_anchors"]
        if anchors:
            lines.append(
                "Material repeated anchors available for silent coverage review: " +
                "; ".join(
                    f"{a.get('label')} x{a.get('count')}"
                    for a in anchors[:25]
                    if isinstance(a, dict)
                )
            )
        if manifest["thin_parts"]:
            lines.append(
                "Final thin requested parts: " +
                " | ".join(rhee.safe_text(x) for x in manifest["thin_parts"][:20])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

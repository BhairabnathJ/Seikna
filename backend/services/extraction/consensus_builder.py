"""
Consensus builder for merging claims, estimating agreement, and flagging contradictions.
"""
import math
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from core.ollama_client import ollama


class ConsensusBuilder:
    """Derives consensus claims and detects simple contradictions between claims."""

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        self.similarity_threshold = similarity_threshold

    def build_consensus(
        self, claims: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Cluster similar claims and mark obvious contradictions.

        Args:
            claims: List of claim dictionaries containing subject/predicate/object keys.

        Returns:
            Dict with consensus_claims and contradictions lists.
        """
        if not claims:
            return {"consensus_claims": [], "contradictions": []}

        enriched_claims = []
        for claim in claims:
            text = self._claim_text(claim)
            try:
                embedding = ollama.generate_embedding(text)
            except Exception as exc:  # pragma: no cover - external dependency
                # Fall back to a simple hashed embedding to keep processing resilient
                print(f"Embedding generation failed for claim {claim.get('claim_id')}: {exc}")
                embedding = self._fallback_embedding(text)

            enriched_claims.append({**claim, "embedding": embedding})

        clusters: List[List[Dict[str, Any]]] = []

        for claim in enriched_claims:
            added = False
            for cluster in clusters:
                similarity = self._similarity(claim["embedding"], self._cluster_centroid(cluster))
                if similarity >= self.similarity_threshold:
                    cluster.append(claim)
                    added = True
                    break
            if not added:
                clusters.append([claim])

        consensus_claims: List[Dict[str, Any]] = []
        for cluster in clusters:
            consensus_claims.append(self._build_consensus_claim(cluster))

        contradictions = self._detect_contradictions(enriched_claims)

        return {"consensus_claims": consensus_claims, "contradictions": contradictions}

    def _claim_text(self, claim: Dict[str, Any]) -> str:
        return f"{claim.get('subject', '')} {claim.get('predicate', '')} {claim.get('object', '')}".strip()

    def _fallback_embedding(self, text: str) -> List[float]:
        # Simple deterministic embedding using character codes
        values = [float(ord(c) % 31) for c in text][:128]
        if not values:
            values = [0.0]
        return values

    def _similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        length = min(len(vec_a), len(vec_b))
        a = vec_a[:length]
        b = vec_b[:length]
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _cluster_centroid(self, cluster: List[Dict[str, Any]]) -> List[float]:
        if not cluster:
            return []
        max_len = max(len(claim["embedding"]) for claim in cluster)
        centroid = [0.0] * max_len
        for claim in cluster:
            emb = claim["embedding"]
            for i, val in enumerate(emb[:max_len]):
                centroid[i] += val
        return [val / len(cluster) for val in centroid]

    def _build_consensus_claim(self, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        primary = cluster[0]
        support_ids = [claim["claim_id"] for claim in cluster]
        support_sources = list({claim.get("source_id") for claim in cluster if claim.get("source_id")})
        confidence = sum(float(claim.get("confidence", 0.8)) for claim in cluster) / max(1, len(cluster))

        return {
            "consensus_id": f"cons_{uuid.uuid4().hex[:12]}",
            "subject": primary.get("subject", ""),
            "predicate": primary.get("predicate", ""),
            "object": primary.get("object", ""),
            "support_claim_ids": support_ids,
            "support_sources": support_sources,
            "support_count": len(cluster),
            "confidence": min(1.0, confidence),
        }

    def _detect_contradictions(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        contradictions: List[Dict[str, Any]] = []
        seen_pairs: set[Tuple[str, str]] = set()

        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for claim in claims:
            key = (claim.get("subject", "").lower(), claim.get("predicate", "").lower())
            grouped[key].append(claim)

        for (subject, predicate), group in grouped.items():
            for i, claim_a in enumerate(group):
                for claim_b in group[i + 1 :]:
                    pair_key = tuple(sorted([claim_a["claim_id"], claim_b["claim_id"]]))
                    if pair_key in seen_pairs:
                        continue
                    if self._is_contradictory(claim_a, claim_b):
                        contradictions.append(
                            {
                                "contradiction_id": f"contr_{uuid.uuid4().hex[:12]}",
                                "claim_id_1": claim_a["claim_id"],
                                "claim_id_2": claim_b["claim_id"],
                                "reasoning": f"Conflicting objects for '{subject} {predicate}'.",
                            }
                        )
                        seen_pairs.add(pair_key)

        return contradictions

    def _is_contradictory(self, claim_a: Dict[str, Any], claim_b: Dict[str, Any]) -> bool:
        obj_a = str(claim_a.get("object", "")).lower()
        obj_b = str(claim_b.get("object", "")).lower()
        if obj_a == obj_b:
            return False

        neg_markers = ["not ", "no ", "false", "never", "none"]
        a_neg = any(marker in obj_a for marker in neg_markers)
        b_neg = any(marker in obj_b for marker in neg_markers)

        return (a_neg and not b_neg) or (b_neg and not a_neg)


consensus_builder = ConsensusBuilder()

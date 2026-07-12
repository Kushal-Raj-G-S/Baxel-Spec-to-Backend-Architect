import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class SemanticClusteringWrapper:
    """
    Wrapper for semantic clustering of synonymous entities/actors.
    Uses the shared CloudEmbedder (Nvidia NIM API) instead of loading
    local SentenceTransformer weights, eliminating the ~10s disk-read cost.
    Falls back to string-similarity if the cloud embedder is unavailable.
    """

    def __init__(self):
        self.initialized = False
        self._init_attempted = False

    def initialize(self):
        if self._init_attempted:
            return
        self._init_attempted = True
        try:
            from app.services.nlp.cloud_embedder import cloud_embedder
            cloud_embedder.initialize()
            self._embedder = cloud_embedder
            self.initialized = cloud_embedder.initialized
            if self.initialized:
                logger.info("SemanticClustering: CloudEmbedder ready.")
            else:
                logger.warning(
                    "SemanticClustering: CloudEmbedder not ready — "
                    "falling back to string similarity."
                )
        except Exception as e:
            logger.warning(
                f"SemanticClustering: failed to load CloudEmbedder: {e}. "
                "Falling back to string similarity."
            )
            self.initialized = False

    def merge_synonyms(self, entities: List[str]) -> List[str]:
        """
        Merge synonym actors/entities (e.g. ['Owner', 'CEO', 'Customer', 'Client'])
        into canonical names using embeddings and cosine similarity via Faiss.
        """
        if not entities:
            return []

        if not self._init_attempted:
            self.initialize()

        if self.initialized:
            try:
                import numpy as np
                import faiss

                # Clean list
                entities = list(set([e.strip() for e in entities if e.strip()]))
                if len(entities) <= 1:
                    return entities

                # Generate embeddings via cloud API
                embeddings = self._embedder.encode(entities)
                embeddings = embeddings.astype("float32")

                # Normalize embeddings for cosine similarity
                faiss.normalize_L2(embeddings)

                # Build index
                dimension = embeddings.shape[1]
                index = faiss.IndexFlatIP(dimension)
                index.add(embeddings)

                # Search nearest neighbors
                k = min(5, len(entities))
                D, I = index.search(embeddings, k)

                canonical_map = {}
                visited = set()

                for idx, entity in enumerate(entities):
                    if entity in visited:
                        continue
                    group = [entity]
                    visited.add(entity)
                    for neighbor_rank in range(1, k):
                        neighbor_idx = I[idx][neighbor_rank]
                        similarity = D[idx][neighbor_rank]
                        neighbor_entity = entities[neighbor_idx]
                        if similarity > 0.80 and neighbor_entity not in visited:
                            group.append(neighbor_entity)
                            visited.add(neighbor_entity)

                    # Representative canonical name (shortest in group)
                    canonical_name = min(group, key=len)
                    for item in group:
                        canonical_map[item] = canonical_name

                return list(set(canonical_map.values()))
            except Exception as e:
                logger.error(f"Error during semantic clustering: {e}")

        # String-similarity fallback
        entities = list(set([e.strip() for e in entities if e.strip()]))
        canonical_map = {}
        visited = set()

        for idx, e1 in enumerate(entities):
            if e1 in visited:
                continue
            group = [e1]
            visited.add(e1)
            for e2 in entities[idx + 1:]:
                if e2 in visited:
                    continue
                if e1.lower() in e2.lower() or e2.lower() in e1.lower():
                    group.append(e2)
                    visited.add(e2)
            rep = min(group, key=len)
            for item in group:
                canonical_map[item] = rep

        return list(set(canonical_map.values()))


semantic_clustering = SemanticClusteringWrapper()

import logging
from typing import List, Dict, Any
from app.services.rag.blueprints import BLUEPRINTS

logger = logging.getLogger(__name__)


class RAGBlueprintRetriever:
    """
    Retrieval-Augmented Generation (RAG) system for design blueprints.
    Indexes blueprints dynamically via Faiss + CloudEmbedder (Nvidia NIM API),
    supporting top-K merging, relevance thresholds, and graceful fallbacks.
    Replaces the local SentenceTransformer model load with a cloud API call,
    eliminating the ~10s model weight materialization cost per request.
    """

    def __init__(self):
        self.index = None
        self.texts = []
        self.embeddings = None
        self.initialized = False
        self._init_attempted = False
        self.min_similarity_score = 0.60

    def initialize(self):
        # Only attempt once per process
        if self._init_attempted:
            return
        self._init_attempted = True
        try:
            from app.services.nlp.cloud_embedder import cloud_embedder
            import faiss
            import numpy as np

            cloud_embedder.initialize()
            if not cloud_embedder.initialized:
                logger.warning(
                    "RAGRetriever: CloudEmbedder not ready — "
                    "falling back to token-based lookup."
                )
                return

            # Prepare search texts: archetype + rules concatenated
            self.texts = []
            for bp in BLUEPRINTS:
                text = f"Archetype: {bp['archetype']}. Rules: {' '.join(bp['rules'])}"
                self.texts.append(text)

            # Embed all blueprints via cloud API (single batch call)
            self.embeddings = cloud_embedder.encode(self.texts).astype("float32")

            # Normalize for cosine similarity
            faiss.normalize_L2(self.embeddings)

            # Flat Inner Product index for cosine similarity
            dimension = self.embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(self.embeddings)

            self._cloud_embedder = cloud_embedder
            self.initialized = True
            logger.info(
                f"RAG Vector DB initialized via CloudEmbedder "
                f"with {len(BLUEPRINTS)} design blueprints."
            )
        except Exception as e:
            logger.warning(
                f"Failed to initialize vector index for RAG: {e}. "
                "Falling back to token-based lookup."
            )
            self.initialized = False

    async def retrieve_blueprints(self, prompt: str, top_k: int = 2) -> Dict[str, Any]:
        """
        Retrieves matching blueprints using vector search, filters by threshold,
        and returns a merged list of rules/anti-patterns.
        """
        if not self.initialized:
            self.initialize()

        if self.initialized and self.index:
            try:
                import numpy as np
                import faiss

                # Embed query via cloud API
                query_vector = self._cloud_embedder.encode([prompt]).astype("float32")
                faiss.normalize_L2(query_vector)

                # Search nearest blueprints
                D, I = self.index.search(query_vector, top_k)

                matched = []
                for score, idx in zip(D[0], I[0]):
                    if score >= self.min_similarity_score:
                        matched.append((BLUEPRINTS[idx], score))

                if not matched:
                    logger.info(
                        f"No blueprints cleared similarity threshold of "
                        f"{self.min_similarity_score}. Falling back to General SaaS."
                    )
                    general_saas = next(
                        bp for bp in BLUEPRINTS if bp["archetype"] == "General SaaS"
                    )
                    return {
                        "archetype": "General SaaS",
                        "rules": general_saas["rules"],
                        "anti_patterns": general_saas["anti_patterns"],
                        "recommended_stack": general_saas["recommended_stack"],
                    }

                # Merge multi-archetype constraints (Top-K hybrid prompts)
                primary = matched[0][0]
                merged_rules = []
                merged_anti_patterns = []

                for bp, _ in matched:
                    merged_rules.extend(bp["rules"])
                    merged_anti_patterns.extend(bp["anti_patterns"])

                merged_rules = list(set(merged_rules))
                merged_anti_patterns = list(set(merged_anti_patterns))

                archetype_name = (
                    " + ".join([bp["archetype"] for bp, _ in matched])
                    if len(matched) > 1
                    else primary["archetype"]
                )

                return {
                    "archetype": archetype_name,
                    "rules": merged_rules,
                    "anti_patterns": merged_anti_patterns,
                    "recommended_stack": primary["recommended_stack"],
                }
            except Exception as e:
                logger.error(f"Error during RAG vector retrieval: {e}")

        # String-matching fallback for headless/offline environments
        prompt_lower = prompt.lower()
        matched = []

        for bp in BLUEPRINTS:
            archetype_words = (
                bp["archetype"].lower().replace("&", "").replace("-", " ").split()
            )
            match_score = sum(1 for word in archetype_words if word in prompt_lower)
            if match_score > 0 and bp["archetype"] != "General SaaS":
                matched.append((bp, match_score))

        matched.sort(key=lambda x: x[1], reverse=True)

        if not matched:
            general_saas = next(bp for bp in BLUEPRINTS if bp["archetype"] == "General SaaS")
            return {
                "archetype": "General SaaS",
                "rules": general_saas["rules"],
                "anti_patterns": general_saas["anti_patterns"],
                "recommended_stack": general_saas["recommended_stack"],
            }

        top_matched = matched[:top_k]
        primary = top_matched[0][0]
        merged_rules = []
        merged_anti_patterns = []

        for bp, _ in top_matched:
            merged_rules.extend(bp["rules"])
            merged_anti_patterns.extend(bp["anti_patterns"])

        merged_rules = list(set(merged_rules))
        merged_anti_patterns = list(set(merged_anti_patterns))

        archetype_name = (
            " + ".join([bp["archetype"] for bp, _ in top_matched])
            if len(top_matched) > 1
            else primary["archetype"]
        )

        return {
            "archetype": archetype_name,
            "rules": merged_rules,
            "anti_patterns": merged_anti_patterns,
            "recommended_stack": primary["recommended_stack"],
        }


rag_retriever = RAGBlueprintRetriever()

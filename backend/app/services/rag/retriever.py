import logging
from typing import List, Dict, Any
from app.services.rag.blueprints import BLUEPRINTS

logger = logging.getLogger(__name__)

class RAGBlueprintRetriever:
    """
    Retrieval-Augmented Generation (RAG) system for design blueprints.
    Indexes blueprints dynamically via Faiss + SentenceTransformer,
    supporting top-K merging, relevance thresholds, and graceful fallbacks.
    """
    def __init__(self):
        self.encoder = None
        self.index = None
        self.texts = []
        self.initialized = False
        self.min_similarity_score = 0.60
        
    def initialize(self):
        try:
            from sentence_transformers import SentenceTransformer
            import faiss
            import numpy as np
            
            # Initialize the same lightweight BGE model (120MB) to conserve space/memory
            self.encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")
            
            # Prepare search text by concatenating archetype and rules
            self.texts = []
            for bp in BLUEPRINTS:
                text = f"Archetype: {bp['archetype']}. Rules: {' '.join(bp['rules'])}"
                self.texts.append(text)
                
            # Embed all blueprints
            embeddings = self.encoder.encode(self.texts)
            self.embeddings = np.array(embeddings).astype('float32')
            
            # Normalize for cosine similarity calculation
            faiss.normalize_L2(self.embeddings)
            
            # Flat Inner Product index for cosine similarity
            dimension = self.embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(self.embeddings)
            
            self.initialized = True
            logger.info("RAG Vector DB successfully initialized with 10 design blueprints.")
        except Exception as e:
            logger.warning(f"Failed to initialize vector index for RAG: {e}. Falling back to token-based lookup.")
            self.initialized = False

    async def retrieve_blueprints(self, prompt: str, top_k: int = 2) -> Dict[str, Any]:
        """
        Retrieves matching blueprints using vector search, filters by threshold,
        and returns a merged list of rules/anti-patterns.
        """
        if not self.initialized:
            self.initialize()
            
        if self.initialized and self.index and self.encoder:
            try:
                import numpy as np
                import faiss
                
                # Embed query
                query_vector = self.encoder.encode([prompt])
                query_vector = np.array(query_vector).astype('float32')
                faiss.normalize_L2(query_vector)
                
                # Search nearest blueprints
                D, I = self.index.search(query_vector, top_k)
                
                matched = []
                for score, idx in zip(D[0], I[0]):
                    if score >= self.min_similarity_score:
                        matched.append((BLUEPRINTS[idx], score))
                        
                if not matched:
                    logger.info(f"No blueprints cleared similarity threshold of {self.min_similarity_score}. Falling back to General SaaS.")
                    general_saas = next(bp for bp in BLUEPRINTS if bp["archetype"] == "General SaaS")
                    return {
                        "archetype": "General SaaS",
                        "rules": general_saas["rules"],
                        "anti_patterns": general_saas["anti_patterns"],
                        "recommended_stack": general_saas["recommended_stack"]
                    }
                
                # Merge multi-archetype constraints (Top-K hybrid prompts)
                primary = matched[0][0]
                merged_rules = []
                merged_anti_patterns = []
                
                for bp, _ in matched:
                    merged_rules.extend(bp["rules"])
                    merged_anti_patterns.extend(bp["anti_patterns"])
                    
                # De-duplicate
                merged_rules = list(set(merged_rules))
                merged_anti_patterns = list(set(merged_anti_patterns))
                
                # Construct combined archetype name if multiple matched
                if len(matched) > 1:
                    archetype_name = " + ".join([bp["archetype"] for bp, _ in matched])
                else:
                    archetype_name = primary["archetype"]
                    
                return {
                    "archetype": archetype_name,
                    "rules": merged_rules,
                    "anti_patterns": merged_anti_patterns,
                    "recommended_stack": primary["recommended_stack"]
                }
            except Exception as e:
                logger.error(f"Error during RAG vector retrieval: {e}")
                
        # String-matching fallback for headless/offline environments
        prompt_lower = prompt.lower()
        matched = []
        
        for bp in BLUEPRINTS:
            archetype_words = bp["archetype"].lower().replace("&", "").replace("-", " ").split()
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
                "recommended_stack": general_saas["recommended_stack"]
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
        
        if len(top_matched) > 1:
            archetype_name = " + ".join([bp["archetype"] for bp, _ in top_matched])
        else:
            archetype_name = primary["archetype"]
            
        return {
            "archetype": archetype_name,
            "rules": merged_rules,
            "anti_patterns": merged_anti_patterns,
            "recommended_stack": primary["recommended_stack"]
        }

rag_retriever = RAGBlueprintRetriever()

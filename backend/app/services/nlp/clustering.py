import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SemanticClusteringWrapper:
    """
    Wrapper for semantic clustering of synonymous entities/actors
    using sentence-transformers embeddings and Faiss index.
    """
    def __init__(self):
        self.encoder = None
        self.initialized = False
        
    def initialize(self):
        try:
            from sentence_transformers import SentenceTransformer
            # Using a lightweight, high-performance BGE model (120MB) 
            # to respect container limits while executing BGE-family embeddings
            self.encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")
            self.initialized = True
            logger.info("SentenceTransformer successfully initialized for clustering.")
        except Exception as e:
            logger.warning(f"Failed to initialize SentenceTransformer: {e}. Falling back to string similarity.")
            self.initialized = False

    def merge_synonyms(self, entities: List[str]) -> List[str]:
        """
        Merge synonym actors/entities (e.g. ['Owner', 'CEO', 'Customer', 'Client']) 
        into canonical names using embeddings and cosine similarity via Faiss.
        """
        if not entities:
            return []
            
        if not self.initialized:
            self.initialize()
            
        if self.initialized and self.encoder:
            try:
                import numpy as np
                import faiss
                
                # Clean list
                entities = list(set([e.strip() for e in entities if e.strip()]))
                if len(entities) <= 1:
                    return entities
                    
                # Generate embeddings
                embeddings = self.encoder.encode(entities)
                embeddings = np.array(embeddings).astype('float32')
                
                # Normalize embeddings for cosine similarity
                faiss.normalize_L2(embeddings)
                
                # Build index
                dimension = embeddings.shape[1]
                index = faiss.IndexFlatIP(dimension)  # Inner Product on normalized vectors = Cosine Similarity
                index.add(embeddings)
                
                # Search nearest neighbors
                k = min(5, len(entities))
                D, I = index.search(embeddings, k)
                
                canonical_map = {}
                visited = set()
                
                for idx, entity in enumerate(entities):
                    if entity in visited:
                        continue
                    # Group duplicates based on similarity threshold (>= 0.8)
                    group = [entity]
                    visited.add(entity)
                    for neighbor_rank in range(1, k):
                        neighbor_idx = I[idx][neighbor_rank]
                        similarity = D[idx][neighbor_rank]
                        neighbor_entity = entities[neighbor_idx]
                        if similarity > 0.80 and neighbor_entity not in visited:
                            group.append(neighbor_entity)
                            visited.add(neighbor_entity)
                    
                    # Representative canonical name (e.g., shortest or most common name)
                    canonical_name = min(group, key=len)
                    for item in group:
                        canonical_map[item] = canonical_name
                
                return list(set(canonical_map.values()))
            except Exception as e:
                logger.error(f"Error during semantic clustering: {e}")
                
        # Simple string-similarity fallback if dependencies are missing
        entities = list(set([e.strip() for e in entities if e.strip()]))
        canonical_map = {}
        visited = set()
        
        for idx, e1 in enumerate(entities):
            if e1 in visited:
                continue
            group = [e1]
            visited.add(e1)
            for e2 in entities[idx+1:]:
                if e2 in visited:
                    continue
                # If substring match exists
                if e1.lower() in e2.lower() or e2.lower() in e1.lower():
                    group.append(e2)
                    visited.add(e2)
            rep = min(group, key=len)
            for item in group:
                canonical_map[item] = rep
                
        return list(set(canonical_map.values()))

semantic_clustering = SemanticClusteringWrapper()

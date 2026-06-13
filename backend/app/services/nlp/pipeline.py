import asyncio
import logging
from typing import Tuple, Dict, Any, List
from app.schemas.spec import IntermediateRepresentation
from app.services.nlp.router import semantic_router
from app.services.nlp.entity_extractor import gliner_extractor
from app.services.nlp.clustering import semantic_clustering
from app.services.nlp.implication_map import get_implied_integrations

logger = logging.getLogger(__name__)

async def run_entity_processing_flow(prompt: str) -> Dict[str, List[str]]:
    """
    Flow A (Entity Processing Pipeline):
    Runs GLiNER extraction, maps synonyms using SentenceTransformer + Faiss,
    and enriches entities using the Implication Map.
    """
    logger.info("Starting Flow A: Entity processing...")
    # Run GLiNER (CPU-bound / I/O-bound depending on environment, wrapped in async)
    loop = asyncio.get_running_loop()
    raw_extracted = await loop.run_in_executor(None, gliner_extractor.extract_entities, prompt)
    
    # Merge synonym actors and entities (CPU-bound Faiss operations)
    canonical_actors = await loop.run_in_executor(None, semantic_clustering.merge_synonyms, raw_extracted["actors"])
    canonical_entities = await loop.run_in_executor(None, semantic_clustering.merge_synonyms, raw_extracted["entities"])
    
    # Extract integrations and check implication map
    raw_integrations = raw_extracted.get("integrations", [])
    implied_integrations = get_implied_integrations(canonical_entities + canonical_actors + raw_integrations)
    combined_integrations = list(set(raw_integrations + implied_integrations))
    
    logger.info("Flow A completed successfully.")
    return {
        "actors": canonical_actors,
        "entities": canonical_entities,
        "implied_integrations": combined_integrations
    }

async def run_archetype_retrieval_flow(prompt: str) -> Dict[str, Any]:
    """
    Flow B (Architectural Retrieval Pipeline):
    Classifies the system archetype and queries Vector DB blueprints.
    """
    logger.info("Starting Flow B: Archetype retrieval...")
    # Import locally to prevent circular dependencies
    from app.services.rag.retriever import rag_retriever
    
    result = await rag_retriever.retrieve_blueprints(prompt)
    logger.info("Flow B completed successfully.")
    return result

async def run_nlp_pipeline(prompt: str) -> Tuple[IntermediateRepresentation, float, List[str], str]:
    """
    Main Phase 1 NLP pipeline executing Flow A and Flow B in parallel.
    
    Returns:
        Tuple[IntermediateRepresentation, float, List[str], str]: 
            (IR, router_confidence_score, retrieved_rules_list, generation_status)
    """
    # 1. Semantic Router Sequential Intent Check
    route_name, confidence_score = semantic_router.route(prompt)
    
    if route_name == "chitchat":
        raise ValueError(
            "Prompt rejected: The request does not describe a valid software architecture or system specification."
        )
        
    status = "complete"
    if route_name == "LOW_CONFIDENCE":
        status = "partial"
        logger.warning(f"Low confidence prompt routed. Score: {confidence_score}")
        
    # 2. Concurrency Block: Run Flow A and Flow B in parallel
    flow_a_task = run_entity_processing_flow(prompt)
    flow_b_task = run_archetype_retrieval_flow(prompt)
    
    entity_results, rag_results = await asyncio.gather(flow_a_task, flow_b_task)
    
    # 3. Compile the Intermediate Representation (IR)
    ir = IntermediateRepresentation(
        actors=entity_results["actors"],
        entities=entity_results["entities"],
        implied_integrations=entity_results["implied_integrations"],
        archetype=rag_results["archetype"]
    )
    
    rules = rag_results["rules"]
    
    return ir, confidence_score, rules, status

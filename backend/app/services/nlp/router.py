import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class SemanticRouterWrapper:
    """
    Wrapper for Aurelio AI's semantic-router.
    Provides fallback mechanisms if dependencies or model files cannot be loaded.
    """
    def __init__(self):
        self.route_layer = None
        self.initialized = False
        
    def initialize(self):
        try:
            from semantic_router import Route
            from semantic_router.encoders import HuggingFaceEncoder
            try:
                from semantic_router import RouteLayer
            except ImportError:
                from semantic_router import SemanticRouter as RouteLayer
            
            spec_route = Route(
                name="software_spec",
                utterances=[
                    "create a database schema for e-commerce",
                    "build a backend API for a ridesharing application",
                    "need a system architecture for real-time multiplayer game",
                    "design a microservices system for inventory tracking",
                    "I want a nextjs and fastapi web app spec",
                    "design a video streaming platform backend"
                ]
            )
            
            # Use a tiny fast encoder to keep latency down
            encoder = HuggingFaceEncoder(name="sentence-transformers/all-MiniLM-L6-v2")
            self.route_layer = RouteLayer(encoder=encoder, routes=[spec_route])
            self.initialized = True
            logger.info("Semantic Router successfully initialized with HuggingFaceEncoder.")
        except Exception as e:
            logger.warning(f"Failed to initialize semantic-router library: {e}. Falling back to keyword-based routing.")
            self.initialized = False

    def route(self, prompt: str) -> Tuple[str, float]:
        """
        Routes the prompt. 
        Returns:
            Tuple[str, float]: (route_name, confidence_score)
            route_name can be "software_spec", "LOW_CONFIDENCE", or "chitchat".
        """
        if not self.initialized:
            self.initialize()
            
        if self.initialized and self.route_layer:
            try:
                # Run query
                result = self.route_layer(prompt)
                name = result.name if result.name else "chitchat"
                score = result.score if result.score is not None else 0.0
                
                if name == "software_spec":
                    if score >= 0.7:
                        return "software_spec", score
                    elif score >= 0.4:
                        return "LOW_CONFIDENCE", score
                    else:
                        return "chitchat", score
                return "chitchat", score
            except Exception as e:
                logger.error(f"Error during semantic routing execution: {e}")
                
        # Robust keyword-based fallback router
        prompt_lower = prompt.lower()
        tech_words = {"build", "create", "api", "backend", "database", "schema", "app", "system", "architecture", "microservice", "server", "postgres", "sql", "mongodb", "endpoint"}
        matched = [word for word in tech_words if word in prompt_lower]
        
        # Check informal or short prompts
        words_count = len(prompt.split())
        if len(matched) >= 3:
            return "software_spec", 0.8
        elif len(matched) >= 1 or (words_count > 5 and any(kw in prompt_lower for kw in ["like", "clone", "for"])):
            # "idk maybe something like Uber but for dogs lol" matches here
            return "LOW_CONFIDENCE", 0.5
        else:
            return "chitchat", 0.2

semantic_router = SemanticRouterWrapper()

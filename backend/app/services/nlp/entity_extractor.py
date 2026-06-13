import logging
import re
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class GLiNERWrapper:
    """
    Wrapper for URCHADE's GLiNER entity extraction.
    Provides rule-based fallbacks if GLiNER library or weights fail to load.
    """
    def __init__(self):
        self.model = None
        self.initialized = False
        
    def initialize(self):
        try:
            from gliner import GLiNER
            # Load the local gliner_small model if available
            local_path = Path(__file__).resolve().parents[3] / "models" / "gliner_small"
            if local_path.exists() and (local_path / "pytorch_model.bin").exists():
                logger.info(f"Loading GLiNER model from local directory: {local_path}")
                self.model = GLiNER.from_pretrained(str(local_path.resolve()), local_files_only=True)
            else:
                logger.warning(f"Local GLiNER directory not found at {local_path}. Trying online fallback...")
                self.model = GLiNER.from_pretrained("gliner-community/gliner_small-v2.5")
            self.initialized = True
            logger.info("GLiNER successfully initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize GLiNER library: {e}. Falling back to rule-based/LLM extraction.")
            self.initialized = False

    def extract_entities(self, prompt: str) -> Dict[str, List[str]]:
        """
        Extracts actors, entities, and services.
        Returns:
            Dict[str, List[str]]: {"actors": [...], "entities": [...], "integrations": [...]}
        """
        # 1. Try LLM-based extraction first to ensure high-fidelity domain entities
        llm_result = self.extract_entities_llm(prompt)
        if llm_result:
            logger.info("Using LLM-based entity extraction for high-quality specifications.")
            return llm_result

        if not self.initialized:
            self.initialize()
            
        labels = ["actor", "entity", "database_table", "external_api", "service"]
        
        if self.initialized and self.model:
            try:
                # Predict entities
                entities = self.model.predict_entities(prompt, labels, threshold=0.4)
                
                result = {"actors": [], "entities": [], "integrations": []}
                for entity in entities:
                    label = entity["label"]
                    text = entity["text"].strip()
                    if label == "actor":
                        result["actors"].append(text)
                    elif label in ("database_table", "entity"):
                        result["entities"].append(text)
                    elif label in ("external_api", "service"):
                        result["integrations"].append(text)
                        
                # Clean and deduplicate
                for k in result:
                    result[k] = list(set([t.title() for t in result[k]]))
                logger.info("Using GLiNER-based fallback entity extraction.")
                return result
            except Exception as e:
                logger.error(f"Error during GLiNER prediction: {e}")
                
        # Smart LLM-based Fallback (First Priority if GLiNER fails)
        llm_result = self.extract_entities_llm(prompt)
        if llm_result:
            return llm_result
                
        # Simple Rule-based Fallback
        result = {"actors": [], "entities": [], "integrations": []}
        
        # Regex for common actors ("as an admin", "buyer uploads", etc.)
        actors_patterns = [
            r"(?:as\s+an?|for)\s+([a-zA-Z\-_]+)",
            r"([a-zA-Z\-_]+)\s+can\s+",
            r"([a-zA-Z\-_]+)\s+roles?"
        ]
        for pattern in actors_patterns:
            for match in re.finditer(pattern, prompt, re.IGNORECASE):
                word = match.group(1).lower().strip()
                if word not in ("he", "she", "they", "user", "someone", "system", "app", "application", "client", "customer"):
                    result["actors"].append(word.capitalize())
                    
        # Common database entities
        entity_keywords = {
            "user", "profile", "account", "product", "order", "invoice", "payment",
            "message", "chat", "video", "item", "cart", "token", "subscription",
            "device", "notification", "transaction", "ledger", "audit"
        }
        for word in prompt.lower().split():
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in entity_keywords:
                result["entities"].append(clean_word.capitalize())
            elif clean_word.endswith("s") and clean_word[:-1] in entity_keywords:
                result["entities"].append(clean_word[:-1].capitalize())
                
        # Integrations
        integration_keywords = {
            "stripe", "paypal", "auth0", "sendgrid", "aws", "s3", "redis", "postgres", 
            "mongodb", "rabbitmq", "celery", "google", "facebook", "github"
        }
        for word in prompt.lower().split():
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in integration_keywords:
                result["integrations"].append(clean_word.upper() if clean_word in ("aws", "s3") else clean_word.capitalize())

        # Clean and deduplicate
        for k in result:
            result[k] = list(set(result[k]))
            
        # Defaults if fallback found nothing
        if not result["actors"]:
            result["actors"] = ["User"]
        if not result["entities"]:
            result["entities"] = ["User", "Session"]
            
        return result

    def extract_entities_llm(self, prompt: str) -> Dict[str, List[str]]:
        try:
            from app.services.agents.generation import _load_api_key, LLM_BASE_URL, LLM_MODEL
            from openai import OpenAI
            import json
            
            api_key = _load_api_key()
            if not api_key:
                return None
                
            client = OpenAI(api_key=api_key, base_url=LLM_BASE_URL)
            system_content = (
                "You are an NLP entity extraction assistant. Analyze the user's software product description. "
                "Extract the key data entities (nouns that represent database tables, e.g., 'Rover', 'MicrobialSample'), "
                "user roles/actors (e.g., 'Scientist', 'Operator'), and external services/APIs/integrations (e.g., 'Stripe', 'Ledger'). "
                "Output a raw JSON object with keys: 'actors' (list of strings), 'entities' (list of strings), and 'integrations' (list of strings). "
                "Keep entity names singular and clean. Output ONLY raw JSON."
            )
            
            completion = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": f"Product description: {prompt}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            raw = completion.choices[0].message.content
            if not raw:
                return None
                
            text = raw.strip()
            if text.startswith("```"):
                first_newline = text.find("\n")
                if first_newline != -1:
                    text = text[first_newline:].strip()
                if text.endswith("```"):
                    text = text[:-3].strip()
                    
            parsed = json.loads(text)
            result = {"actors": [], "entities": [], "integrations": []}
            
            for k in ("actors", "entities", "integrations"):
                if k in parsed and isinstance(parsed[k], list):
                    result[k] = [str(item).strip().title() for item in parsed[k]]
                    
            for k in result:
                result[k] = list(set(result[k]))
                
            return result
        except Exception as e:
            logger.warning(f"LLM-based entity extraction fallback failed: {e}. Using regex/rule-based fallback.")
            return None

gliner_extractor = GLiNERWrapper()

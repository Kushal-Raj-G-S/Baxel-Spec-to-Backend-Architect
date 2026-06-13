from typing import List, Dict

# Hardcoded domain implication map to enrich the GLiNER extracted entities
# with implied technical requirements before vector blueprint retrieval.
IMPLICATION_MAP: Dict[str, List[str]] = {
    "credit_card": ["stripe_integration", "webhook_endpoint", "idempotency_keys"],
    "payment": ["stripe_integration", "webhook_endpoint", "idempotency_keys"],
    "billing": ["stripe_integration", "webhook_endpoint", "idempotency_keys"],
    "video_upload": ["message_broker", "cdn", "transcoding_pipeline"],
    "video": ["message_broker", "cdn", "transcoding_pipeline"],
    "chat": ["websockets", "redis_pubsub", "message_history"],
    "message": ["websockets", "redis_pubsub", "message_history"],
    "auth": ["jwt_authentication", "password_hashing", "user_persistence"],
    "search": ["elasticsearch", "full_text_search_index"],
    "notification": ["sendgrid_integration", "email_queue", "background_worker"],
    "file_upload": ["s3_storage", "presigned_urls", "cdn_caching"],
    "analytics": ["time_series_db", "metric_aggregation", "event_stream"]
}

def get_implied_integrations(entities: List[str]) -> List[str]:
    """
    Given a list of extracted raw entities, check the implication map
    and return unique implied architectural integrations.
    """
    implied = set()
    for entity in entities:
        # Normalize to lower case and check substring/exact match
        normalized = entity.lower().strip().replace(" ", "_")
        for key, implications in IMPLICATION_MAP.items():
            if key in normalized:
                implied.update(implications)
    return list(implied)

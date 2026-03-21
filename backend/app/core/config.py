import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase_db_url = os.getenv("SUPABASE_DB_URL", "")
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
        self.auth_enabled = os.getenv("AUTH_ENABLED", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.allowed_origins = [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        ]


settings = Settings()

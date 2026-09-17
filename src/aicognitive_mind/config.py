from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Cognitive Mind"
    storage_provider: str = "surreal"
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "ai_cognitive_mind"
    surrealdb_uri: str = "surrealkv://.surreal/cognitive_mind"
    surrealdb_namespace: str = "mir_ai"
    surrealdb_database: str = "ai_cognitive_mind"
    surrealdb_username: str | None = None
    surrealdb_password: str | None = None
    reasoning_provider: str = "ollama"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2:3b"
    admin_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

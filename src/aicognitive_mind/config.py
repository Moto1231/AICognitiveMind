from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Cognitive Mind"
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "ai_cognitive_mind"
    reasoning_provider: str = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:1.7b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Cognitive Mind"
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "ai_cognitive_mind"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_models: str = ""
    admin_pin: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def openai_model_options(self) -> tuple[str, ...]:
        configured = [
            item.strip()
            for item in self.openai_models.split(",")
            if item.strip()
        ]
        models = [self.openai_model, *configured]
        return tuple(dict.fromkeys(models))


@lru_cache
def get_settings() -> Settings:
    return Settings()

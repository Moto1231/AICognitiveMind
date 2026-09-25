# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from functools import lru_cache

from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Axiom"
    storage_provider: str = "surreal"
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "ai_cognitive_mind"
    surrealdb_uri: str = "surrealkv://.surreal/cognitive_mind"
    surrealdb_namespace: str = "mir_ai"
    surrealdb_database: str = "ai_cognitive_mind"
    surrealdb_username: str | None = None
    surrealdb_password: str | None = None
    surrealdb_auth_level: str = "database"

    # Axiom's primary reasoning architecture is an external host using MCP.
    # This provider exists only so the Body/API can operate when no external
    # host is actively driving cognition. REASONING_PROVIDER remains a
    # backwards-compatible environment setting for existing deployments.
    standalone_reasoning_provider: str | None = None
    reasoning_provider: str = "disabled"
    mcp_access_token: str | None = None
    standalone_calls_per_minute: int = Field(default=6, ge=1, le=120)
    standalone_quota_cooldown_seconds: int = Field(default=300, ge=1)
    reasoning_timeout_seconds: int = Field(default=120, ge=1)

    gemini_api_key: str | None = None
    gemini_model: str = "auto"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_transcription_model: str = "gpt-4o-transcribe"
    admin_pin: str | None = None
    app_access_username: str = "mind"
    app_access_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def effective_standalone_reasoning_provider(self) -> str:
        return (
            self.standalone_reasoning_provider
            or self.reasoning_provider
            or "echo"
        ).strip().lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""
Application configuration loaded from environment variables.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "AI Business Workflow Architect"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="BACKEND_DEBUG")
    log_level: str = Field(default="INFO", alias="BACKEND_LOG_LEVEL")
    secret_key: str = Field(default="change-this-to-a-random-secret-key", alias="SECRET_KEY")

    # Server
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/workflow_architect",
        alias="DATABASE_URL",
    )

    # Qdrant
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="company_knowledge", alias="QDRANT_COLLECTION")

    # LLM
    llm_provider: str = Field(default="huggingface", alias="LLM_PROVIDER")
    llm_model: str = Field(default="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", alias="LLM_MODEL")
    llm_base_url: str = Field(default="https://router.huggingface.co/hf-inference/v1", alias="LLM_BASE_URL")
    llm_api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")
    hf_token: Optional[str] = Field(default=None, alias="HF_TOKEN")
    huggingface_api_key: Optional[str] = Field(default=None, alias="HUGGINGFACE_API_KEY")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")

    # Embedding
    embedding_provider: str = Field(default="dense", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    embedding_base_url: str = Field(default="https://router.huggingface.co/hf-inference/v1", alias="EMBEDDING_BASE_URL")
    embedding_api_key: Optional[str] = Field(default=None, alias="EMBEDDING_API_KEY")

    @property
    def effective_llm_api_key(self) -> Optional[str]:
        """Returns the configured LLM API key, checking LLM_API_KEY, HF_TOKEN, or HUGGINGFACE_API_KEY."""
        return self.llm_api_key or self.hf_token or self.huggingface_api_key

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Execution Limits
    max_workflow_steps: int = Field(default=50, alias="MAX_WORKFLOW_STEPS")
    max_execution_time_seconds: int = Field(default=300, alias="MAX_EXECUTION_TIME_SECONDS")
    max_retries_per_step: int = Field(default=3, alias="MAX_RETRIES_PER_STEP")
    max_tool_calls_per_execution: int = Field(default=100, alias="MAX_TOOL_CALLS_PER_EXECUTION")
    max_concurrent_executions: int = Field(default=10, alias="MAX_CONCURRENT_EXECUTIONS")
    max_requirement_length: int = Field(default=5000, alias="MAX_REQUIREMENT_LENGTH")

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {
        "env_file": (".env", "../.env"),
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }


from dotenv import load_dotenv

# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """Get application settings (singleton, or reloaded if requested)."""
    global _settings
    if _settings is None or reload:
        # Load from .env and ../.env with override
        for env_path in (".env", "../.env"):
            if os.path.exists(env_path):
                load_dotenv(env_path, override=True)
        _settings = Settings()
    return _settings


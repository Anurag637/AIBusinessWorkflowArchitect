"""
LLM factory providing instances based on application configuration.
Supports OpenAI, Ollama, Anthropic, and custom base URLs.
"""

from typing import Optional, Any
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_llm(temperature: Optional[float] = None) -> Any:
    """Instantiate and return configured ChatModel."""
    settings = get_settings()
    temp = temperature if temperature is not None else settings.llm_temperature
    provider = settings.llm_provider.lower()

    try:
        if provider in ("huggingface", "hugging_face", "hf"):
            from langchain_openai import ChatOpenAI
            api_key = settings.effective_llm_api_key or "hf_dummy_token"
            base_url = settings.llm_base_url
            if not base_url or "localhost" in base_url or "11434" in base_url:
                base_url = "https://router.huggingface.co/hf-inference/v1"
            return ChatOpenAI(
                model=settings.llm_model,
                temperature=temp,
                api_key=api_key,
                base_url=base_url,
                max_tokens=settings.llm_max_tokens,
            )
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.llm_model,
                temperature=temp,
                api_key=settings.effective_llm_api_key or "fake-key",
                base_url=settings.llm_base_url if settings.llm_base_url != "http://localhost:11434" else None,
                max_tokens=settings.llm_max_tokens,
            )
        elif provider == "ollama":
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                model=settings.llm_model,
                temperature=temp,
                base_url=settings.llm_base_url,
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.llm_model,
                temperature=temp,
                api_key=settings.effective_llm_api_key or "fake-key",
                base_url=settings.llm_base_url if settings.llm_base_url != "http://localhost:11434" else None,
                max_tokens=settings.llm_max_tokens,
            )
    except Exception as e:
        logger.warning(f"Could not initialize ChatModel ({provider}): {e}")
        return None

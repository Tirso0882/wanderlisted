"""LLM provider factory — swap models by changing environment variables.

Set LLM_PROVIDER to choose the chat model backend:
    azure_openai  — AzureChatOpenAI  (default)
    openai        — ChatOpenAI
    anthropic     — ChatAnthropic
    google        — ChatGoogleGenerativeAI
    ollama        — ChatOllama (local)

Set EMBEDDINGS_PROVIDER to choose the embeddings backend:
    azure_openai  — AzureOpenAIEmbeddings (default)
    openai        — OpenAIEmbeddings

Each provider reads its own env vars (see inline comments below).
Pass **overrides to customise any parameter at call time.
"""

import os

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

load_dotenv()

_SUPPORTED_CHAT = ("azure_openai", "openai", "anthropic", "google", "ollama")
_SUPPORTED_EMBEDDINGS = ("azure_openai", "openai")


def get_llm(**overrides) -> BaseChatModel:
    """Create a chat LLM instance based on ``LLM_PROVIDER`` env var.

    Any keyword argument is forwarded to the underlying LangChain class,
    so you can override temperature, max_tokens, etc. per call site.
    """
    provider = os.environ.get("LLM_PROVIDER", "azure_openai")

    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        defaults = dict(
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        return AzureChatOpenAI(**(defaults | overrides))

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        defaults = dict(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        return ChatOpenAI(**(defaults | overrides))

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        defaults = dict(
            model=os.environ["ANTHROPIC_MODEL"],
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )
        return ChatAnthropic(**(defaults | overrides))

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        defaults = dict(
            model=os.environ["GOOGLE_MODEL"],
            google_api_key=os.environ["GOOGLE_API_KEY"],
        )
        return ChatGoogleGenerativeAI(**(defaults | overrides))

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        defaults = dict(
            model=os.environ["OLLAMA_MODEL"],
            base_url=os.environ["OLLAMA_BASE_URL"],
        )
        return ChatOllama(**(defaults | overrides))

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. Supported: {_SUPPORTED_CHAT}"
    )


def get_embeddings(**overrides) -> Embeddings:
    """Create an embeddings model based on ``EMBEDDINGS_PROVIDER`` env var."""
    provider = os.environ.get("EMBEDDINGS_PROVIDER", "azure_openai")

    if provider == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings

        defaults = dict(
            azure_deployment=os.environ["AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        return AzureOpenAIEmbeddings(**(defaults | overrides))

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        defaults = dict(
            model=os.environ["OPENAI_EMBEDDINGS_MODEL"],
            api_key=os.environ["OPENAI_API_KEY"],
        )
        return OpenAIEmbeddings(**(defaults | overrides))

    raise ValueError(
        f"Unknown EMBEDDINGS_PROVIDER: {provider!r}. Supported: {_SUPPORTED_EMBEDDINGS}"
    )

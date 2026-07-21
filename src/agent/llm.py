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

Three-tier model pyramid (TPM / cost optimization):
    "reasoning" (default) — heavy model for complex multi-source synthesis,
                            tool-calling agents that require judgment
                            (gpt-5.4, 300K TPM)
    "fast"                — worker model for domain-specialist agents that
                            call one API and format results
                            (gpt-5.4-mini, 500K TPM)
    "utility"             — cheapest / lowest-latency model for routing,
                            classification, extraction, and rendering
                            (gpt-5.4-nano, 200K TPM)

All gpt-5.4 family models are reasoning models.  Key constraints:
    - Tool calling is NOT supported in Chat Completions with reasoning: none.
    - The Responses API is required for full tool-calling support.
    - We set use_responses_api=True and per-tier reasoning_effort to avoid
      the issue we hit with gpt-5.4-pro (Responses-only model).
    - Content returned via Responses API is a list of blocks, not a string;
      callers must use _extract_text_content() to read message content.

    Set *_FAST_* and *_UTILITY_* env vars to enable each tier.  When absent,
    each tier falls back to the next higher tier so the system works unchanged
    on a single-deployment setup.  Set LLM_EFFORT_<TIER> (REASONING/FAST/UTILITY)
    to tune reasoning effort per tier — see _resolve_reasoning_effort below.

Each provider reads its own env vars (see inline comments below).
Pass **overrides to customise any parameter at call time.
"""

import os
from typing import Literal, get_args

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from src.agent.concurrency import _SemaphoreLLM, _get_llm_semaphore

# Shells and entry points own runtime overrides such as EDD tracing policy.
load_dotenv()

_SUPPORTED_CHAT = ("azure_openai", "openai", "anthropic", "google", "ollama")
_SUPPORTED_EMBEDDINGS = ("azure_openai", "openai")

ModelTier = Literal["reasoning", "fast", "utility"]

# The effort ladder the gpt-5.4 family accepts, ordered low -> high compute.
# This Literal is the SINGLE source of truth for the effort vocabulary: the
# validation set below is DERIVED from it (get_args), so the two can never drift.
# (Responses API; "xhigh" is newest-model only, and some deployments reject "none".)
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
_VALID_REASONING_EFFORTS = get_args(ReasoningEffort)

# Tiers whose agents call tools. "reasoning: none" DISABLES tool calling on
# gpt-5.4 (a previously shipped production bug), so these tiers may not use "none".
_TOOL_CALLING_TIERS: tuple[ModelTier, ...] = ("fast", "utility")

# DEFAULT reasoning effort per tier — NOT a ceiling. Override any tier at runtime
# via the LLM_EFFORT_<TIER> env vars (resolved in _resolve_reasoning_effort).
# Because the dict is typed dict[ModelTier, ReasoningEffort], a typo'd default
# (e.g. "med") is caught by the type checker, not at an Azure 400 in production.
#   reasoning -> medium : complex multi-source synthesis benefits from deeper thinking
#   fast      -> low     : tool-calling workers need speed; "low" keeps tools working
#   utility   -> low     : routing/extraction still tool-calls; keep it cheap
_TIER_REASONING_EFFORT: dict[ModelTier, ReasoningEffort] = {
    "reasoning": "medium",
    "fast": "low",
    "utility": "low",
}


def _resolve_reasoning_effort(tier: ModelTier) -> str:
    """Resolve the reasoning effort for a tier, allowing a per-tier env override.

    Set ``LLM_EFFORT_REASONING`` / ``LLM_EFFORT_FAST`` / ``LLM_EFFORT_UTILITY``
    to any of ``none | minimal | low | medium | high | xhigh`` to tune compute
    per tier. Falls back to the per-tier default above.

    Fails fast on an invalid value, and refuses ``none`` on the tool-calling
    tiers (``fast`` / ``utility``): ``reasoning: none`` DISABLES tool calling on
    gpt-5.4 — a previously shipped production bug — so ``low`` is the safe floor.
    """
    default = _TIER_REASONING_EFFORT.get(tier, "low")
    effort = os.environ.get(f"LLM_EFFORT_{tier.upper()}", default).strip().lower()
    if effort not in _VALID_REASONING_EFFORTS:
        raise ValueError(
            f"Invalid reasoning effort {effort!r} for tier {tier!r}. "
            f"Valid levels: {_VALID_REASONING_EFFORTS}."
        )
    if effort == "none" and tier in _TOOL_CALLING_TIERS:
        raise ValueError(
            f"reasoning effort 'none' disables tool calling on gpt-5.4, but the "
            f"{tier!r} tier runs tool-calling agents. Use 'low' or higher."
        )
    return effort


def _resolve_deployment(tier: ModelTier, env_prefix: str) -> str:
    """Resolve the deployment/model name for a given tier.

    Falls back up the chain: utility -> fast -> reasoning.
    """
    if tier == "utility":
        val = os.environ.get(f"{env_prefix}_UTILITY_DEPLOYMENT_NAME") or os.environ.get(
            f"{env_prefix}_FAST_DEPLOYMENT_NAME"
        )
        if val:
            return val
    if tier in ("fast", "utility"):
        val = os.environ.get(f"{env_prefix}_FAST_DEPLOYMENT_NAME")
        if val:
            return val
    return os.environ[f"{env_prefix}_DEPLOYMENT_NAME"]


def _resolve_model(tier: ModelTier, env_prefix: str, default: str = "") -> str:
    """Resolve the model name for non-Azure providers.

    Falls back up the chain: utility -> fast -> reasoning.
    """
    if tier == "utility":
        val = os.environ.get(f"{env_prefix}_UTILITY_MODEL")
        if val:
            return val
    if tier in ("fast", "utility"):
        val = os.environ.get(f"{env_prefix}_FAST_MODEL")
        if val:
            return val
    return os.environ.get(f"{env_prefix}_MODEL", default)


def get_llm(tier: ModelTier = "reasoning", **overrides) -> BaseChatModel:
    """Create a chat LLM instance based on ``LLM_PROVIDER`` env var.

    Args:
        tier: Model tier selection.
            * ``"reasoning"`` (default) — full-power model for complex agent
              reasoning, multi-source synthesis, and judgment calls.
            * ``"fast"`` — worker model for domain-specialist agents that
              call APIs and format structured results.
            * ``"utility"`` — cheapest / fastest model for routing,
              classification, extraction, rendering, and shallow replies.
            Falls back up the chain when a tier's env var is absent.
        **overrides: Forwarded to the underlying LangChain class
            (temperature, max_tokens, etc.).
    """
    provider = os.environ.get("LLM_PROVIDER", "azure_openai")

    raw: BaseChatModel

    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        deployment = _resolve_deployment(tier, "AZURE_OPENAI")

        defaults = dict(
            azure_deployment=deployment,
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            # gpt-5.4 family: Responses API required for tool calling
            # when reasoning effort is none (the default). We enable
            # Responses API and set a per-tier reasoning effort.
            use_responses_api=True,
            reasoning_effort=_resolve_reasoning_effort(tier),
        )
        raw = AzureChatOpenAI(**(defaults | overrides))

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        model = _resolve_model(tier, "OPENAI", default="gpt-4o")

        defaults = dict(
            model=model,
            api_key=os.environ.get("OPENAI_API_KEY"),
            # gpt-5.4 family: enable Responses API + reasoning effort
            use_responses_api=True,
            reasoning_effort=_resolve_reasoning_effort(tier),
        )
        raw = ChatOpenAI(**(defaults | overrides))

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = _resolve_model(tier, "ANTHROPIC")

        defaults = dict(
            model=model,
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )
        raw = ChatAnthropic(**(defaults | overrides))

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = _resolve_model(tier, "GOOGLE")

        defaults = dict(
            model=model,
            google_api_key=os.environ["GOOGLE_API_KEY"],
        )
        raw = ChatGoogleGenerativeAI(**(defaults | overrides))

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model = _resolve_model(tier, "OLLAMA")

        defaults = dict(
            model=model,
            base_url=os.environ["OLLAMA_BASE_URL"],
        )
        raw = ChatOllama(**(defaults | overrides))

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. Supported: {_SUPPORTED_CHAT}"
        )

    return _SemaphoreLLM(raw, _get_llm_semaphore(tier))


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

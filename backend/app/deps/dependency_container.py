import logging
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

DEFAULT_ARCH = "supervisor"


class DIContainer:
    def __init__(self) -> None:
        self._embedding_client: Any | None = None
        self._llm_client: BaseChatModel | None = None
        self._mcp_server_client: MultiServerMCPClient | None = None
        # Single source of truth for compiled agent graphs, keyed by arch name.
        self._agents: dict[str, Any] = {}

    # --- Embedding Client ---
    @property
    def embedding_client(self):
        return self._embedding_client

    @embedding_client.setter
    def embedding_client(self, value):
        self._embedding_client = value

    # --- LLM Client ---
    @property
    def llm_client(self) -> BaseChatModel:
        return self._llm_client

    @llm_client.setter
    def llm_client(self, value: BaseChatModel):
        if value is not None and not isinstance(value, BaseChatModel):
            raise TypeError("llm_client must be an instance of BaseChatModel")
        self._llm_client = value

    # --- MCP Server Client ---
    @property
    def mcp_server_client(self) -> MultiServerMCPClient:
        return self._mcp_server_client

    @mcp_server_client.setter
    def mcp_server_client(self, value: MultiServerMCPClient):
        self._mcp_server_client = value

    # --- Agent Instances (multi-arch) ---
    def register_agent(self, name: str, graph: Any) -> None:
        """Register a compiled agent graph under an architecture name."""
        self._agents[name] = graph

    def get_agent(self, arch: str = DEFAULT_ARCH) -> Any:
        """Return the agent graph registered for ``arch``.

        Fails loud: an unknown or unregistered arch raises ``ValueError`` rather
        than silently falling back to the supervisor. Silently running the wrong
        arm would contaminate the thesis architecture-comparison measurements.
        A no-arg call still returns the supervisor when it has been registered.
        """
        agent = self._agents.get(arch)
        if agent is None:
            registered = sorted(self._agents.keys())
            raise ValueError(
                f"No agent registered for arch '{arch}'. Registered arches: {registered}."
            )
        return agent

    # --- Agent Instance (backward-compatible: supervisor arm) ---
    @property
    def agent_instance(self) -> Any | None:
        return self._agents.get(DEFAULT_ARCH)

    def get_agent_instance(self) -> Any | None:
        return self._agents.get(DEFAULT_ARCH)

di_container_instance = DIContainer()
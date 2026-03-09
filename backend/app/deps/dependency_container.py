from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.language_models.chat_models import BaseChatModel

class DIContainer:
    def __init__(self):
        self._embedding_client = None
        self._llm_client: BaseChatModel = None
        self._mcp_server_client: MultiServerMCPClient = None
        self._agent_instance = None

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

    # --- Agent Instance ---
    @property
    def agent_instance(self):
        return self._agent_instance

    @agent_instance.setter
    def agent_instance(self, value):
        self._agent_instance = value

    def get_agent_instance(self):
        return self._agent_instance

di_container_instance = DIContainer()
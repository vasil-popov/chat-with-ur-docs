from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.language_models.chat_models import BaseChatModel


class DIContainer:
    def __init__(self):
        self.embedding_client = None
        self.llm_client: BaseChatModel = None
        self.mcp_server_client: MultiServerMCPClient = None
        self.agent_instance = None
        
di_container_instance = DIContainer()
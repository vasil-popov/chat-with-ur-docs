from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_genai import ChatGoogleGenerativeAI


def get_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient({
        "finance_server": {
            "url": "http://localhost:8000/mcp",
            "transport": "http",
        }
    })

def get_llm_client() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", 
        temperature=0 
    )
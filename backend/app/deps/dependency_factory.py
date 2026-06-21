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
        temperature=0,
        timeout=60,
        # max_retries counts TOTAL attempts (alias of `retries`), not extra retries:
        # 2 = one retry. Library default is 6; bounded here so a transient 504 fails
        # within the timeout budget instead of backing off for minutes.
        max_retries=2,
    )
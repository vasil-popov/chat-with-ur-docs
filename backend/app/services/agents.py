import logging
from datetime import date
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from pydantic import BaseModel

logger = logging.getLogger(__name__)

TRACKING_SYSTEM_PROMPT = """You are a personal fitness and finance tracking assistant.
Use the available tools to:
- Log expenses (grocery bills, restaurant tabs, purchases, anything the user wants to record as a spend)
- Log workouts and exercises
- Query expense and workout history

When the user mentions items from a receipt, store, or grocery trip — log those as expenses.
Always confirm what you recorded. Today's date: {today}."""

RAG_SYSTEM_PROMPT = """You are a document Q&A assistant.
Use the available tools to search through uploaded documents and answer questions based on their content.
Only answer questions about document content — do NOT log expenses or workouts.
Cite the source document when you answer. Today's date: {today}."""

SUPERVISOR_SYSTEM_PROMPT = """You are a routing supervisor. Decide which specialist to invoke next.

Specialists:
- "tracking": expenses (logging, editing, querying), workouts/exercises (logging, querying).
  Use for: "log this", "add expense", "record my workout", "groceries cost X", "I spent X on Y", receipt items that need to be saved.
- "rag": questions about the CONTENT of uploaded files/documents (what does the document say, summarise file, search notes).
  Do NOT use for logging or saving data.
- "FINISH": the last assistant message already answered the user fully — no more work needed.

Rules:
- If the last message in the conversation is a complete assistant answer, respond FINISH.
- If the user wants to save/log something (even from a receipt), respond tracking.
- If the user asks a question about file contents, respond rag.
- Never route to the same agent twice in a row for the same request.

Respond with exactly one word: tracking, rag, or FINISH."""


class RouteDecision(BaseModel):
    next: Literal["tracking", "rag", "FINISH"]


def _last_human_message(state: MessagesState) -> list:
    """Return only the last human turn to avoid sending full history to sub-agents."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return [msg]
    return state["messages"][-1:]


def build_graph(llm, mcp_tools: list, rag_tools: list):
    today = date.today().isoformat()

    tracking_agent = create_react_agent(
        llm,
        mcp_tools,
        prompt=SystemMessage(content=TRACKING_SYSTEM_PROMPT.format(today=today)),
    )

    rag_agent = create_react_agent(
        llm,
        rag_tools,
        prompt=SystemMessage(content=RAG_SYSTEM_PROMPT.format(today=today)),
    )

    router_llm = llm.with_structured_output(RouteDecision)

    async def supervisor_node(state: MessagesState) -> Command:
        # Only send the last few messages to the supervisor to keep context small
        recent = state["messages"][-6:]
        messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)] + recent
        try:
            decision = await router_llm.ainvoke(messages)
        except Exception as e:
            logger.error("Supervisor LLM error: %s", e)
            return Command(goto=END)
        logger.info("Supervisor routed to: %s", decision.next)
        goto = END if decision.next == "FINISH" else decision.next
        return Command(goto=goto)

    async def call_tracking_agent(state: MessagesState) -> Command:
        # Pass only the last human message so the agent's context stays bounded
        sub_state = {"messages": _last_human_message(state)}
        try:
            result = await tracking_agent.ainvoke(sub_state)
            # Append only the final AI response (not intermediate tool calls)
            new_messages = [m for m in result["messages"] if isinstance(m, AIMessage)][-1:]
        except Exception as e:
            logger.error("TrackingAgent error: %s", e)
            new_messages = [AIMessage(content=f"I encountered an error processing your request: {e}")]
        return Command(goto="supervisor", update={"messages": new_messages})

    async def call_rag_agent(state: MessagesState) -> Command:
        sub_state = {"messages": _last_human_message(state)}
        try:
            result = await rag_agent.ainvoke(sub_state)
            new_messages = [m for m in result["messages"] if isinstance(m, AIMessage)][-1:]
        except Exception as e:
            logger.error("RAGAgent error: %s", e)
            new_messages = [AIMessage(content=f"I encountered an error searching documents: {e}")]
        return Command(goto="supervisor", update={"messages": new_messages})

    graph = (
        StateGraph(MessagesState)
        .add_node("supervisor", supervisor_node)
        .add_node("tracking", call_tracking_agent)
        .add_node("rag", call_rag_agent)
        .add_edge(START, "supervisor")
        .compile()
    )

    logger.info("LangGraph Supervisor compiled with %d MCP tools and %d RAG tools", len(mcp_tools), len(rag_tools))
    return graph

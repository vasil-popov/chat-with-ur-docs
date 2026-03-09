from fastapi import APIRouter, BackgroundTasks, Depends
from app.api.schemas.chat import ChatRequest
from app.deps.dependency_container import di_container_instance

router = APIRouter()

def get_last_message_text(response):
    last_msg = response["messages"][-1]
    content = last_msg.content
    
    if isinstance(content, str):
        return content
    
    # If it's a list of blocks (like your output), find the 'text' type
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text")
            # Some providers use a plain string inside the list
            if isinstance(block, str):
                return block
                
    return str(content)

@router.post("", summary="Chat API")
async def chat(
    req: ChatRequest,
    #background_tasks: BackgroundTasks,
    agent = Depends(di_container_instance.get_agent_instance)
):
    try:
        response = await agent.ainvoke({"messages": [("user", req.message)]})
        # 1. Grab the raw content
        raw_content = response["messages"][-1].content
        
        # 2. Safely extract the string, even if LangChain returns a list of objects
        final_message = ""
        if isinstance(raw_content, str):
            final_message = raw_content
        elif isinstance(raw_content, list):
            # Loop through the blocks and grab only the text parts
            text_blocks = [block.get("text", "") for block in raw_content if isinstance(block, dict) and "text" in block]
            final_message = "\n".join(text_blocks)
        else:
            final_message = str(raw_content) # Absolute fallback
            
        # 3. Extract the tools used
        tools_used = []
        for msg in response["messages"]:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool in msg.tool_calls:
                    tools_used.append(tool['name'])
                    
        unique_tools = list(set(tools_used))

        # 4. Return the guaranteed string
        return {
            "role": "assistant", 
            "content": final_message,
            "metadata": {
                "tools_executed": unique_tools
            }
        }
        
    except Exception as e:
        return {"role": "assistant", "content": f"System Error: {str(e)}", "metadata": {"tools_executed": []}}
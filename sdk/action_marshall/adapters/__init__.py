"""
Framework adapters for Action Marshall.

Each adapter wraps a framework's tool primitive (LangChain ``BaseTool``,
LangGraph nodes, CrewAI tools, AutoGen function tools, MCP tools,
LlamaIndex tools, OpenAI function-calling tools) so a call to that tool
is governed by Action Marshall before it executes.

Adapters are optional extras. Install only what you need:

    pip install "action-marshall[langchain]"
    pip install "action-marshall[langgraph]"
    pip install "action-marshall[crewai]"
    pip install "action-marshall[autogen]"
    pip install "action-marshall[mcp]"
    pip install "action-marshall[llamaindex]"
    pip install "action-marshall[openai]"

Importing an adapter without its underlying framework installed raises
``ImportError`` with a hint to install the matching extra.

Status today:

- ``langchain`` — experimental, ships in this release
- ``langgraph`` — planned
- ``crewai`` — planned
- ``autogen`` — planned
- ``mcp`` — planned
- ``llamaindex`` — planned
- ``openai`` — planned
"""

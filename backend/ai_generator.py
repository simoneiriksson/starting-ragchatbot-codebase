import anthropic
from typing import List, Optional

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Tool Usage:
- **Course outline queries** (e.g., "what lessons does course X have", "show me the syllabus", "list the topics"): Use `get_course_outline` — it returns the course title, link, and complete numbered lesson list
- **Course content questions** (e.g., "explain X from course Y", "what does lesson 2 cover"): Use `search_course_content`
- **Up to 2 sequential tool calls per query** — use a second call only when the first result reveals a need for additional information
- Synthesize results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    MAX_TOOL_ROUNDS = 2

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool calls.
        """
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]
        api_params = {**self.base_params, "messages": messages, "system": system_content}
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        response = self.client.messages.create(**api_params)
        rounds = 0

        while response.stop_reason == "tool_use" and tool_manager and rounds < self.MAX_TOOL_ROUNDS:
            messages = messages + [{"role": "assistant", "content": response.content}]
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = tool_manager.execute_tool(block.name, **block.input)
                    except Exception as e:
                        result = f"Error executing tool '{block.name}': {e}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            messages = messages + [{"role": "user", "content": tool_results}]

            next_params = {**self.base_params, "messages": messages, "system": system_content}
            if tools:
                next_params["tools"] = tools
                next_params["tool_choice"] = {"type": "auto"}
            response = self.client.messages.create(**next_params)
            rounds += 1

        # Rounds exhausted but Claude still wants tools — force a text response
        if response.stop_reason == "tool_use" and tool_manager:
            response = self.client.messages.create(
                **{**self.base_params, "messages": messages, "system": system_content}
            )

        return response.content[0].text
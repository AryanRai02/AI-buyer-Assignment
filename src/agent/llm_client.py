"""
LLM Client dispatcher supporting Gemini API and Autonomous Deterministic Mode.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional

from src.config import settings
from src.tools import TOOL_REGISTRY, TOOL_DEFINITIONS
from src.models.agent import ToolCallRecord


class LLMDispatcher:
    """
    Intelligent LLM Dispatcher that routes to Google Gemini
    or Autonomous Deterministic Engine based on configuration and available API key.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.gemini_key = settings.GEMINI_API_KEY

        # Determine active provider
        if self.provider == "auto":
            if self.gemini_key and not self.gemini_key.startswith("your_"):
                self.active_provider = "gemini"
            else:
                self.active_provider = "deterministic"
        else:
            self.active_provider = self.provider

    def get_provider_name(self) -> str:
        return self.active_provider

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallRecord:
        """Execute a tool from registry and record metadata."""
        start_time = time.perf_counter()
        tool_func = TOOL_REGISTRY.get(tool_name)
        if not tool_func:
            res = {"error": f"Tool '{tool_name}' not recognized."}
        else:
            try:
                res = tool_func(**arguments)
                # Convert pydantic models to dict if needed
                if hasattr(res, "model_dump"):
                    res = res.model_dump()
            except Exception as e:
                res = {"error": f"Tool execution failed: {str(e)}"}

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            result=res,
            latency_ms=elapsed_ms
        )

    def run_gemini(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """Execute reasoning and tool calling loop via Google Gemini."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        # Setup tool declarations
        function_declarations = []
        for tool_def in TOOL_DEFINITIONS:
            function_declarations.append(
                types.FunctionDeclaration(
                    name=tool_def["name"],
                    description=tool_def["description"],
                    parameters=tool_def["parameters"]
                )
            )

        tools = [types.Tool(function_declarations=function_declarations)]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
            temperature=0.1
        )

        chat = client.chats.create(model=settings.GEMINI_MODEL, config=config)
        response = chat.send_message(user_prompt)

        # Multi-turn tool execution loop
        max_turns = 10
        turn = 0
        tool_calls_record = []
        reasoning_trace = []

        while turn < max_turns:
            turn += 1
            function_calls = response.function_calls
            if not function_calls:
                break

            for fc in function_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}
                call_rec = self.execute_tool(name, args)
                tool_calls_record.append(call_rec)
                reasoning_trace.append(f"Invoked tool: {name}({json.dumps(args)}) -> result: {str(call_rec.result)[:120]}...")

                # Send function response back to Gemini
                response = chat.send_message(
                    types.Part.from_function_response(
                        name=name,
                        response={"result": call_rec.result}
                    )
                )

        final_text = response.text or ""
        return {
            "text": final_text,
            "tool_calls": tool_calls_record,
            "reasoning_trace": reasoning_trace
        }


llm_dispatcher = LLMDispatcher()

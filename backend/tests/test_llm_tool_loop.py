import unittest
from unittest.mock import patch

from app.pipeline.llm import generate_agent_reply
from app.agent.tools import check_appointment_slots, create_lead


class FakeToolCallMessage:
    def __init__(self, tool_name, args):
        self.tool_calls = [
            type("ToolCall", (), {"function": type("Function", (), {"name": tool_name, "arguments": args})()})()
        ]


class FakeResponse:
    def __init__(self, message):
        self.choices = [type("Choice", (), {"message": message})()]


class FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse(FakeToolCallMessage("check_appointment_slots", '{"date": "2026-08-10"}'))
        return FakeResponse(type("Message", (), {"content": "I found a couple of slots.", "tool_calls": []})())


class LLMToolLoopTests(unittest.TestCase):
    def test_generate_agent_reply_calls_tool_and_returns_final_text(self):
        fake_client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()
        tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "check_appointment_slots",
                    "description": "Check available appointment slots.",
                    "parameters": {"type": "object", "properties": {"date": {"type": "string"}}},
                },
            }
        ]

        reply = unittest.mock.Mock()
        with patch("app.pipeline.llm._call_tool_function", return_value="slot info") as mocked_call:
            result = generate_agent_reply("Do you have anything on August 10?", [], tool_definitions, client=fake_client)
            self.assertIn("slots", result.lower())
            mocked_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()

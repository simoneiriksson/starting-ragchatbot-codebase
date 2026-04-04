"""
Tests for AIGenerator tool-calling behaviour.

Key questions:
1. Does a non-course question get answered directly (no tool call)?
2. Does a course content question trigger search_course_content?
3. Is the tool result fed back into a second API call?
4. Is the final text response correctly returned?
5. What happens if the response content list is empty or malformed?
"""
import pytest
from unittest.mock import MagicMock, patch

from ai_generator import AIGenerator
from conftest import make_text_response, make_tool_use_response


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def generator():
    return AIGenerator(api_key="test-key", model="claude-test-model")


@pytest.fixture
def mock_tool_manager():
    tm = MagicMock()
    tm.execute_tool.return_value = "[Test Course - Lesson 1]\nPython is great."
    return tm


TOOL_DEFS = [
    {
        "name": "search_course_content",
        "description": "Search course materials",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }
]


# ── Tests: direct (no-tool) response ─────────────────────────────────────────

class TestDirectResponse:
    def test_returns_text_when_no_tool_use(self, generator):
        with patch.object(generator.client.messages, "create",
                          return_value=make_text_response("42")) as mock_create:
            result = generator.generate_response(query="What is 6 times 7?")

        assert result == "42"
        assert mock_create.call_count == 1

    def test_no_tools_means_single_api_call(self, generator):
        with patch.object(generator.client.messages, "create",
                          return_value=make_text_response("Hello")) as mock_create:
            generator.generate_response(query="Say hello")

        assert mock_create.call_count == 1

    def test_conversation_history_included_in_system_prompt(self, generator):
        history = "User: hi\nAssistant: hello"
        with patch.object(generator.client.messages, "create",
                          return_value=make_text_response("ok")) as mock_create:
            generator.generate_response(query="test", conversation_history=history)

        call_kwargs = mock_create.call_args[1]
        assert history in call_kwargs.get("system", "")


# ── Tests: tool-use flow ──────────────────────────────────────────────────────

class TestToolUseFlow:
    def test_tool_use_triggers_second_api_call(self, generator, mock_tool_manager):
        first = make_tool_use_response(
            "search_course_content", {"query": "python basics"}, "toolu_001"
        )
        second = make_text_response("Python is a programming language.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second]) as mock_create:
            result = generator.generate_response(
                query="What is python?",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        assert mock_create.call_count == 2
        assert result == "Python is a programming language."

    def test_tool_manager_execute_called_with_correct_args(self, generator, mock_tool_manager):
        first = make_tool_use_response(
            "search_course_content",
            {"query": "variables", "course_name": "Python Course"},
            "toolu_002",
        )
        second = make_text_response("Variables store values.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second]):
            generator.generate_response(
                query="Explain variables",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="variables",
            course_name="Python Course",
        )

    def test_tool_result_sent_in_second_api_call(self, generator, mock_tool_manager):
        tool_output = "[Test Course - Lesson 1]\nPython is great."
        mock_tool_manager.execute_tool.return_value = tool_output

        first = make_tool_use_response(
            "search_course_content", {"query": "test"}, "toolu_003"
        )
        second = make_text_response("Great stuff.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second]) as mock_create:
            generator.generate_response(
                query="test query",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        second_call_messages = mock_create.call_args_list[1][1]["messages"]
        # The last message in the second call should be a user message containing tool results
        tool_result_msg = second_call_messages[-1]
        assert tool_result_msg["role"] == "user"
        content = tool_result_msg["content"]
        assert isinstance(content, list)
        assert any(
            block.get("type") == "tool_result" and block.get("content") == tool_output
            for block in content
        )

    def test_round2_api_call_includes_tools(self, generator, mock_tool_manager):
        """The follow-up call within the tool loop must include tools so Claude can chain."""
        first = make_tool_use_response(
            "search_course_content", {"query": "test"}, "toolu_004"
        )
        second = make_text_response("Answer.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second]) as mock_create:
            generator.generate_response(
                query="test",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        second_call_kwargs = mock_create.call_args_list[1][1]
        assert "tools" in second_call_kwargs

    def test_two_sequential_tool_calls(self, generator, mock_tool_manager):
        """Claude makes two tool calls in separate rounds before giving a final answer."""
        first = make_tool_use_response(
            "search_course_content", {"query": "outline"}, "toolu_010"
        )
        second = make_tool_use_response(
            "search_course_content", {"query": "similar topic"}, "toolu_011"
        )
        third = make_text_response("Here is the combined answer.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second, third]) as mock_create:
            result = generator.generate_response(
                query="Find a course similar to lesson 4 of Course X",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        assert mock_create.call_count == 3
        assert mock_tool_manager.execute_tool.call_count == 2
        assert result == "Here is the combined answer."
        # Both follow-up calls within the loop include tools (rounds 1 and 2 are both < MAX_TOOL_ROUNDS)
        assert "tools" in mock_create.call_args_list[1][1]
        assert "tools" in mock_create.call_args_list[2][1]

    def test_terminates_after_max_rounds_force_text_call(self, generator, mock_tool_manager):
        """After MAX_TOOL_ROUNDS tool rounds, a final force-text call is made without tools."""
        first = make_tool_use_response("search_course_content", {"query": "q1"}, "toolu_020")
        second = make_tool_use_response("search_course_content", {"query": "q2"}, "toolu_021")
        # Claude still wants tools after round 2 — should be ignored and force-text call made
        third = make_tool_use_response("search_course_content", {"query": "q3"}, "toolu_022")
        fourth = make_text_response("Forced final answer.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second, third, fourth]) as mock_create:
            result = generator.generate_response(
                query="complex query",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        assert mock_create.call_count == 4
        assert mock_tool_manager.execute_tool.call_count == 2
        assert result == "Forced final answer."
        # Force-text call (4th) must not include tools
        assert "tools" not in mock_create.call_args_list[3][1]

    def test_tool_execution_error_included_in_results(self, generator, mock_tool_manager):
        """A tool execution exception is caught and injected as error text; the round continues."""
        mock_tool_manager.execute_tool.side_effect = Exception("DB offline")

        first = make_tool_use_response(
            "search_course_content", {"query": "test"}, "toolu_030"
        )
        second = make_text_response("Could not retrieve data.")

        with patch.object(generator.client.messages, "create",
                          side_effect=[first, second]) as mock_create:
            result = generator.generate_response(
                query="test",
                tools=TOOL_DEFS,
                tool_manager=mock_tool_manager,
            )

        assert mock_create.call_count == 2
        assert result == "Could not retrieve data."
        second_call_messages = mock_create.call_args_list[1][1]["messages"]
        tool_result_msg = second_call_messages[-1]
        assert tool_result_msg["role"] == "user"
        content = tool_result_msg["content"]
        assert any(
            block.get("type") == "tool_result"
            and "Error executing tool" in block.get("content", "")
            and "DB offline" in block.get("content", "")
            for block in content
        )


# ── Tests: error / edge cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_content_list_raises(self, generator):
        """If the API returns an empty content list, accessing [0] raises IndexError."""
        bad_response = MagicMock()
        bad_response.stop_reason = "end_turn"
        bad_response.content = []  # empty!

        with patch.object(generator.client.messages, "create",
                          return_value=bad_response):
            with pytest.raises(IndexError):
                generator.generate_response(query="test")

    def test_tool_use_without_tool_manager_skips_execution(self, generator):
        """If stop_reason is tool_use but tool_manager=None, _handle_tool_execution is skipped.
        The code falls through to response.content[0].text — only ONE API call is made."""
        tool_resp = make_tool_use_response(
            "search_course_content", {"query": "test"}, "toolu_005"
        )
        with patch.object(generator.client.messages, "create",
                          return_value=tool_resp) as mock_create:
            # Should not raise, but also should NOT make a second API call
            generator.generate_response(query="test", tools=TOOL_DEFS, tool_manager=None)

        assert mock_create.call_count == 1, (
            "Expected exactly 1 API call when tool_manager=None, "
            f"but got {mock_create.call_count}"
        )

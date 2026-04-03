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

    def test_second_api_call_does_not_include_tools(self, generator, mock_tool_manager):
        """The follow-up call must NOT pass tools to avoid infinite tool loops."""
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
        assert "tools" not in second_call_kwargs


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

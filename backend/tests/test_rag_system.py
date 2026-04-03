"""
Tests for RAGSystem.query() — the end-to-end content-query pipeline.

Layers tested:
1. RAGSystem with mocked AIGenerator  → isolates vector-store / tool plumbing
2. RAGSystem with mocked VectorStore  → isolates AI-generator / message flow
3. Full integration (no mocks, temp chroma, no real LLM) → tests doc loading + search
"""
import pytest
from unittest.mock import MagicMock, patch

from conftest import make_text_response, make_tool_use_response


# ── Shared RAGSystem factory ──────────────────────────────────────────────────

def _make_rag(config):
    from rag_system import RAGSystem
    return RAGSystem(config)


@pytest.fixture
def fake_config(tmp_path):
    from dataclasses import dataclass

    @dataclass
    class FakeConfig:
        ANTHROPIC_API_KEY: str = "test-key"
        ANTHROPIC_MODEL: str = "claude-test-model"
        EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
        CHUNK_SIZE: int = 800
        CHUNK_OVERLAP: int = 100
        MAX_RESULTS: int = 5
        MAX_HISTORY: int = 2
        CHROMA_PATH: str = str(tmp_path / "chroma")

    return FakeConfig()


@pytest.fixture
def rag(fake_config):
    from rag_system import RAGSystem
    return RAGSystem(fake_config)


# ── Layer 1: mocked AIGenerator ───────────────────────────────────────────────

class TestRAGWithMockedAI:
    def test_query_returns_tuple_of_response_and_sources(self, rag):
        rag.ai_generator.generate_response = MagicMock(return_value="Test answer")
        response, sources = rag.query("What is Python?")
        assert isinstance(response, str)
        assert isinstance(sources, list)

    def test_query_response_is_ai_output(self, rag):
        rag.ai_generator.generate_response = MagicMock(return_value="AI answer here")
        response, _ = rag.query("Some question")
        assert response == "AI answer here"

    def test_session_history_passed_to_ai(self, rag):
        session_id = rag.session_manager.create_session()
        rag.session_manager.add_exchange(session_id, "prev question", "prev answer")

        rag.ai_generator.generate_response = MagicMock(return_value="ok")
        rag.query("follow-up question", session_id=session_id)

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") is not None
        assert "prev question" in call_kwargs["conversation_history"]

    def test_tools_passed_to_ai(self, rag):
        rag.ai_generator.generate_response = MagicMock(return_value="ok")
        rag.query("What does lesson 1 cover?")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        tools = call_kwargs.get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert "search_course_content" in tool_names

    def test_tool_manager_passed_to_ai(self, rag):
        rag.ai_generator.generate_response = MagicMock(return_value="ok")
        rag.query("test")

        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("tool_manager") is rag.tool_manager

    def test_sources_reset_after_query(self, rag):
        rag.ai_generator.generate_response = MagicMock(return_value="ok")
        rag.search_tool.last_sources = [{"label": "stale", "url": None}]
        rag.query("test")
        # After query, sources should be reset (consumed and cleared)
        assert rag.search_tool.last_sources == []


# ── Layer 2: mocked VectorStore (real AIGenerator, mocked Anthropic client) ───

class TestRAGWithMockedVectorStore:
    def test_content_query_triggers_search_tool(self, rag):
        """When AI requests search_course_content, the tool is executed."""
        first = make_tool_use_response(
            "search_course_content", {"query": "python variables"}, "toolu_001"
        )
        second = make_text_response("Variables are containers for data.")

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[first, second]):
            response, _ = rag.query("What are python variables?")

        assert "Variables" in response or "containers" in response

    def test_search_tool_executed_calls_vector_store(self, rag):
        """search_course_content tool execution reaches VectorStore.search()."""
        first = make_tool_use_response(
            "search_course_content", {"query": "loops"}, "toolu_002"
        )
        second = make_text_response("Loops repeat code.")

        with patch.object(rag.vector_store, "search") as mock_search, \
             patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[first, second]):

            from vector_store import SearchResults
            mock_search.return_value = SearchResults(
                documents=["Loops repeat blocks of code."],
                metadata=[{"course_title": "Test Course", "lesson_number": 3}],
                distances=[0.05],
            )
            rag.query("Explain loops")

        mock_search.assert_called_once_with(
            query="loops",
            course_name=None,
            lesson_number=None,
        )

    def test_no_tool_use_on_general_knowledge_question(self, rag):
        """General knowledge questions should NOT trigger the search tool."""
        direct = make_text_response("The capital of France is Paris.")

        with patch.object(rag.ai_generator.client.messages, "create",
                          return_value=direct) as mock_create:
            response, _ = rag.query("What is the capital of France?")

        # Only one API call = no tool execution
        assert mock_create.call_count == 1
        assert "Paris" in response


# ── Layer 3: Full integration (real components, real docs, no Anthropic) ──────

class TestRAGIntegration:
    def test_add_course_document_and_search(self, rag, tmp_path):
        """Documents loaded into the RAG system should be searchable."""
        doc = tmp_path / "course_test.txt"
        doc.write_text(
            "Course Title: Integration Test Course\n"
            "Course Link: https://example.com/integration\n"
            "Course Instructor: Test Instructor\n"
            "\n"
            "Lesson 1: Getting Started\n"
            "Lesson Link: https://example.com/integration/1\n"
            "This lesson covers the fundamentals of integration testing "
            "and why it matters for software quality.\n"
            "\n"
            "Lesson 2: Advanced Topics\n"
            "Lesson Link: https://example.com/integration/2\n"
            "Advanced integration patterns include mocking external services "
            "and testing database interactions.\n"
        )
        course, n_chunks = rag.add_course_document(str(doc))
        assert course is not None, "Document processing returned None"
        assert n_chunks > 0, "No chunks were created from the document"

        from vector_store import SearchResults
        results = rag.vector_store.search(query="integration testing fundamentals")
        assert not results.is_empty(), "Search returned no results after loading document"
        assert any("integration" in d.lower() for d in results.documents), \
            "Expected document content not found in search results"

    def test_course_search_tool_returns_content_after_load(self, rag, tmp_path):
        """CourseSearchTool.execute() returns real content after doc is loaded."""
        doc = tmp_path / "course_tool_test.txt"
        doc.write_text(
            "Course Title: Tool Test Course\n"
            "Course Link: https://example.com/tool\n"
            "Course Instructor: Tester\n"
            "\n"
            "Lesson 1: Basics\n"
            "Lesson Link: https://example.com/tool/1\n"
            "The basics lesson explains fundamental concepts clearly.\n"
        )
        rag.add_course_document(str(doc))

        result = rag.search_tool.execute(query="fundamental concepts")
        assert isinstance(result, str)
        assert "No relevant content found" not in result, \
            f"Tool returned no-content message instead of results: {result!r}"
        assert "Tool Test Course" in result

    def test_query_pipeline_does_not_raise_on_tool_execution(self, rag, tmp_path):
        """The full query pipeline must not raise when tool is executed."""
        doc = tmp_path / "course_pipeline.txt"
        doc.write_text(
            "Course Title: Pipeline Course\n"
            "Course Link: https://example.com/pipeline\n"
            "Course Instructor: Tester\n"
            "\n"
            "Lesson 1: Overview\n"
            "Lesson Link: https://example.com/pipeline/1\n"
            "This overview lesson introduces the pipeline architecture.\n"
        )
        rag.add_course_document(str(doc))

        first = make_tool_use_response(
            "search_course_content",
            {"query": "pipeline architecture"},
            "toolu_pipeline_001",
        )
        second = make_text_response("The pipeline architecture is described in lesson 1.")

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[first, second]):
            # Must not raise
            response, sources = rag.query("What is the pipeline architecture?")

        assert isinstance(response, str)
        assert len(response) > 0

    def test_sources_populated_after_content_query(self, rag, tmp_path):
        """After a tool-based content query, sources must be a list of dicts."""
        doc = tmp_path / "course_sources.txt"
        doc.write_text(
            "Course Title: Sources Course\n"
            "Course Link: https://example.com/sources\n"
            "Course Instructor: Tester\n"
            "\n"
            "Lesson 1: Introduction\n"
            "Lesson Link: https://example.com/sources/1\n"
            "Introduction to source tracking in RAG systems.\n"
        )
        rag.add_course_document(str(doc))

        first = make_tool_use_response(
            "search_course_content",
            {"query": "source tracking"},
            "toolu_sources_001",
        )
        second = make_text_response("Source tracking is explained in the intro.")

        with patch.object(rag.ai_generator.client.messages, "create",
                          side_effect=[first, second]):
            _, sources = rag.query("Explain source tracking")

        assert isinstance(sources, list)
        if sources:
            for src in sources:
                assert "label" in src, f"Source missing 'label': {src}"
                assert "url" in src, f"Source missing 'url': {src}"

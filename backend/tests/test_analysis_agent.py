import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault(
    "SUPABASE_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/postgres",
)

from app.agent.analysis_agent import (
    ANALYSIS_INSTRUCTIONS,
    MAX_ANALYSIS_QUERIES,
    RESULT_PREVIEW_ROWS,
    AnalysisAlreadyRunError,
    AnalysisNotFoundError,
    _build_analysis_agent,
    build_analysis_prompt,
    generate_analysis_query,
    parse_analysis_response,
    run_analysis_chain,
)


class ParseAnalysisResponseTests(unittest.TestCase):
    def test_run_query_json(self) -> None:
        parsed = parse_analysis_response(
            '{"action": "run_query", "sql": "SELECT 1"}'
        )
        self.assertEqual(parsed, {"action": "run_query", "sql": "SELECT 1"})

    def test_synthesize_json(self) -> None:
        parsed = parse_analysis_response(
            '{"action": "synthesize", "answer": "West leads."}'
        )
        self.assertEqual(
            parsed, {"action": "synthesize", "answer": "West leads."}
        )

    def test_json_fence(self) -> None:
        parsed = parse_analysis_response(
            '```json\n{"action": "run_query", "sql": "SELECT id FROM t"}\n```'
        )
        self.assertEqual(parsed["sql"], "SELECT id FROM t")

    def test_sql_fence_fallback(self) -> None:
        parsed = parse_analysis_response("```sql\nSELECT region FROM sales\n```")
        self.assertEqual(parsed["action"], "run_query")
        self.assertEqual(parsed["sql"], "SELECT region FROM sales")

    def test_json_embedded_in_prose(self) -> None:
        parsed = parse_analysis_response(
            'Sure. {"action": "synthesize", "answer": "Done."} thanks'
        )
        self.assertEqual(parsed["answer"], "Done.")

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_analysis_response("I cannot help with that.")


class AnalysisPromptTests(unittest.TestCase):
    def test_prior_results_are_plain_text(self) -> None:
        prompt = build_analysis_prompt(
            "Compare A and B",
            prior_results=[
                {
                    "status": "ok",
                    "columns": ["name", "total"],
                    "rows": [{"name": "A", "total": 10}],
                    "row_count": 1,
                }
            ],
        )
        self.assertIn("Original question: Compare A and B", prompt)
        self.assertIn("Here is the result of your previous query:", prompt)
        self.assertIn("columns: ['name', 'total']", prompt)
        self.assertIn("Do you need another query", prompt)
        self.assertNotIn("tool result", prompt.lower())

    def test_force_synthesize_instruction(self) -> None:
        prompt = build_analysis_prompt(
            "Compare A and B",
            prior_results=[{"status": "ok", "columns": ["x"], "rows": [], "row_count": 0}],
            force_synthesize=True,
        )
        self.assertIn(
            "Write your final answer now using only what you have — "
            "no more queries are available.",
            prompt,
        )
        self.assertIn("Do not call introspect_schema", prompt)
        self.assertNotIn("Do you need another query", prompt)

    def test_schema_in_session_skips_repeat_introspect(self) -> None:
        prompt = build_analysis_prompt(
            "Compare A and B",
            prior_results=[{"status": "ok", "columns": ["x"], "rows": [], "row_count": 0}],
            schema_in_session=True,
        )
        self.assertIn("Do not call introspect_schema again", prompt)

    def test_truncates_large_result_sets(self) -> None:
        rows = [{"n": i} for i in range(RESULT_PREVIEW_ROWS + 25)]
        prompt = build_analysis_prompt(
            "q",
            prior_results=[{"status": "ok", "columns": ["n"], "rows": rows, "row_count": len(rows)}],
        )
        self.assertIn(f"row_count: {len(rows)}", prompt)
        self.assertNotIn(f'"n": {RESULT_PREVIEW_ROWS + 1}', prompt)

    def test_instructions_forbid_execution(self) -> None:
        text = " ".join(ANALYSIS_INSTRUCTIONS)
        self.assertIn("You NEVER execute SQL", text)
        self.assertIn("no execute_query tool", text)
        self.assertIn("You may ONLY join two tables using a relationship explicitly present", text)
        self.assertIn("same conversation", text)
        self.assertNotIn("call execute_query", text.lower())


class AnalysisAgentToolsTests(unittest.TestCase):
    def test_agent_has_only_introspect_schema(self) -> None:
        sentinel = object()
        captured: dict = {}

        def fake_agent(**kwargs):
            captured.update(kwargs)
            agent = MagicMock()
            agent.tools = kwargs.get("tools")
            return agent

        with (
            patch(
                "app.agent.analysis_agent.create_introspect_schema_tool",
                return_value=sentinel,
            ),
            patch("app.agent.analysis_agent.OpenAIChat"),
            patch("app.agent.analysis_agent.Agent", side_effect=fake_agent),
        ):
            agent = _build_analysis_agent(uuid4(), MagicMock())

        self.assertEqual(agent.tools, [sentinel])
        self.assertEqual(captured["tools"], [sentinel])
        self.assertEqual(len(captured["tools"]), 1)
        self.assertTrue(captured["add_history_to_context"])
        self.assertTrue(captured["store_tool_messages"])
        self.assertIsNotNone(captured["db"])
        self.assertEqual(captured["session_id"], None)

    def test_agent_forwards_session_id(self) -> None:
        captured: dict = {}

        def fake_agent(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with (
            patch(
                "app.agent.analysis_agent.create_introspect_schema_tool",
                return_value=object(),
            ),
            patch("app.agent.analysis_agent.OpenAIChat"),
            patch("app.agent.analysis_agent.Agent", side_effect=fake_agent),
        ):
            _build_analysis_agent(uuid4(), MagicMock(), session_id="analysis-session")

        self.assertEqual(captured["session_id"], "analysis-session")
        self.assertTrue(captured["add_history_to_context"])


class RunAnalysisChainTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.project_id = uuid4()
        self.analysis_id = uuid4()
        self.attempt_1 = uuid4()
        self.attempt_2 = uuid4()
        self.pool = MagicMock()
        self.first = {
            "id": self.attempt_1,
            "project_id": self.project_id,
            "question": "Compare revenue by region",
            "generated_sql": "SELECT region, SUM(revenue) FROM sales GROUP BY region",
            "execution_status": "not_run",
        }
        self.exec_result = {
            "status": "ok",
            "columns": ["region", "sum"],
            "rows": [{"region": "west", "sum": 10}],
            "row_count": 1,
        }
        self.session_agent = MagicMock()
        self.session_agent.tools = [object()]
        self.build_patcher = patch(
            "app.agent.analysis_agent._build_analysis_agent",
            return_value=self.session_agent,
        )
        self.mock_build = self.build_patcher.start()
        self.addCleanup(self.build_patcher.stop)

    async def test_stops_after_one_query_when_agent_synthesizes(self) -> None:
        gen_calls: list[dict] = []

        async def gen_side_effect(**kwargs):
            gen_calls.append(kwargs)
            if kwargs.get("force_synthesize"):
                return {"action": "synthesize", "answer": "West is higher."}
            return {"action": "synthesize", "answer": "enough after one"}

        with (
            patch(
                "app.agent.analysis_agent.learnings.list_attempts_for_analysis",
                new_callable=AsyncMock,
                return_value=[self.first],
            ),
            patch(
                "app.agent.analysis_agent.learnings.update_attempt_execution",
                new_callable=AsyncMock,
            ),
            patch(
                "app.agent.analysis_agent.learnings.insert_query_attempt",
                new_callable=AsyncMock,
            ) as insert,
            patch(
                "app.agent.analysis_agent.execute_sql_for_project",
                new_callable=AsyncMock,
                return_value=self.exec_result,
            ) as execute,
            patch(
                "app.agent.analysis_agent.generate_analysis_query",
                side_effect=gen_side_effect,
            ),
        ):
            result = await run_analysis_chain(
                project_id=self.project_id,
                analysis_id=self.analysis_id,
                pool=self.pool,
            )

        self.assertEqual(execute.await_count, 1)
        insert.assert_not_awaited()
        self.assertEqual(len(result["queries_used"]), 1)
        self.assertEqual(result["answer"], "West is higher.")
        self.assertFalse(gen_calls[0].get("force_synthesize"))
        self.assertTrue(gen_calls[-1].get("force_synthesize"))
        self.assertEqual(self.mock_build.call_count, 1)
        self.assertEqual(
            self.mock_build.call_args.kwargs.get("session_id"),
            str(self.analysis_id),
        )
        for call in gen_calls:
            self.assertIs(call.get("agent"), self.session_agent)

    async def test_never_exceeds_two_executes(self) -> None:
        self.assertEqual(MAX_ANALYSIS_QUERIES, 2)
        gen_calls: list[dict] = []

        async def gen_side_effect(**kwargs):
            gen_calls.append(kwargs)
            if kwargs.get("force_synthesize"):
                return {"action": "synthesize", "answer": "final synthesis"}
            return {"action": "run_query", "sql": "SELECT 2"}

        second = {
            "id": self.attempt_2,
            "project_id": self.project_id,
            "question": self.first["question"],
            "generated_sql": "SELECT 2",
            "execution_status": "not_run",
        }

        with (
            patch(
                "app.agent.analysis_agent.learnings.list_attempts_for_analysis",
                new_callable=AsyncMock,
                return_value=[self.first],
            ),
            patch(
                "app.agent.analysis_agent.learnings.update_attempt_execution",
                new_callable=AsyncMock,
            ),
            patch(
                "app.agent.analysis_agent.learnings.insert_query_attempt",
                new_callable=AsyncMock,
                return_value=second,
            ) as insert,
            patch(
                "app.agent.analysis_agent.execute_sql_for_project",
                new_callable=AsyncMock,
                return_value=self.exec_result,
            ) as execute,
            patch(
                "app.agent.analysis_agent.generate_analysis_query",
                side_effect=gen_side_effect,
            ),
        ):
            result = await run_analysis_chain(
                project_id=self.project_id,
                analysis_id=self.analysis_id,
                pool=self.pool,
            )

        self.assertEqual(execute.await_count, 2)
        self.assertEqual(insert.await_count, 1)
        self.assertEqual(len(result["queries_used"]), 2)
        non_force = [c for c in gen_calls if not c.get("force_synthesize")]
        force = [c for c in gen_calls if c.get("force_synthesize")]
        self.assertEqual(len(non_force), 1)
        self.assertEqual(len(force), 1)
        self.assertEqual(result["answer"], "final synthesis")
        self.assertEqual(self.mock_build.call_count, 1)
        agents = [c.get("agent") for c in gen_calls]
        self.assertEqual(len(agents), 2)
        self.assertTrue(all(a is self.session_agent for a in agents))
        self.assertFalse(gen_calls[0].get("schema_in_session"))
        self.assertTrue(gen_calls[1].get("schema_in_session"))
        self.assertTrue(force[0].get("schema_in_session"))

    async def test_force_synthesize_called_after_loop(self) -> None:
        async def gen_side_effect(**kwargs):
            if kwargs.get("force_synthesize"):
                self.assertEqual(len(kwargs.get("prior_results") or []), 1)
                return {"action": "synthesize", "answer": "ok"}
            return {"action": "synthesize", "answer": "early"}

        with (
            patch(
                "app.agent.analysis_agent.learnings.list_attempts_for_analysis",
                new_callable=AsyncMock,
                return_value=[self.first],
            ),
            patch(
                "app.agent.analysis_agent.learnings.update_attempt_execution",
                new_callable=AsyncMock,
            ),
            patch(
                "app.agent.analysis_agent.execute_sql_for_project",
                new_callable=AsyncMock,
                return_value=self.exec_result,
            ),
            patch(
                "app.agent.analysis_agent.generate_analysis_query",
                side_effect=gen_side_effect,
            ) as gen,
        ):
            await run_analysis_chain(
                project_id=self.project_id,
                analysis_id=self.analysis_id,
                pool=self.pool,
            )

        self.assertGreaterEqual(gen.await_count, 2)
        self.assertTrue(gen.await_args.kwargs.get("force_synthesize"))
        self.assertIs(gen.await_args.kwargs.get("agent"), self.session_agent)
        self.assertEqual(self.mock_build.call_count, 1)

    async def test_missing_analysis_raises(self) -> None:
        with patch(
            "app.agent.analysis_agent.learnings.list_attempts_for_analysis",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with self.assertRaises(AnalysisNotFoundError):
                await run_analysis_chain(
                    project_id=self.project_id,
                    analysis_id=self.analysis_id,
                    pool=self.pool,
                )

    async def test_already_run_raises(self) -> None:
        already = {**self.first, "execution_status": "success"}
        with patch(
            "app.agent.analysis_agent.learnings.list_attempts_for_analysis",
            new_callable=AsyncMock,
            return_value=[already],
        ):
            with self.assertRaises(AnalysisAlreadyRunError):
                await run_analysis_chain(
                    project_id=self.project_id,
                    analysis_id=self.analysis_id,
                    pool=self.pool,
                )
        self.mock_build.assert_not_called()


class GenerateAnalysisQuerySessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_path_builds_fresh_agent(self) -> None:
        agent = MagicMock()
        agent.tools = []
        agent.arun = AsyncMock(
            return_value=MagicMock(
                content='{"action": "run_query", "sql": "SELECT 1"}',
                tools=[],
            )
        )
        with (
            patch(
                "app.agent.analysis_agent.get_relevant_learnings",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.agent.analysis_agent._build_analysis_agent",
                return_value=agent,
            ) as build,
        ):
            result = await generate_analysis_query(
                project_id=uuid4(),
                pool=MagicMock(),
                question="q",
            )

        build.assert_called_once()
        agent.arun.assert_awaited_once()
        self.assertEqual(result["sql"], "SELECT 1")

    async def test_run_path_does_not_rebuild_agent(self) -> None:
        agent = MagicMock()
        agent.tools = []
        agent.arun = AsyncMock(
            return_value=MagicMock(
                content='{"action": "synthesize", "answer": "West leads."}',
                tools=[],
            )
        )
        with (
            patch(
                "app.agent.analysis_agent.get_relevant_learnings",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.agent.analysis_agent._build_analysis_agent") as build,
        ):
            result = await generate_analysis_query(
                project_id=uuid4(),
                pool=MagicMock(),
                question="q",
                prior_results=[
                    {"status": "ok", "columns": ["x"], "rows": [], "row_count": 0}
                ],
                force_synthesize=True,
                agent=agent,
                schema_in_session=True,
            )

        build.assert_not_called()
        agent.arun.assert_awaited_once()
        prompt = agent.arun.await_args.args[0]
        self.assertIn("Do not call introspect_schema", prompt)
        self.assertEqual(result["answer"], "West leads.")


if __name__ == "__main__":
    unittest.main()

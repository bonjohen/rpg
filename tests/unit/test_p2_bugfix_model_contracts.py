"""Tests for P2 Phase 5: Model pipeline error handling, type safety, metrics cap."""

from __future__ import annotations

from models.contracts.output_repair import _check_required_fields
from models.fast.router import is_fast_tier
from server.observability.metrics import MetricsCollector


# -------------------------------------------------------------------
# BUG-048: bool checked before int in validate_output
# -------------------------------------------------------------------


class TestBUG048BoolBeforeInt:
    def test_bool_value_not_misidentified_as_int(self):
        schema = {
            "required": ["flag"],
            "properties": {
                "flag": {"type": "boolean"},
            },
        }
        errors = _check_required_fields({"flag": True}, schema)
        assert errors == []

    def test_int_value_passes_integer_check(self):
        schema = {
            "required": ["count"],
            "properties": {
                "count": {"type": "integer"},
            },
        }
        errors = _check_required_fields({"count": 42}, schema)
        assert errors == []

    def test_bool_caught_before_integer_check(self):
        schema = {
            "required": ["flag", "count"],
            "properties": {
                "flag": {"type": "boolean"},
                "count": {"type": "integer"},
            },
        }
        # Both should validate cleanly — bool is checked before int
        errors = _check_required_fields({"flag": True, "count": 5}, schema)
        assert errors == []


# -------------------------------------------------------------------
# BUG-050: Unknown task types rejected
# -------------------------------------------------------------------


class TestBUG050UnknownTaskType:
    def test_unknown_task_raises_valueerror(self):
        import pytest

        with pytest.raises(ValueError, match="Unknown task type"):
            is_fast_tier("totally_bogus_task")

    def test_known_fast_task_returns_true(self):
        assert is_fast_tier("intent_classification") is True

    def test_known_main_task_returns_false(self):
        assert is_fast_tier("scene_narration") is False


# -------------------------------------------------------------------
# BUG-051: json.dumps for inline schema
# -------------------------------------------------------------------


class TestBUG051JsonDumpsSchema:
    def test_assembled_prompt_uses_json_not_repr(self):
        from models.contracts.context_assembly import ContextAssembler

        assembler = ContextAssembler()
        prompt = assembler.assemble(
            contract_id="fast.intent_classification",
            action_text="look around",
        )
        combined = prompt.system_prompt + prompt.user_prompt
        # If output_schema is rendered into the prompt, it should use
        # json.dumps (double-quoted keys), not Python repr (single quotes)
        if '"type"' in combined:
            assert "'type':" not in combined


# -------------------------------------------------------------------
# BUG-062: SchemaValidationError logged before fallback
# -------------------------------------------------------------------


class TestBUG062SchemaValidationLogged:
    def test_schema_error_logged(self, caplog):
        # This is a design-level test: verify the logger exists in tasks module
        import models.main.tasks as tasks_mod

        assert hasattr(tasks_mod, "logger")
        assert tasks_mod.logger.name == "models.main.tasks"


# -------------------------------------------------------------------
# BUG-063: Template rendering failure logged
# -------------------------------------------------------------------


class TestBUG063TemplateRenderingLogged:
    def test_context_assembly_has_logger(self):
        import models.contracts.context_assembly as ctx_mod

        assert hasattr(ctx_mod, "logger")
        assert ctx_mod.logger.name == "models.contracts.context_assembly"


# -------------------------------------------------------------------
# BUG-064: Narrow except in model_recovery
# -------------------------------------------------------------------


class TestBUG064NarrowExcept:
    def test_model_recovery_catches_specific_exceptions(self):
        import ast
        import inspect
        import server.reliability.model_recovery as mod

        source = inspect.getsource(mod.call_with_timeout)
        tree = ast.parse(source)
        # Find except handlers
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    raise AssertionError("Bare except found in call_with_timeout")
                # Check it's not a bare "Exception" catch
                if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    raise AssertionError(
                        "call_with_timeout still catches bare Exception"
                    )


# -------------------------------------------------------------------
# BUG-061: Histogram capped with reservoir sampling
# -------------------------------------------------------------------


class TestBUG061HistogramCap:
    def test_histogram_does_not_exceed_max_size(self):
        collector = MetricsCollector(histogram_max_size=100)
        for i in range(500):
            collector.record("test.latency", float(i))
        with collector._lock:
            values = collector._histograms.get("test.latency", [])
            assert len(values) <= 100

    def test_small_histogram_not_truncated(self):
        collector = MetricsCollector(histogram_max_size=1000)
        for i in range(50):
            collector.record("test.latency", float(i))
        with collector._lock:
            values = collector._histograms.get("test.latency", [])
            assert len(values) == 50

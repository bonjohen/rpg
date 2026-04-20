"""Schema validation and output-repair pipeline.

Formalises the repair pipeline that currently lives scattered across
models/main/tasks.py and models/fast/tasks.py into a single, testable
module driven by prompt contracts.

Pipeline:
  1. validate_output -- parse JSON and check against contract schema.
  2. repair_output   -- if invalid, send to fast model for repair.
  3. get_fallback    -- if repair fails, return contract fallback_output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from models.contracts.fast_contracts import FAST_CONTRACTS, PromptContract
from models.contracts.main_contracts import MAIN_CONTRACTS
from models.fast.instrumentation import ModelCallLog


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of validating model output against a contract schema."""

    is_valid: bool
    parsed_data: dict | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class RepairResult:
    """Result of the full validate-repair-fallback pipeline."""

    success: bool
    data: dict
    repair_attempted: bool = False
    repair_succeeded: bool = False
    fallback_used: bool = False
    log: ModelCallLog | None = None


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _check_required_fields(data: dict, schema: dict) -> list[str]:
    """Check that all required fields are present and have correct basic types."""
    errors: list[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field_name in required:
        if field_name not in data:
            errors.append(f"Missing required field: '{field_name}'")
            continue

        prop_schema = properties.get(field_name, {})
        value = data[field_name]

        # Type checking
        expected_type = prop_schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            errors.append(
                f"Field '{field_name}' must be a string, got {type(value).__name__}"
            )
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(
                f"Field '{field_name}' must be a boolean, got {type(value).__name__}"
            )
        elif expected_type == "integer" and not isinstance(value, int):
            errors.append(
                f"Field '{field_name}' must be an integer, got {type(value).__name__}"
            )
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(
                f"Field '{field_name}' must be an array, got {type(value).__name__}"
            )
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(
                f"Field '{field_name}' must be an object, got {type(value).__name__}"
            )

        # Enum checking
        enum_values = prop_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            errors.append(
                f"Field '{field_name}' must be one of {enum_values}, got {value!r}"
            )

    return errors


def validate_output(contract: PromptContract, raw_output: str) -> ValidationResult:
    """Validate raw model output against a contract's schema.

    Args:
        contract: The prompt contract defining the expected schema.
        raw_output: Raw JSON string from the model.

    Returns:
        ValidationResult with parsed data if valid.
    """
    # Step 1: JSON parse
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid JSON: {exc}"],
        )

    if not isinstance(data, dict):
        return ValidationResult(
            is_valid=False,
            errors=[f"Expected JSON object, got {type(data).__name__}"],
        )

    # Step 2: Schema validation
    errors = _check_required_fields(data, contract.output_schema)
    if errors:
        return ValidationResult(
            is_valid=False,
            parsed_data=data,
            errors=errors,
        )

    return ValidationResult(
        is_valid=True,
        parsed_data=data,
    )


# ---------------------------------------------------------------------------
# Contract lookup helper
# ---------------------------------------------------------------------------


def _find_contract(contract_id: str) -> PromptContract:
    """Find a contract by ID across both registries."""
    if contract_id in FAST_CONTRACTS:
        return FAST_CONTRACTS[contract_id]
    if contract_id in MAIN_CONTRACTS:
        return MAIN_CONTRACTS[contract_id]
    raise KeyError(f"No contract found: {contract_id!r}")


# ---------------------------------------------------------------------------
# Repair pipeline
# ---------------------------------------------------------------------------


class RepairPipeline:
    """Full validate-repair-fallback pipeline."""

    def __init__(self, fast_adapter: Any = None) -> None:
        """Initialize with an optional fast adapter for repair calls.

        Args:
            fast_adapter: OllamaFastAdapter instance (optional). If None,
                repair step is skipped and fallback is used directly.
        """
        self._fast_adapter = fast_adapter

    def validate(self, contract_id: str, raw_output: str) -> ValidationResult:
        """Validate output against the contract's schema."""
        contract = _find_contract(contract_id)
        return validate_output(contract, raw_output)

    async def repair(
        self,
        contract_id: str,
        raw_output: str,
        *,
        trace_id: str = "",
    ) -> RepairResult:
        """Full repair pipeline: validate -> repair -> fallback.

        1. Validate raw_output against contract schema.
        2. If valid, return as-is.
        3. If invalid and fast_adapter is available, attempt repair.
        4. If repair fails or no adapter, return contract fallback.
        """
        contract = _find_contract(contract_id)

        # Step 1: Validate
        validation = validate_output(contract, raw_output)
        if validation.is_valid and validation.parsed_data is not None:
            return RepairResult(
                success=True,
                data=validation.parsed_data,
            )

        # Step 2: Attempt repair via fast model
        repair_log: ModelCallLog | None = None
        if self._fast_adapter is not None:
            from models.fast.tasks import repair_schema

            schema_desc = json.dumps(contract.output_schema)
            repaired, repair_log = await repair_schema(
                self._fast_adapter,
                raw_output,
                schema_desc,
                trace_id=trace_id,
            )

            if repaired.success:
                # Validate the repaired output
                repair_validation = validate_output(contract, repaired.repaired_json)
                if (
                    repair_validation.is_valid
                    and repair_validation.parsed_data is not None
                ):
                    return RepairResult(
                        success=True,
                        data=repair_validation.parsed_data,
                        repair_attempted=True,
                        repair_succeeded=True,
                        log=repair_log,
                    )

        # Step 3: Fallback
        return RepairResult(
            success=True,
            data=dict(contract.fallback_output),
            repair_attempted=self._fast_adapter is not None,
            repair_succeeded=False,
            fallback_used=True,
            log=repair_log,
        )

    def get_fallback(self, contract_id: str) -> dict:
        """Return the contract's deterministic fallback output."""
        contract = _find_contract(contract_id)
        return dict(contract.fallback_output)

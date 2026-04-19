"""Prompt size limits and truncation policies.

Per model_routing.md:
  - Fast tier: target < 2K tokens, hard limit 4K tokens.
  - Main tier: target < 16K tokens, hard limit 32K tokens (256K deep-context).
  - Truncation order: drop oldest chat history first, then oldest non-critical
    facts. Never drop scene state or critical quest facts.

Token estimation uses a conservative 4 chars/token heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TruncationResult:
    """Result of a prompt size limit check."""

    within_target: bool
    within_hard_limit: bool
    estimated_tokens: int
    tier: str


@dataclass
class ScopedFact:
    """Minimal fact container for truncation (mirrors context_assembly.ScopedFact)."""

    fact_id: str = ""
    text: str = ""
    scope: str = "public"
    fact_type: str = ""
    is_critical: bool = False


class TruncationPolicy:
    """Prompt size limits and truncation logic."""

    FAST_TARGET_TOKENS: int = 2048
    FAST_HARD_LIMIT_TOKENS: int = 4096
    MAIN_TARGET_TOKENS: int = 16384
    MAIN_HARD_LIMIT_TOKENS: int = 32768
    MAIN_DEEP_CONTEXT_TOKENS: int = 262144  # 256K

    CHARS_PER_TOKEN: int = 4

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: len(text) // CHARS_PER_TOKEN."""
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def truncate_history(
        self,
        history_entries: list[str],
        current_prompt_tokens: int,
        max_tokens: int,
    ) -> tuple[list[str], bool]:
        """Drop oldest history entries until prompt fits within max_tokens.

        Args:
            history_entries: Messages oldest-first.
            current_prompt_tokens: Token estimate for the non-history part.
            max_tokens: Token budget.

        Returns:
            (remaining_entries, was_truncated) -- remaining is newest-first
            subset that fits.
        """
        if not history_entries:
            return [], False

        budget_chars = (max_tokens - current_prompt_tokens) * self.CHARS_PER_TOKEN
        if budget_chars <= 0:
            return [], bool(history_entries)

        # Keep newest entries within budget
        kept: list[str] = []
        used = 0
        was_truncated = False
        for entry in reversed(history_entries):
            cost = len(entry) + 1  # +1 for separator
            if used + cost > budget_chars:
                was_truncated = True
                break
            kept.append(entry)
            used += cost

        kept.reverse()
        if len(kept) < len(history_entries):
            was_truncated = True

        return kept, was_truncated

    def truncate_facts(
        self,
        facts: list[ScopedFact],
        current_tokens: int,
        max_tokens: int,
    ) -> tuple[list[ScopedFact], bool]:
        """Drop oldest non-critical facts to fit within budget.

        Preserves facts where is_critical is True. Drops from the
        beginning of the list (oldest first) among non-critical facts.

        Returns:
            (remaining_facts, was_truncated)
        """
        if not facts:
            return [], False

        total_fact_chars = sum(len(f.text) + 3 for f in facts)  # "- " + newline
        total_tokens = current_tokens + self.estimate_tokens("x" * total_fact_chars)

        if total_tokens <= max_tokens:
            return list(facts), False

        # Separate critical and non-critical
        critical = [f for f in facts if f.is_critical]
        non_critical = [f for f in facts if not f.is_critical]

        # Drop oldest non-critical facts until we fit
        budget_chars = (max_tokens - current_tokens) * self.CHARS_PER_TOKEN
        # Reserve space for critical facts
        critical_chars = sum(len(f.text) + 3 for f in critical)
        remaining_budget = budget_chars - critical_chars

        if remaining_budget <= 0:
            return critical, bool(non_critical)

        # Keep newest non-critical facts within remaining budget
        kept_nc: list[ScopedFact] = []
        used = 0
        for fact in reversed(non_critical):
            cost = len(fact.text) + 3
            if used + cost > remaining_budget:
                break
            kept_nc.append(fact)
            used += cost

        kept_nc.reverse()
        was_truncated = len(kept_nc) < len(non_critical)
        return critical + kept_nc, was_truncated

    def check_limit(self, text: str, tier: str) -> TruncationResult:
        """Check whether text fits within the target and hard limit for a tier.

        Args:
            text: The full prompt text.
            tier: "fast" or "main".

        Returns:
            TruncationResult with target and hard limit checks.
        """
        tokens = self.estimate_tokens(text)

        if tier == "fast":
            return TruncationResult(
                within_target=tokens <= self.FAST_TARGET_TOKENS,
                within_hard_limit=tokens <= self.FAST_HARD_LIMIT_TOKENS,
                estimated_tokens=tokens,
                tier=tier,
            )
        else:
            return TruncationResult(
                within_target=tokens <= self.MAIN_TARGET_TOKENS,
                within_hard_limit=tokens <= self.MAIN_HARD_LIMIT_TOKENS,
                estimated_tokens=tokens,
                tier=tier,
            )

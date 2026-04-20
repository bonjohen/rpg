"""Scene revisit memory and recall engine — pure domain logic, no I/O.

Tracks which characters have visited which scenes, how many times, and
what they observed on those visits.  Used to:

  - Suppress redundant "you enter a bare stone room" narration on revisit
  - Gate triggers to "first visit only" via TriggerCondition.once
  - Build the "you recall..." context for LLM prompts
  - Give the referee accurate data about party knowledge

Design decisions:
  - SceneVisitRecord is the core data object; callers persist it.
  - MemoryEngine.record_visit() creates or updates a SceneVisitRecord.
  - MemoryEngine.recall_description() produces a concise recall string
    describing what the character saw on their last visit.
  - No DB calls. Everything is pure Python on plain data objects.

No imports from server.storage. Everything here is pure Python on domain types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from server.domain.helpers import new_id, utc_now


# ---------------------------------------------------------------------------
# Visit record
# ---------------------------------------------------------------------------


@dataclass
class SceneVisitRecord:
    """Tracks one character's visit history for one scene.

    One record per (character_id, scene_id) pair.  Updated on each visit.
    """

    record_id: str
    character_id: str
    player_id: str
    scene_id: str
    campaign_id: str
    first_visited_at: datetime
    last_visited_at: datetime
    visit_count: int = 1
    # Public description observed on the first visit
    first_visit_description: str = ""
    # Public description observed on the most recent visit
    last_visit_description: str = ""
    # IDs of KnowledgeFacts discovered in this scene by this character
    discovered_fact_ids: list[str] = field(default_factory=list)
    # IDs of items seen (not necessarily hidden) on most recent visit
    observed_item_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class VisitResult:
    """Returned by MemoryEngine.record_visit()."""

    is_first_visit: bool
    record: SceneVisitRecord
    # True if visit_count == 1 (same as is_first_visit, for clarity)
    just_created: bool = False


@dataclass
class RecallResult:
    """Returned by MemoryEngine.recall_description()."""

    has_visited: bool
    recall_text: str = ""
    visit_count: int = 0


# ---------------------------------------------------------------------------
# MemoryEngine
# ---------------------------------------------------------------------------


class MemoryEngine:
    """Stateless engine for scene visit tracking and recall.

    Callers are responsible for:
      - Loading the existing SceneVisitRecord for (character_id, scene_id)
        before calling record_visit (pass None if none exists yet).
      - Persisting the returned SceneVisitRecord.
      - Passing discovered fact_ids back via add_discovered_fact().

    The engine never calls any storage layer directly.
    """

    def record_visit(
        self,
        character_id: str,
        player_id: str,
        scene_id: str,
        campaign_id: str,
        scene_description: str,
        existing_record: SceneVisitRecord | None,
        observed_item_ids: list[str] | None = None,
    ) -> VisitResult:
        """Record that a character visited a scene.

        If ``existing_record`` is None a new one is created (first visit).
        Otherwise the existing record is updated (revisit).

        Args:
            character_id:      The character making the visit.
            player_id:         Their controlling player.
            scene_id:          The scene being visited.
            campaign_id:       The campaign this belongs to.
            scene_description: The public description shown to the character.
            existing_record:   Existing SceneVisitRecord or None.
            observed_item_ids: IDs of items visible in the scene on this visit.

        Returns:
            VisitResult.
        """
        now = utc_now()
        observed_item_ids = observed_item_ids or []

        if existing_record is None:
            record = SceneVisitRecord(
                record_id=new_id(),
                character_id=character_id,
                player_id=player_id,
                scene_id=scene_id,
                campaign_id=campaign_id,
                first_visited_at=now,
                last_visited_at=now,
                visit_count=1,
                first_visit_description=scene_description,
                last_visit_description=scene_description,
                observed_item_ids=list(observed_item_ids),
            )
            return VisitResult(is_first_visit=True, record=record, just_created=True)

        # Revisit
        existing_record.visit_count += 1
        existing_record.last_visited_at = now
        existing_record.last_visit_description = scene_description
        existing_record.observed_item_ids = list(observed_item_ids)
        return VisitResult(is_first_visit=False, record=existing_record)

    def add_discovered_fact(
        self,
        record: SceneVisitRecord,
        fact_id: str,
    ) -> SceneVisitRecord:
        """Append a newly-discovered fact_id to the visit record.

        Returns the updated record.  Caller must persist.
        Guards against duplicates.
        """
        if fact_id not in record.discovered_fact_ids:
            record.discovered_fact_ids.append(fact_id)
        return record

    def recall_description(
        self,
        character_id: str,
        scene_id: str,
        existing_record: SceneVisitRecord | None,
    ) -> RecallResult:
        """Produce a recall string for a character returning to a scene.

        If the character has never been here, returns has_visited=False.

        Args:
            character_id:    The character whose memory to consult.
            scene_id:        The target scene.
            existing_record: Their SceneVisitRecord, or None.

        Returns:
            RecallResult with a natural-language recall string.
        """
        if existing_record is None:
            return RecallResult(has_visited=False, recall_text="", visit_count=0)

        if (
            existing_record.character_id != character_id
            or existing_record.scene_id != scene_id
        ):
            return RecallResult(has_visited=False, recall_text="", visit_count=0)

        count = existing_record.visit_count
        description = existing_record.last_visit_description

        if count == 1:
            recall_text = f"You have been here once before. You recall: {description}"
        else:
            recall_text = (
                f"You have visited this place {count} times. You recall: {description}"
            )

        return RecallResult(
            has_visited=True,
            recall_text=recall_text,
            visit_count=count,
        )

    def has_character_visited(
        self,
        character_id: str,
        scene_id: str,
        records: list[SceneVisitRecord],
    ) -> bool:
        """Return True if ``character_id`` has any visit record for ``scene_id``.

        Args:
            character_id: The character to check.
            scene_id:     The scene to check.
            records:      All SceneVisitRecords to search.
        """
        return any(
            r.character_id == character_id and r.scene_id == scene_id for r in records
        )

    def scenes_visited_by_character(
        self,
        character_id: str,
        records: list[SceneVisitRecord],
    ) -> list[str]:
        """Return the list of scene_ids visited by a character, most recent first.

        Args:
            character_id: The character to query.
            records:      All SceneVisitRecords.
        """
        relevant = [r for r in records if r.character_id == character_id]
        relevant.sort(key=lambda r: r.last_visited_at, reverse=True)
        return [r.scene_id for r in relevant]

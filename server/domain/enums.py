"""State-machine enums for scene, turn, and action lifecycles."""

from enum import Enum


class SceneState(str, Enum):
    idle = "idle"
    prompting = "prompting"
    awaiting_actions = "awaiting_actions"
    resolving = "resolving"
    narrated = "narrated"
    paused = "paused"


class TurnWindowState(str, Enum):
    open = "open"
    all_ready = "all_ready"
    locked = "locked"
    resolving = "resolving"
    committed = "committed"
    aborted = "aborted"


class ActionState(str, Enum):
    draft = "draft"
    submitted = "submitted"
    validated = "validated"
    rejected = "rejected"
    resolved = "resolved"


class ScopeType(str, Enum):
    public = "public"
    private_referee = "private_referee"
    side_channel = "side_channel"
    referee_only = "referee_only"


class BehaviorMode(str, Enum):
    patrol = "patrol"
    ambush = "ambush"
    defend = "defend"
    pursue = "pursue"
    flee = "flee"
    guard = "guard"
    call_help = "call_help"
    idle = "idle"


class AwarenessState(str, Enum):
    unaware = "unaware"
    alert = "alert"
    aware = "aware"
    engaged = "engaged"


class ActionType(str, Enum):
    move = "move"
    inspect = "inspect"
    search = "search"
    interact = "interact"
    attack = "attack"
    defend = "defend"
    assist = "assist"
    use_item = "use_item"
    use_ability = "use_ability"
    question = "question"
    persuade = "persuade"
    threaten = "threaten"
    lie = "lie"
    bargain = "bargain"
    pass_turn = "pass_turn"
    hold = "hold"
    custom = "custom"


class ReadyState(str, Enum):
    not_ready = "not_ready"
    ready = "ready"
    passed = "passed"


class ValidationStatus(str, Enum):
    pending = "pending"
    valid = "valid"
    invalid = "invalid"


class KnowledgeFactType(str, Enum):
    clue = "clue"
    awareness_result = "awareness_result"
    npc_tell = "npc_tell"
    hidden_object = "hidden_object"
    secret_objective = "secret_objective"
    lore = "lore"
    trap = "trap"
    custom = "custom"


class QuestStatus(str, Enum):
    inactive = "inactive"
    active = "active"
    completed = "completed"
    failed = "failed"


class PuzzleStatus(str, Enum):
    unsolved = "unsolved"
    in_progress = "in_progress"
    solved = "solved"
    bypassed = "bypassed"

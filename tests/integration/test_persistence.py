"""Persistence integration tests.

Uses a real in-memory SQLite database (no mocks). Covers create, load,
update, and append-only turn log / replay for all core entities.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from server.domain.enums import (
    ActionType,
    AwarenessState,
    PuzzleStatus,
    QuestStatus,
    SceneState,
    ScopeType,
    TurnWindowState,
)
from server.storage.db import (
    create_all_tables,
    drop_all_tables,
    get_engine,
    get_session_factory,
)
from server.storage.repository import (
    CampaignRepo,
    CharacterRepo,
    CommittedActionRepo,
    ConversationScopeRepo,
    InventoryItemRepo,
    KnowledgeFactRepo,
    MonsterGroupRepo,
    NPCRepo,
    PlayerRepo,
    PuzzleStateRepo,
    QuestStateRepo,
    SceneRepo,
    TurnLogRepo,
    TurnWindowRepo,
    VisibilityGrantRepo,
)
from tests.fixtures.builders import (
    make_campaign,
    make_character,
    make_committed_action,
    make_conversation_scope,
    make_inventory_item,
    make_knowledge_fact,
    make_monster_group,
    make_npc,
    make_player,
    make_puzzle_state,
    make_quest_state,
    make_scene,
    make_turn_log_entry,
    make_turn_window,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    e = get_engine("sqlite:///:memory:")
    create_all_tables(e)
    yield e
    drop_all_tables(e)
    e.dispose()


@pytest.fixture
def session(engine):
    SessionLocal = get_session_factory(engine)
    with SessionLocal() as s:
        yield s


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


def test_campaign_create_and_load(session):
    repo = CampaignRepo(session)
    c = make_campaign(name="Dark Dungeon", telegram_group_id=9999)
    repo.save(c)
    session.commit()

    loaded = repo.get(c.campaign_id)
    assert loaded is not None
    assert loaded.name == "Dark Dungeon"
    assert loaded.telegram_group_id == 9999
    assert loaded.is_active is True


def test_campaign_update(session):
    repo = CampaignRepo(session)
    c = make_campaign()
    repo.save(c)
    session.commit()

    c.name = "Updated Name"
    c.is_active = False
    repo.save(c)
    session.commit()

    loaded = repo.get(c.campaign_id)
    assert loaded.name == "Updated Name"
    assert loaded.is_active is False


def test_campaign_get_by_telegram_group(session):
    repo = CampaignRepo(session)
    c = make_campaign(telegram_group_id=42)
    repo.save(c)
    session.commit()

    found = repo.get_by_telegram_group(42)
    assert found is not None
    assert found.campaign_id == c.campaign_id


def test_campaign_list_active(session):
    repo = CampaignRepo(session)
    c1 = make_campaign(telegram_group_id=1, is_active=True)
    c2 = make_campaign(telegram_group_id=2, is_active=False)
    repo.save(c1)
    repo.save(c2)
    session.commit()

    active = repo.list_active()
    ids = [c.campaign_id for c in active]
    assert c1.campaign_id in ids
    assert c2.campaign_id not in ids


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


def test_player_create_and_load(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    session.commit()

    p = make_player(campaign_id=camp.campaign_id, telegram_user_id=55555)
    PlayerRepo(session).save(p)
    session.commit()

    loaded = PlayerRepo(session).get(p.player_id)
    assert loaded.display_name == "Test Player"
    assert loaded.telegram_user_id == 55555


def test_player_get_by_telegram_user(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    p = make_player(campaign_id=camp.campaign_id, telegram_user_id=77777)
    PlayerRepo(session).save(p)
    session.commit()

    found = PlayerRepo(session).get_by_telegram_user(camp.campaign_id, 77777)
    assert found is not None
    assert found.player_id == p.player_id


def test_player_list_for_campaign(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    repo = PlayerRepo(session)
    for i in range(3):
        repo.save(make_player(campaign_id=camp.campaign_id, telegram_user_id=i + 1))
    session.commit()

    players = repo.list_for_campaign(camp.campaign_id)
    assert len(players) == 3


# ---------------------------------------------------------------------------
# Scene and Character
# ---------------------------------------------------------------------------


def test_scene_create_and_load(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id, name="The Vault")
    SceneRepo(session).save(scene)
    session.commit()

    loaded = SceneRepo(session).get(scene.scene_id)
    assert loaded.name == "The Vault"
    assert loaded.state == SceneState.idle


def test_scene_state_update(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    session.commit()

    scene.state = SceneState.awaiting_actions
    SceneRepo(session).save(scene)
    session.commit()

    loaded = SceneRepo(session).get(scene.scene_id)
    assert loaded.state == SceneState.awaiting_actions


def test_character_create_and_load(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    player = make_player(campaign_id=camp.campaign_id)
    PlayerRepo(session).save(player)
    char = make_character(
        player_id=player.player_id,
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        name="Aragorn",
        stats={"str": 18, "dex": 14},
    )
    CharacterRepo(session).save(char)
    session.commit()

    loaded = CharacterRepo(session).get(char.character_id)
    assert loaded.name == "Aragorn"
    assert loaded.stats["str"] == 18
    assert loaded.scene_id == scene.scene_id


# ---------------------------------------------------------------------------
# TurnWindow and CommittedAction
# ---------------------------------------------------------------------------


def test_turn_window_create_and_load(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    tw = make_turn_window(
        campaign_id=camp.campaign_id, scene_id=scene.scene_id, turn_number=1
    )
    TurnWindowRepo(session).save(tw)
    session.commit()

    loaded = TurnWindowRepo(session).get(tw.turn_window_id)
    assert loaded.state == TurnWindowState.open
    assert loaded.turn_number == 1


def test_turn_window_state_transition(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    tw = make_turn_window(campaign_id=camp.campaign_id, scene_id=scene.scene_id)
    TurnWindowRepo(session).save(tw)
    session.commit()

    tw.state = TurnWindowState.locked
    tw.locked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    TurnWindowRepo(session).save(tw)
    session.commit()

    loaded = TurnWindowRepo(session).get(tw.turn_window_id)
    assert loaded.state == TurnWindowState.locked
    assert loaded.locked_at is not None


def test_one_committed_action_per_player_per_window(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    player = make_player(campaign_id=camp.campaign_id)
    PlayerRepo(session).save(player)
    char = make_character(player_id=player.player_id, campaign_id=camp.campaign_id)
    CharacterRepo(session).save(char)
    tw = make_turn_window(campaign_id=camp.campaign_id, scene_id=scene.scene_id)
    TurnWindowRepo(session).save(tw)

    action = make_committed_action(
        turn_window_id=tw.turn_window_id,
        player_id=player.player_id,
        character_id=char.character_id,
        declared_action_type=ActionType.move,
    )
    CommittedActionRepo(session).save(action)
    session.commit()

    found = CommittedActionRepo(session).get_for_player_in_window(
        tw.turn_window_id, player.player_id
    )
    assert found is not None
    assert found.action_id == action.action_id


# ---------------------------------------------------------------------------
# Append-only TurnLog and Replay
# ---------------------------------------------------------------------------


def test_turn_log_append_only(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)

    log_repo = TurnLogRepo(session)
    entries = []
    for i in range(3):
        tw = make_turn_window(campaign_id=camp.campaign_id, scene_id=scene.scene_id)
        TurnWindowRepo(session).save(tw)
        entry = make_turn_log_entry(
            campaign_id=camp.campaign_id,
            scene_id=scene.scene_id,
            turn_window_id=tw.turn_window_id,
            turn_number=i + 1,
            narration=f"Turn {i + 1} narration.",
        )
        log_repo.append(entry)
        entries.append(entry)
    session.commit()

    loaded = log_repo.list_for_campaign(camp.campaign_id)
    assert len(loaded) == 3
    assert [e.turn_number for e in loaded] == [1, 2, 3]
    assert loaded[0].narration == "Turn 1 narration."


def test_turn_log_replay_preserves_order(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)

    log_repo = TurnLogRepo(session)
    for i in range(5):
        tw = make_turn_window(campaign_id=camp.campaign_id, scene_id=scene.scene_id)
        TurnWindowRepo(session).save(tw)
        log_repo.append(
            make_turn_log_entry(
                campaign_id=camp.campaign_id,
                scene_id=scene.scene_id,
                turn_window_id=tw.turn_window_id,
                turn_number=i + 1,
                state_snapshot={"turn": i + 1},
            )
        )
    session.commit()

    loaded = log_repo.list_for_campaign(camp.campaign_id)
    numbers = [e.turn_number for e in loaded]
    assert numbers == sorted(numbers)


# ---------------------------------------------------------------------------
# NPC and MonsterGroup
# ---------------------------------------------------------------------------


def test_npc_create_and_update_memory_tags(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)

    npc = make_npc(
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        name="Old Aldric",
        trust_by_player={"player-1": 10},
    )
    NPCRepo(session).save(npc)
    session.commit()

    npc.memory_tags.append("player-1 returned heirloom")
    npc.trust_by_player["player-1"] = 40
    NPCRepo(session).save(npc)
    session.commit()

    loaded = NPCRepo(session).get(npc.npc_id)
    assert "player-1 returned heirloom" in loaded.memory_tags
    assert loaded.trust_by_player["player-1"] == 40


def test_monster_group_create_and_load(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)

    mg = make_monster_group(
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        unit_type="skeleton",
        count=5,
    )
    MonsterGroupRepo(session).save(mg)
    session.commit()

    loaded = MonsterGroupRepo(session).get(mg.monster_group_id)
    assert loaded.unit_type == "skeleton"
    assert loaded.count == 5
    assert loaded.awareness_state == AwarenessState.unaware


# ---------------------------------------------------------------------------
# InventoryItem, QuestState, PuzzleState
# ---------------------------------------------------------------------------


def test_inventory_item_owned_by_character(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    player = make_player(campaign_id=camp.campaign_id)
    PlayerRepo(session).save(player)
    char = make_character(player_id=player.player_id, campaign_id=camp.campaign_id)
    CharacterRepo(session).save(char)

    item = make_inventory_item(
        campaign_id=camp.campaign_id,
        owner_character_id=char.character_id,
        name="Magic Staff",
    )
    InventoryItemRepo(session).save(item)
    session.commit()

    items = InventoryItemRepo(session).list_for_character(char.character_id)
    assert len(items) == 1
    assert items[0].name == "Magic Staff"


def test_quest_state_activate_and_complete(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)

    qs = make_quest_state(campaign_id=camp.campaign_id, quest_id="find_the_relic")
    QuestStateRepo(session).save(qs)
    session.commit()

    qs.status = QuestStatus.active
    qs.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    QuestStateRepo(session).save(qs)
    session.commit()

    loaded = QuestStateRepo(session).get(qs.quest_state_id)
    assert loaded.status == QuestStatus.active
    assert loaded.started_at is not None


def test_puzzle_state_attempt_and_solve(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)

    ps = make_puzzle_state(
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        puzzle_id="lever_puzzle",
    )
    PuzzleStateRepo(session).save(ps)
    session.commit()

    ps.attempts += 1
    ps.state_slots["lever_a"] = True
    ps.status = PuzzleStatus.in_progress
    PuzzleStateRepo(session).save(ps)
    session.commit()

    loaded = PuzzleStateRepo(session).get(ps.puzzle_state_id)
    assert loaded.attempts == 1
    assert loaded.state_slots["lever_a"] is True
    assert loaded.status == PuzzleStatus.in_progress


# ---------------------------------------------------------------------------
# KnowledgeFact and VisibilityGrant
# ---------------------------------------------------------------------------


def test_knowledge_fact_scoped_private(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    scope = make_conversation_scope(
        campaign_id=camp.campaign_id, scope_type=ScopeType.private_referee
    )
    ConversationScopeRepo(session).save(scope)
    session.commit()

    fact = make_knowledge_fact(
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        owner_scope_id=scope.scope_id,
        payload="You notice a thin draft from behind the west wall.",
    )
    KnowledgeFactRepo(session).save(fact)
    session.commit()

    loaded_facts = KnowledgeFactRepo(session).list_for_scope(scope.scope_id)
    assert len(loaded_facts) == 1
    assert "west wall" in loaded_facts[0].payload


def test_knowledge_fact_not_in_other_scope(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)

    private_scope = make_conversation_scope(
        campaign_id=camp.campaign_id, scope_type=ScopeType.private_referee
    )
    public_scope = make_conversation_scope(
        campaign_id=camp.campaign_id, scope_type=ScopeType.public
    )
    ConversationScopeRepo(session).save(private_scope)
    ConversationScopeRepo(session).save(public_scope)
    session.commit()

    fact = make_knowledge_fact(
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        owner_scope_id=private_scope.scope_id,
    )
    KnowledgeFactRepo(session).save(fact)
    session.commit()

    public_facts = KnowledgeFactRepo(session).list_for_scope(public_scope.scope_id)
    assert len(public_facts) == 0


def test_visibility_grant_expands_fact_access(session):
    camp = make_campaign()
    CampaignRepo(session).save(camp)
    scene = make_scene(campaign_id=camp.campaign_id)
    SceneRepo(session).save(scene)
    private_scope = make_conversation_scope(
        campaign_id=camp.campaign_id, scope_type=ScopeType.private_referee
    )
    public_scope = make_conversation_scope(
        campaign_id=camp.campaign_id, scope_type=ScopeType.public
    )
    ConversationScopeRepo(session).save(private_scope)
    ConversationScopeRepo(session).save(public_scope)

    fact = make_knowledge_fact(
        campaign_id=camp.campaign_id,
        scene_id=scene.scene_id,
        owner_scope_id=private_scope.scope_id,
    )
    KnowledgeFactRepo(session).save(fact)
    session.commit()

    from server.domain.entities import VisibilityGrant

    grant = VisibilityGrant(
        grant_id=str(__import__("uuid").uuid4()),
        fact_id=fact.fact_id,
        campaign_id=camp.campaign_id,
        granted_to_scope_id=public_scope.scope_id,
        granted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    VisibilityGrantRepo(session).save(grant)
    session.commit()

    grants = VisibilityGrantRepo(session).list_for_fact(fact.fact_id)
    assert len(grants) == 1
    assert grants[0].granted_to_scope_id == public_scope.scope_id

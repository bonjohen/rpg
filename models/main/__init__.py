"""Main gameplay model tier (GPT-5.4 mini via OpenAI API).

Handles high-quality narrative and social tasks:
  - scene_narration
  - npc_dialogue
  - combat_summary
  - ruling_proposal
  - social_arbitration
  - puzzle_flavor
  - unusual_action_interpretation

The inference adapter (OpenAIMainAdapter) calls the OpenAI Chat Completions
API. Requires OPENAI_API_KEY in environment variables. All prompt contracts,
context assembly, schema validation, and fallback behavior are fully
functional and tested with mocks.
"""

"""Main gameplay model tier (Gemma 4 26B A4B via Ollama).

Handles high-quality narrative and social tasks:
  - scene_narration
  - npc_dialogue
  - combat_summary
  - ruling_proposal
  - social_arbitration
  - puzzle_flavor
  - unusual_action_interpretation

The inference adapter (OllamaMainAdapter) is built but requires the actual
model to be running in Ollama. All prompt contracts, context assembly, schema
validation, and fallback behavior are fully functional and tested with mocks.
"""

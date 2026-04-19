"""NPC Social Loop — pure domain logic, no I/O.

Submodules:
  social.py   — SocialEngine: resolve social actions (question/persuade/threaten/lie/bargain)
  trust.py    — TrustEngine: trust delta computation and stance transitions
  tells.py    — NpcTellEngine: secret tells and referee-only reaction facts
  dialogue.py — DialogueContextBuilder: assemble structured dialogue context for main model
"""

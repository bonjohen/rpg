"""Exploration Loop — pure domain logic, no I/O.

Implements:
  - Room/scene transition rules (move between connected scenes)
  - Move, inspect, search, interact action resolution
  - Environmental triggers and simple traps
  - Hidden clue discovery and scoped delivery
  - Object-state change handling (doors, chests, etc.)
  - Revisit memory and scene recall
"""

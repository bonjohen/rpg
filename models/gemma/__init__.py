"""Gemma 4 26B A4B inference adapter for the main gameplay model tier.

Connects to a Gemma model served via an OpenAI-compatible API endpoint
(vLLM, llama.cpp server, Ollama with OpenAI compat, etc.) on the local
network.  Requires GEMMA_BASE_URL to be set.
"""

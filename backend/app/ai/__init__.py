"""Deterministic intelligence pipeline: parsing, extraction, correlation.

Pure functions over evidence content live here (no FastAPI, no SQLAlchemy).
Persistence, API, RBAC, and audit belong to ``app.modules.intelligence``.

Milestone 4 implements extraction and shared-value correlation. Rule-based
reasoning, findings, and recommendations arrive in Milestone 5. The LLM
remains a language-generation component only; see docs/ai-architecture.md.
"""

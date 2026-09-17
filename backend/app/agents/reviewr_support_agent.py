"""Reviewer support agent wrapper.

Aliases the implementation in guidance_agent.py for compatibility.
"""

from .guidance_agent import GuidanceAgent, guidance_agent, reviewer_support_agent

__all__ = ["GuidanceAgent", "guidance_agent", "reviewer_support_agent"]

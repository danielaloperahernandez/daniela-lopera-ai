"""Versioned prompt templates.

Prompts are first-class, versioned assets (not strings buried in code). Each lives in a
YAML file with an explicit ``version`` so changes are reviewable and traceable. See
``docs/prompt-engineering.md`` for the why and how.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent


@dataclass(slots=True, frozen=True)
class Prompt:
    """A loaded prompt template.

    ``system`` and ``user`` are Python ``str.format``-style templates. Call
    :meth:`render` with keyword arguments to fill the placeholders.
    """

    name: str
    version: str
    description: str
    system: str
    user: str

    def render(self, **kwargs: object) -> tuple[str, str]:
        """Return ``(system, user)`` with placeholders substituted."""
        return self.system.format(**kwargs), self.user.format(**kwargs)


@lru_cache(maxsize=None)
def load_prompt(name: str) -> Prompt:
    """Load ``<name>.yaml`` from this directory into a :class:`Prompt`."""
    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in _PROMPTS_DIR.glob("*.yaml")))
        raise FileNotFoundError(
            f"Prompt '{name}' not found. Available prompts: {available or '(none)'}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Prompt(
        name=data["name"],
        version=str(data["version"]),
        description=data.get("description", ""),
        system=data["system"].strip(),
        user=data["user"].strip(),
    )


__all__ = ["Prompt", "load_prompt"]

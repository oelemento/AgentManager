"""State management for AgentManager - data model and persistence."""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DATA_DIR, AGENTS_FILE


@dataclass
class Agent:
    """Represents a managed AI agent session."""
    id: str
    name: str
    agent_type: str  # "claude" or "gemini"
    tmux_session: str  # tmux session name (persistent)
    working_dir: str
    status: str  # "active", "idle", "waiting"
    created_at: str
    # Legacy field for backwards compatibility during migration
    iterm_session_id: str = ""
    # Archive status - archived agents are hidden from main view
    archived: bool = False

    @classmethod
    def create(cls, name: str, agent_type: str, tmux_session: str,
               working_dir: Optional[str] = None) -> "Agent":
        """Create a new agent with generated ID and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            agent_type=agent_type,
            tmux_session=tmux_session,
            working_dir=working_dir or str(Path.home()),
            status="idle",
            created_at=datetime.now().isoformat(),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
        # Handle migration from old format (iterm_session_id -> tmux_session)
        if "tmux_session" not in data and "iterm_session_id" in data:
            data["tmux_session"] = data.get("iterm_session_id", "")
        # Ensure tmux_session exists
        if "tmux_session" not in data:
            data["tmux_session"] = ""
        return cls(**data)


class StateManager:
    """Manages the collection of agents and persistence."""

    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self._ensure_data_dir()
        self.load()

    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        """Load agents from disk."""
        if AGENTS_FILE.exists():
            try:
                with open(AGENTS_FILE, "r") as f:
                    data = json.load(f)
                self.agents = {
                    agent_id: Agent.from_dict(agent_data)
                    for agent_id, agent_data in data.items()
                }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading agents: {e}")
                self.agents = {}
        else:
            self.agents = {}

    def save(self):
        """Save agents to disk."""
        data = {
            agent_id: agent.to_dict()
            for agent_id, agent in self.agents.items()
        }
        with open(AGENTS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def add_agent(self, agent: Agent):
        """Add a new agent and persist."""
        self.agents[agent.id] = agent
        self.save()

    def remove_agent(self, agent_id: str):
        """Remove an agent and persist."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.save()

    def update_status(self, agent_id: str, status: str):
        """Update an agent's status."""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
            # Don't save on every status update - too frequent

    def rename_agent(self, agent_id: str, new_name: str):
        """Rename an agent and persist."""
        if agent_id in self.agents:
            self.agents[agent_id].name = new_name
            self.save()

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_all_agents(self, archived: bool = False) -> list[Agent]:
        """Get all agents sorted by creation time, filtered by archived status."""
        return sorted(
            [a for a in self.agents.values() if a.archived == archived],
            key=lambda a: a.created_at
        )

    def archive_agent(self, agent_id: str):
        """Archive an agent (hide from main view but keep tmux session)."""
        if agent_id in self.agents:
            self.agents[agent_id].archived = True
            self.save()

    def unarchive_agent(self, agent_id: str):
        """Unarchive an agent (restore to main view)."""
        if agent_id in self.agents:
            self.agents[agent_id].archived = False
            self.save()

    def count_archived(self) -> int:
        """Count number of archived agents."""
        return sum(1 for a in self.agents.values() if a.archived)

    def count_active(self) -> int:
        """Count number of non-archived agents."""
        return sum(1 for a in self.agents.values() if not a.archived)

    def prune_dead_sessions(self, valid_tmux_sessions: set[str]):
        """Remove agents whose tmux sessions no longer exist."""
        dead_ids = [
            agent_id for agent_id, agent in self.agents.items()
            if agent.tmux_session not in valid_tmux_sessions
        ]
        for agent_id in dead_ids:
            del self.agents[agent_id]
        if dead_ids:
            self.save()

    def get_agents_by_tmux_session(self, tmux_session: str) -> Optional["Agent"]:
        """Find an agent by its tmux session name."""
        for agent in self.agents.values():
            if agent.tmux_session == tmux_session:
                return agent
        return None

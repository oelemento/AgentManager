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
    iterm_session_id: str
    working_dir: str
    status: str  # "active", "idle", "waiting"
    created_at: str

    @classmethod
    def create(cls, name: str, agent_type: str, iterm_session_id: str,
               working_dir: Optional[str] = None) -> "Agent":
        """Create a new agent with generated ID and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            agent_type=agent_type,
            iterm_session_id=iterm_session_id,
            working_dir=working_dir or str(Path.home()),
            status="idle",
            created_at=datetime.now().isoformat(),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
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

    def get_all_agents(self) -> list[Agent]:
        """Get all agents sorted by creation time."""
        return sorted(self.agents.values(), key=lambda a: a.created_at)

    def prune_dead_sessions(self, valid_session_ids: set[str]):
        """Remove agents whose iTerm sessions no longer exist."""
        dead_ids = [
            agent_id for agent_id, agent in self.agents.items()
            if agent.iterm_session_id not in valid_session_ids
        ]
        for agent_id in dead_ids:
            del self.agents[agent_id]
        if dead_ids:
            self.save()

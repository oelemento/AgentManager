"""Configuration constants for AgentManager."""

import os
from pathlib import Path

# Paths
DATA_DIR = Path.home() / ".agentmanager"
AGENTS_FILE = DATA_DIR / "agents.json"

# Default working directories
DEFAULT_WORKING_DIR = "/Users/ole2001/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault"
PROGRAMS_DIR = "/Users/ole2001/PROGRAMS"

# Quick folder options for the directory picker
FOLDER_OPTIONS = [
    ("Obsidian Vault", DEFAULT_WORKING_DIR),
    ("PROGRAMS (new project)", PROGRAMS_DIR),
]

# Status detection
ACTIVE_TIMEOUT_SECONDS = 3  # Time before "active" becomes "idle"
STATUS_CHECK_INTERVAL = 1   # How often to check status (seconds)

# Agent types and their launch commands
AGENT_COMMANDS = {
    "claude": "claude",
    "gemini": "gemini",
}

# Status indicators
STATUS_ICONS = {
    "active": "🟢",
    "idle": "⚪",
    "waiting": "🟡",
}

# Menu bar icon (text works more reliably than emoji)
MENU_BAR_ICON = "AG"

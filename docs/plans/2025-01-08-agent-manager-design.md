# AgentManager Design

A macOS menu bar app for managing multiple Claude and Gemini terminal sessions.

## Problem

When running multiple AI agents in separate terminal tabs:
- Tabs show only "Terminal" with no identification
- Hard to track which agent is doing what
- No way to see status at a glance
- Switching between 10-15 agents is painful

## Solution

**AgentManager** - a menu bar app that:
- Launches named AI agent sessions in iTerm2
- Shows all agents in a dropdown with status indicators
- Allows one-click switching to any agent
- Persists agent list between restarts

## Core Workflow

1. Click menu bar icon
2. See list: `🟢 Claude - AuthRefactor` / `⚪ Gemini - DataPipeline`
3. Click agent → brings that iTerm tab to front
4. Launch new agents via "+ New Claude Session..."

## Data Model

```python
{
  "id": "uuid",
  "name": "AuthRefactor",        # User-provided name
  "type": "claude" | "gemini",   # Which AI
  "iterm_session_id": "...",     # iTerm's session GUID
  "working_dir": "/path/to/project",
  "status": "active" | "idle" | "waiting",
  "created_at": "2025-01-08T..."
}
```

### Status Detection

- `active` (🟢) - Output received in last 3 seconds
- `idle` (⚪) - No output for 3+ seconds
- `waiting` (🟡) - Agent prompted for input

Agents saved to `~/.agentmanager/agents.json`

## Menu Structure

```
┌─────────────────────────────┐
│ 🤖 AgentManager             │
├─────────────────────────────┤
│ 🟢 Claude - AuthRefactor    │
│ ⚪ Claude - DataMigration   │
│ 🟡 Gemini - APIDesign       │
├─────────────────────────────┤
│ + New Claude Session...     │
│ + New Gemini Session...     │
├─────────────────────────────┤
│ ⚙️ Settings                  │
│ Quit                        │
└─────────────────────────────┘
```

### Interactions

- **Click agent row** → Brings iTerm to front, activates that tab
- **Right-click agent** → Submenu: Rename / Close
- **"New Session"** → Prompts for name, optionally folder, then launches

## iTerm2 Integration

Uses iTerm2's Python API to:
- Create new tabs
- Get session IDs for tracking
- Activate specific tabs
- Subscribe to output for status detection

### Launch Sequence

1. Connect to iTerm2 via API
2. Create new tab in current window
3. Capture session ID
4. Send command: `cd /path && claude` (or gemini)
5. Store agent record with session ID
6. Start monitoring output for status

### Requirement

User must enable iTerm2's Python API:
- iTerm2 → Settings → General → Magic → Enable Python API

## File Structure

```
AgentManager/
├── agent_manager.py      # Main app - menu bar, event handling
├── iterm_bridge.py       # iTerm2 API wrapper
├── state.py              # Load/save agents.json, data model
├── config.py             # Constants (timeouts, paths)
├── requirements.txt      # rumps, iterm2
└── README.md             # Setup instructions
```

## Dependencies

- `rumps` - Menu bar framework
- `iterm2` - Official iTerm2 Python API

## Future Enhancements (Not in v1)

- Auto-detect existing claude/gemini tabs
- Keyboard shortcuts for switching
- Cost/token tracking
- Session groups/folders

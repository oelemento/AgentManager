# AgentManager

A macOS floating window app for managing multiple Claude and Gemini terminal sessions in iTerm2.

## Features

- **Floating always-on-top window** - Visible across all spaces
- Launch named Claude/Gemini sessions with one click
- **Reliable tab switching** - Uses iTerm's persistent session UUID (survives Claude renaming terminal titles)
- **50% larger font** - Agent sessions open with larger text for readability
- Option-click to close sessions
- Persists agents between restarts

## Requirements

- macOS
- iTerm2
- Python 3.11+
- `claude` and/or `gemini` CLI tools installed

## Setup

### 1. Create virtual environment and install dependencies

```bash
cd AgentManager
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create the AgentLarge iTerm profile (for larger font)

```bash
source venv/bin/activate
python setup_iterm_profile.py
```

This creates an "AgentLarge" profile with Monaco 18 font (50% larger than default).

**Important:** Run this with iTerm2 closed, then restart iTerm2.

### 3. Run the app

```bash
source venv/bin/activate
python floating_manager.py
```

A floating "Agent Manager" window appears in the top-left corner.

## Usage

### Launch a new agent

1. Click **+ Claude** or **+ Gemini** button
2. Enter a name (e.g., "AuthRefactor")
3. Choose working directory:
   - **Obsidian Vault** - Default notes location
   - **PROGRAMS (new project)** - Creates new folder in ~/PROGRAMS
   - **Custom path...** - Enter any path
4. A new iTerm tab opens with the agent running (with larger font)

### Switch to an agent

Click any agent button to bring its iTerm tab to front.

### Close an agent

**Option-click** on an agent button to close its iTerm tab and remove it from the list.

### Status indicators

- 🟢 Active
- ⚪ Idle
- 🟡 Waiting

## Files

| File | Description |
|------|-------------|
| `floating_manager.py` | Main app - PyObjC floating window |
| `agent_manager.py` | Alternative menu bar version (rumps) |
| `iterm_bridge.py` | iTerm2 communication via AppleScript |
| `state.py` | Agent data model, JSON persistence |
| `config.py` | Constants (paths, commands, icons) |
| `setup_iterm_profile.py` | Creates AgentLarge iTerm profile |

## Data locations

- Agent data: `~/.agentmanager/agents.json`
- iTerm profile: `~/Library/Preferences/com.googlecode.iterm2.plist`

## Technical Notes

### Why AppleScript instead of iTerm2 Python API?

The iTerm2 Python API requires running as an iTerm2 script (inside `~/Library/Application Support/iTerm2/Scripts/`). For a standalone app, AppleScript via `osascript` is more reliable.

### How tab switching works

Claude CLI changes the terminal title (e.g., to "✳ Cultural Tracker (node)"), which breaks name-based tab matching. We use iTerm's `unique ID` property instead - a UUID that's persistent per session and survives title changes.

### Font size

AppleScript can't directly change font size. We create an "AgentLarge" profile in iTerm's preferences with Monaco 18 font, then open new tabs using that profile.

## Troubleshooting

### Agent not switching tabs

- The agent's iTerm tab may have been closed manually
- Option-click to remove stale agents

### Font not larger

1. Quit iTerm2 completely
2. Run `python setup_iterm_profile.py`
3. Restart iTerm2
4. Create a new agent (existing tabs won't change)

### Window not appearing

- Check if another instance is running: `pkill -f floating_manager.py`
- Run again

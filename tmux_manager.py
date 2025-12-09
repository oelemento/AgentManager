"""Tmux session management for AgentManager."""

import subprocess
import hashlib
import time
from typing import Optional
from config import AGENT_COMMANDS


def run_command(cmd: list[str], timeout: int = 5) -> tuple[bool, str]:
    """Run a shell command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, ""
    except Exception as e:
        return False, str(e)


def run_applescript(script: str) -> tuple[bool, str]:
    """Run AppleScript and return (success, output)."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout.strip()


def ensure_iterm_running():
    """Make sure iTerm2 is running."""
    result = subprocess.run(
        ["pgrep", "-x", "iTerm2"],
        capture_output=True
    )
    if result.returncode != 0:
        subprocess.run(["open", "-a", "iTerm"])
        time.sleep(2)


class TmuxManager:
    """Manages tmux sessions for persistent agent sessions."""

    # Prefix for all our tmux sessions
    SESSION_PREFIX = "agent-"

    def create_session(self, agent_type: str, working_dir: str, name: str) -> Optional[str]:
        """Create a new tmux session and launch the agent.

        Returns the tmux session name if successful, None otherwise.
        """
        # Generate unique session name
        session_name = f"{self.SESSION_PREFIX}{name.lower().replace(' ', '-')}-{int(time.time())}"

        command = AGENT_COMMANDS.get(agent_type, agent_type)

        # Create tmux session in detached mode
        success, _ = run_command([
            "tmux", "new-session",
            "-d",  # detached
            "-s", session_name,
            "-c", working_dir,  # start in working directory
        ])

        if not success:
            return None

        # Send the agent command to the session
        run_command([
            "tmux", "send-keys",
            "-t", session_name,
            command,
            "Enter"
        ])

        # Open iTerm and attach to the session
        self._open_in_iterm(session_name)

        return session_name

    def _open_in_iterm(self, session_name: str):
        """Open an iTerm tab attached to the tmux session."""
        ensure_iterm_running()

        # Extract a friendly name from session name (e.g., "agent-project-manager-123" -> "project-manager")
        friendly_name = session_name.replace("agent-", "").rsplit("-", 1)[0]

        # AppleScript to create new tab and attach to tmux
        # We set the tab title using escape sequence before attaching to tmux
        script = f'''
        tell application "iTerm"
            activate
            if (count of windows) = 0 then
                create window with default profile
            end if
            tell current window
                try
                    create tab with profile "AgentLarge"
                on error
                    create tab with default profile
                end try
                tell current session
                    -- Set tab title using escape sequence (works even with tmux)
                    write text "printf '\\\\033]0;{friendly_name}\\\\007'"
                    write text "tmux attach-session -t {session_name}"
                end tell
            end tell
        end tell
        '''
        run_applescript(script)

    def attach_session(self, session_name: str) -> bool:
        """Attach to an existing tmux session in iTerm.

        Opens a new iTerm tab connected to the session.
        """
        if not self.session_exists(session_name):
            return False

        self._open_in_iterm(session_name)
        return True

    def session_exists(self, session_name: str) -> bool:
        """Check if a tmux session exists."""
        success, output = run_command(["tmux", "has-session", "-t", session_name])
        return success

    def kill_session(self, session_name: str) -> bool:
        """Kill a tmux session."""
        success, _ = run_command(["tmux", "kill-session", "-t", session_name])
        return success

    def list_sessions(self) -> list[str]:
        """List all agent tmux sessions."""
        success, output = run_command([
            "tmux", "list-sessions", "-F", "#{session_name}"
        ])
        if not success:
            return []

        sessions = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith(self.SESSION_PREFIX):
                sessions.append(line)
        return sessions

    def get_session_text(self, session_name: str, lines: int = 50) -> Optional[str]:
        """Capture recent text from a tmux session pane."""
        if not self.session_exists(session_name):
            return None

        success, output = run_command([
            "tmux", "capture-pane",
            "-t", session_name,
            "-p",  # print to stdout
            "-S", f"-{lines}",  # start from N lines back
        ])

        if success:
            return output
        return None

    def get_session_text_hash(self, session_name: str) -> Optional[str]:
        """Get a hash of recent session text for activity detection."""
        text = self.get_session_text(session_name, lines=30)
        if text is None:
            return None
        return hashlib.md5(text.encode()).hexdigest()

    def find_iterm_window_for_session(self, session_name: str) -> bool:
        """Try to find and activate an iTerm window attached to this tmux session."""
        ensure_iterm_running()

        # tmux truncates session names heavily in the status bar
        # Use just the first 3 chars of the name part which is unique enough
        # e.g., "agent-program-manager-123" -> "agent-pro"
        # e.g., "agent-personal-assistant-123" -> "agent-per"
        name_part = session_name.replace("agent-", "")  # "program-manager-123"
        short_name = name_part.split("-")[0][:3]  # "pro" or "per"
        search_term = f"agent-{short_name}"  # "agent-pro" or "agent-per"

        script = f'''
        tell application "iTerm"
            activate
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        try
                            set sessionText to text of s
                            if sessionText contains "{search_term}" then
                                select t
                                return true
                            end if
                        end try
                    end repeat
                end repeat
            end repeat
            return false
        end tell
        '''
        success, output = run_applescript(script)
        return success and output == "true"

    def activate_session(self, session_name: str) -> bool:
        """Bring a session to front, opening a new iTerm tab if needed."""
        if not self.session_exists(session_name):
            return False

        # Check how many clients are attached to this tmux session
        success, output = run_command([
            "tmux", "list-clients", "-t", session_name
        ])

        # If there are attached clients, just activate iTerm (don't open new tab)
        if success and output.strip():
            # There's already a client attached, just bring iTerm to front
            # and try to switch to the right tab
            ensure_iterm_running()
            if self.find_iterm_window_for_session(session_name):
                return True
            # If we can't find it, still just activate iTerm - user can find tab
            run_applescript('tell application "iTerm" to activate')
            return True

        # No attached client, open a new tab and attach
        self._open_in_iterm(session_name)
        return True

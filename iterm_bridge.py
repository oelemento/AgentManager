"""iTerm2 integration for AgentManager using AppleScript."""

import subprocess
import time
import uuid
from typing import Optional
from config import AGENT_COMMANDS


def ensure_iterm_running():
    """Make sure iTerm2 is running."""
    result = subprocess.run(
        ["pgrep", "-x", "iTerm2"],
        capture_output=True
    )
    if result.returncode != 0:
        subprocess.run(["open", "-a", "iTerm"])
        time.sleep(2)


def run_applescript(script: str) -> tuple[bool, str]:
    """Run AppleScript and return (success, output)."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout.strip()


class ITermManager:
    """Manages communication with iTerm2 using AppleScript."""

    def connect(self):
        """Test connection to iTerm2."""
        ensure_iterm_running()

    def create_session(self, agent_type: str, working_dir: str) -> Optional[str]:
        """Create a new iTerm tab and launch the agent.

        Returns the iTerm session's unique ID (UUID) which is persistent
        and survives title changes by Claude.
        """
        ensure_iterm_running()

        command = AGENT_COMMANDS.get(agent_type, agent_type)

        # AppleScript to create new tab with large font profile and run command
        # Uses "AgentLarge" profile if it exists, otherwise creates tab and uses escape sequence
        script = f'''
        tell application "iTerm"
            activate

            -- Create a new window if none exists, otherwise use current
            if (count of windows) = 0 then
                create window with default profile
            end if

            tell current window
                -- Try to create tab with AgentLarge profile (has 50% larger font)
                -- If profile doesn't exist, fall back to default
                try
                    create tab with profile "AgentLarge"
                on error
                    create tab with default profile
                end try

                tell current session
                    -- Get the unique ID before running anything
                    set sessId to unique ID
                    -- Use escape sequence to try switching to larger font profile
                    write text "printf '\\\\033]50;SetProfile=AgentLarge\\\\a' 2>/dev/null"
                    write text "cd \\"{working_dir}\\" && {command}"
                    return sessId
                end tell
            end tell
        end tell
        '''

        success, output = run_applescript(script)
        if success and output:
            # Return the iTerm unique session ID
            return output.strip()
        return None

    def activate_session(self, session_id: str) -> bool:
        """Bring the specified session to front by finding its tab.

        Uses iTerm's unique ID which is persistent and survives title changes.
        """
        ensure_iterm_running()

        # Search for the session by its unique ID (most reliable method)
        script = f'''
        tell application "iTerm"
            activate
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        try
                            if unique ID of s is "{session_id}" then
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

    def close_session(self, session_id: str) -> bool:
        """Close the specified session by finding and closing its tab.

        Uses iTerm's unique ID which is persistent and survives title changes.
        """
        ensure_iterm_running()

        # Search for the session by its unique ID
        script = f'''
        tell application "iTerm"
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        try
                            if unique ID of s is "{session_id}" then
                                tell t to close
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

    def get_all_session_ids(self) -> set[str]:
        """Get all current session IDs (markers) from iTerm.

        Note: This is inherently unreliable since terminal text can scroll.
        We return a very large set to avoid aggressive pruning.
        Only prune when we're certain the session is gone.
        """
        ensure_iterm_running()

        # Get text from all sessions and extract our markers
        # Also check the session's variables/environment
        script = '''
        tell application "iTerm"
            set allText to ""
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        try
                            set allText to allText & text of s & "|||"
                        end try
                    end repeat
                end repeat
            end repeat
            return allText
        end tell
        '''

        success, output = run_applescript(script)
        if not success:
            # If we can't connect, return empty but don't prune
            return set()

        # Extract AGENT_* markers from the output
        import re
        markers = set(re.findall(r'AGENT_[a-f0-9]{8}', output))
        return markers

    def has_any_sessions(self) -> bool:
        """Check if iTerm has any open sessions at all."""
        script = '''
        tell application "iTerm"
            set sessionCount to 0
            repeat with w in windows
                repeat with t in tabs of w
                    set sessionCount to sessionCount + (count of sessions of t)
                end repeat
            end repeat
            return sessionCount
        end tell
        '''
        success, output = run_applescript(script)
        if success:
            try:
                return int(output) > 0
            except:
                pass
        return True  # Assume sessions exist if we can't check

    def get_session_text_hash(self, session_id: str) -> Optional[str]:
        """Get a hash of the last 500 chars of session text for activity detection.

        Returns None if session not found, otherwise returns hash of recent text.
        """
        script = f'''
        tell application "iTerm"
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        try
                            if unique ID of s is "{session_id}" then
                                set sessionText to text of s
                                -- Get last 500 characters to detect changes
                                if length of sessionText > 500 then
                                    set sessionText to text -500 thru -1 of sessionText
                                end if
                                return sessionText
                            end if
                        end try
                    end repeat
                end repeat
            end repeat
            return "SESSION_NOT_FOUND"
        end tell
        '''
        success, output = run_applescript(script)
        if not success or output == "SESSION_NOT_FOUND":
            return None
        # Return hash of the text
        import hashlib
        return hashlib.md5(output.encode()).hexdigest()

    def session_exists(self, session_id: str) -> bool:
        """Check if a session with this ID still exists."""
        script = f'''
        tell application "iTerm"
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        try
                            if unique ID of s is "{session_id}" then
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

#!/usr/bin/env python3
"""AgentManager - Menu bar app for managing AI agent sessions."""

import rumps
import subprocess
import threading
import time
from pathlib import Path

from config import STATUS_ICONS, MENU_BAR_ICON, STATUS_CHECK_INTERVAL, DEFAULT_WORKING_DIR, PROGRAMS_DIR, FOLDER_OPTIONS
from state import StateManager, Agent
from iterm_bridge import ITermManager


def show_input_dialog(title: str, message: str, default_text: str = "") -> str | None:
    """Show an AppleScript input dialog that works reliably."""
    script = f'''
    tell application "System Events"
        activate
        set userInput to display dialog "{message}" default answer "{default_text}" with title "{title}" buttons {{"Cancel", "OK"}} default button "OK"
        return text returned of userInput
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def show_folder_choice_dialog() -> str | None:
    """Show a dialog to choose between preset folders or enter custom path."""
    # Use choose from list since display dialog only allows 3 buttons max
    script = '''
    tell application "System Events"
        activate
        set theChoice to choose from list {"Obsidian Vault", "PROGRAMS (new project)", "Custom path..."} with title "Working Directory" with prompt "Choose working directory:" default items {"Obsidian Vault"}
        if theChoice is false then
            return "CANCELLED"
        else
            return item 1 of theChoice
        end if
    end tell
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return None

        choice = result.stdout.strip()

        if choice == "CANCELLED":
            return None
        elif choice == "Obsidian Vault":
            return DEFAULT_WORKING_DIR
        elif choice == "PROGRAMS (new project)":
            # Ask for new project folder name
            folder_name = show_input_dialog(
                title="New Project",
                message="Enter new project folder name:",
                default_text=""
            )
            if folder_name:
                return f"{PROGRAMS_DIR}/{folder_name}"
            return None
        elif choice == "Custom path...":
            return show_input_dialog(
                title="Custom Directory",
                message="Enter full path:",
                default_text=str(Path.home())
            )
        return None
    except Exception:
        return None


class AgentManagerApp(rumps.App):
    """Main menu bar application."""

    def __init__(self):
        super().__init__(name="AgentManager", title=MENU_BAR_ICON, quit_button=None)
        self.state = StateManager()
        self.iterm = ITermManager()
        # Don't connect at startup - connect lazily when needed
        self._build_menu()

    def _build_menu(self):
        """Rebuild the menu from current state."""
        self.menu.clear()

        # Add agent items
        agents = self.state.get_all_agents()
        if agents:
            for agent in agents:
                icon = STATUS_ICONS.get(agent.status, "⚪")
                type_label = agent.agent_type.capitalize()
                title = f"{icon} {type_label} - {agent.name}"
                item = rumps.MenuItem(title, callback=self._make_activate_callback(agent.id))
                self.menu.add(item)
            self.menu.add(rumps.separator)

        # Add "New Session" options - use rumps.clicked decorator style
        self.menu.add(rumps.MenuItem("+ New Claude Session..."))
        self.menu.add(rumps.MenuItem("+ New Gemini Session..."))
        self.menu.add(rumps.separator)

        # Settings and Quit
        self.menu.add(rumps.MenuItem("Refresh"))
        self.menu.add(rumps.MenuItem("Quit"))

    @rumps.clicked("+ New Claude Session...")
    def on_new_claude(self, _):
        """Launch a new Claude session."""
        print("[DEBUG] on_new_claude clicked!")
        self._new_session("claude")

    @rumps.clicked("+ New Gemini Session...")
    def on_new_gemini(self, _):
        """Launch a new Gemini session."""
        print("[DEBUG] on_new_gemini clicked!")
        self._new_session("gemini")

    @rumps.clicked("Refresh")
    def on_refresh(self, _):
        """Refresh the menu."""
        print("[DEBUG] on_refresh clicked!")
        self._refresh(None)

    @rumps.clicked("Quit")
    def on_quit(self, _):
        """Quit the app."""
        print("[DEBUG] on_quit clicked!")
        rumps.quit_application()

    def _make_activate_callback(self, agent_id: str):
        """Create a callback for activating a specific agent."""
        def callback(_):
            self._activate_agent(agent_id)
        return callback

    def _activate_agent(self, agent_id: str):
        """Bring the agent's iTerm session to front."""
        agent = self.state.get_agent(agent_id)
        if agent:
            # Try to find and activate the session, but don't remove if not found
            # The marker may have scrolled off screen - that's OK
            self.iterm.activate_session(agent.iterm_session_id)


    def _new_session(self, agent_type: str):
        """Create a new agent session."""
        print(f"[DEBUG] _new_session called with type: {agent_type}")

        # Prompt for name using native dialog
        name = show_input_dialog(
            title="New Session",
            message=f"Name this {agent_type.capitalize()} session:",
            default_text=""
        )
        print(f"[DEBUG] Got name: {name}")

        if not name or not name.strip():
            print("[DEBUG] Name empty, returning")
            return

        name = name.strip()

        # Prompt for working directory with preset options
        working_dir = show_folder_choice_dialog()
        print(f"[DEBUG] Got working_dir: {working_dir}")

        if working_dir is None:
            print("[DEBUG] working_dir is None, returning")
            return

        # Create the session
        print(f"[DEBUG] Creating session...")
        try:
            session_id = self.iterm.create_session(agent_type, working_dir)
            print(f"[DEBUG] Got session_id: {session_id}")
            if session_id:
                agent = Agent.create(
                    name=name,
                    agent_type=agent_type,
                    iterm_session_id=session_id,
                    working_dir=working_dir
                )
                self.state.add_agent(agent)
                self._build_menu()
                print(f"[DEBUG] Agent created successfully")
            else:
                print("[DEBUG] session_id is None")
                rumps.alert(
                    title="Failed",
                    message="Could not create iTerm session."
                )
        except Exception as e:
            print(f"[DEBUG] Exception: {e}")
            import traceback
            traceback.print_exc()
            rumps.alert(
                title="Error",
                message=f"Failed to create session: {e}"
            )

    def _refresh(self, _):
        """Refresh the menu - no auto-pruning as marker detection is unreliable."""
        self._build_menu()

    def _quit(self, _):
        """Quit the application."""
        rumps.quit_application()


def main():
    AgentManagerApp().run()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AgentManager - Floating window for managing AI agent sessions."""

import subprocess
import threading
import uuid
from pathlib import Path

import objc
import AppKit
from Foundation import NSObject
from PyObjCTools import AppHelper

from config import STATUS_ICONS, DEFAULT_WORKING_DIR, PROGRAMS_DIR
from state import StateManager, Agent
from tmux_manager import TmuxManager


def show_input_dialog(title: str, message: str, default_text: str = "") -> str | None:
    """Show an AppleScript input dialog."""
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
    """Show a dialog to choose working directory."""
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
            folder_name = show_input_dialog(
                title="New Project",
                message="Enter new project folder name:",
                default_text=""
            )
            if folder_name:
                new_path = Path(PROGRAMS_DIR) / folder_name
                new_path.mkdir(parents=True, exist_ok=True)
                return str(new_path)
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


class AgentManagerDelegate(NSObject):
    """Main app delegate managing the floating window."""

    def init(self):
        self = objc.super(AgentManagerDelegate, self).init()
        if self is None:
            return None
        self.state = StateManager()
        self.tmux = TmuxManager()
        self.window = None
        self.content_view = None
        self.agent_buttons = []
        self.agents_start_y = 50
        # Activity detection: track text hashes per session
        self.session_hashes: dict[str, str] = {}  # tmux_session -> last hash
        self.session_stable_count: dict[str, int] = {}  # tmux_session -> consecutive stable polls
        # Archive view toggle
        self.showing_archived = False
        self.archive_toggle_btn = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        """Create the floating window when app launches."""
        self.create_window()

        # Don't refresh immediately - let the window show first
        # Start refresh timer (first fire after 0.5s, then every 2s)
        AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "refreshTimer:", None, True
        )

    def create_window(self):
        """Create the floating panel window."""
        # Window size and position (top-left corner)
        screen = AppKit.NSScreen.mainScreen().frame()
        width = 280
        height = 300
        x = 20
        y = screen.size.height - height - 50

        frame = AppKit.NSMakeRect(x, y, width, height)

        # Create window with panel style
        style = (
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable |
            AppKit.NSWindowStyleMaskMiniaturizable |
            AppKit.NSWindowStyleMaskResizable
        )

        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            style,
            AppKit.NSBackingStoreBuffered,
            False
        )

        self.window.setTitle_("Agent Manager")
        self.window.setLevel_(AppKit.NSFloatingWindowLevel)  # Always on top
        self.window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
            AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        # Main content view
        self.content_view = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        self.window.setContentView_(self.content_view)

        # Add buttons at bottom
        self.create_bottom_buttons()

        self.window.makeKeyAndOrderFront_(None)

    def create_bottom_buttons(self):
        """Create the + Claude, + Gemini, + Codex, Archive toggle, and help text at bottom."""
        button_height = 30
        button_width = 80
        margin = 10
        y = margin

        # Help text at bottom
        help_label = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin, y, 260, 36)
        )
        help_label.setStringValue_("Click=switch  ⌘-click=archive  ⌥-click=kill\n🔄=recoverable (hover for details)")
        help_label.setBezeled_(False)
        help_label.setDrawsBackground_(False)
        help_label.setEditable_(False)
        help_label.setSelectable_(False)
        help_label.setFont_(AppKit.NSFont.systemFontOfSize_(10))
        help_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self.content_view.addSubview_(help_label)
        y += 36

        # + Claude button
        claude_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin, y, button_width, button_height)
        )
        claude_btn.setTitle_("+ Claude")
        claude_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        claude_btn.setTarget_(self)
        claude_btn.setAction_("newClaudeSession:")
        self.content_view.addSubview_(claude_btn)

        # + Gemini button
        gemini_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin + button_width + 5, y, button_width, button_height)
        )
        gemini_btn.setTitle_("+ Gemini")
        gemini_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        gemini_btn.setTarget_(self)
        gemini_btn.setAction_("newGeminiSession:")
        self.content_view.addSubview_(gemini_btn)

        # + Codex button
        codex_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin + (button_width + 5) * 2, y, button_width, button_height)
        )
        codex_btn.setTitle_("+ Codex")
        codex_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        codex_btn.setTarget_(self)
        codex_btn.setAction_("newCodexSession:")
        self.content_view.addSubview_(codex_btn)
        y += button_height + 5

        # Archive toggle button (second row)
        self.archive_toggle_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin, y, 260, button_height)
        )
        self.archive_toggle_btn.setTitle_("Show Archived (0)")
        self.archive_toggle_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self.archive_toggle_btn.setTarget_(self)
        self.archive_toggle_btn.setAction_("toggleArchiveView:")
        self.content_view.addSubview_(self.archive_toggle_btn)
        y += button_height + margin

        self.agents_start_y = y

    def refresh_agents(self):
        """Refresh the agent list display - runs in background thread."""
        def do_refresh():
            # Prune agents whose tmux sessions no longer exist
            valid_sessions = set(self.tmux.list_sessions())
            self.state.prune_dead_sessions(valid_sessions)

            # Get agents based on current view mode
            agents = self.state.get_all_agents(archived=self.showing_archived)

            # Get counts for toggle button
            archived_count = self.state.count_archived()
            active_count = self.state.count_active()

            # Build session info dict for UI
            session_infos = {}

            # Check activity status for each agent
            for agent in agents:
                tmux_session = agent.tmux_session

                # Load session info for this agent
                session_info = self.state.get_session_info(tmux_session)
                if session_info:
                    session_infos[agent.id] = session_info

                # Check if tmux session exists
                if tmux_session not in valid_sessions:
                    # Session is dead - check if recoverable
                    if session_info and session_info.conversation_id:
                        agent.status = "recoverable"
                    else:
                        agent.status = "idle"
                    continue

                current_hash = self.tmux.get_session_text_hash(tmux_session)

                if current_hash is None:
                    agent.status = "idle"
                    continue

                # Get previous hash
                prev_hash = self.session_hashes.get(tmux_session)

                if prev_hash is None or current_hash != prev_hash:
                    # Text changed - agent is active (outputting)
                    agent.status = "active"
                    self.session_stable_count[tmux_session] = 0
                else:
                    # Text is the same - increment stable count
                    count = self.session_stable_count.get(tmux_session, 0) + 1
                    self.session_stable_count[tmux_session] = count

                    # After 3 consecutive stable polls (~6 seconds), mark as waiting
                    if count >= 3:
                        agent.status = "waiting"
                    else:
                        agent.status = "active"

                # Update hash
                self.session_hashes[tmux_session] = current_hash

            # Update UI on main thread - pass agents and counts as dict
            data = {
                "agents": agents,
                "archived_count": archived_count,
                "active_count": active_count,
                "session_infos": session_infos
            }
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "updateAgentList:", data, False
            )

        threading.Thread(target=do_refresh, daemon=True).start()

    def updateAgentList_(self, data):
        """Update the agent list UI (must be called on main thread)."""
        # Remove old agent buttons
        for btn in self.agent_buttons:
            btn.removeFromSuperview()
        self.agent_buttons = []

        # Extract data from dict
        if data is None:
            agents = []
            archived_count = 0
            active_count = 0
            session_infos = {}
        else:
            agents = data.get("agents", [])
            archived_count = data.get("archived_count", 0)
            active_count = data.get("active_count", 0)
            session_infos = data.get("session_infos", {})

        # Update toggle button text
        if self.archive_toggle_btn:
            if self.showing_archived:
                self.archive_toggle_btn.setTitle_(f"Show Active ({active_count})")
            else:
                self.archive_toggle_btn.setTitle_(f"Show Archived ({archived_count})")

        # Create button for each agent
        row_height = 35
        y = self.agents_start_y

        for i, agent in enumerate(agents):
            icon = STATUS_ICONS.get(agent.status, "?")
            type_label = agent.agent_type[0].upper()  # C or G
            title = f"{icon} [{type_label}] {agent.name}"

            btn = AppKit.NSButton.alloc().initWithFrame_(
                AppKit.NSMakeRect(10, y, 260, row_height - 5)
            )
            btn.setTitle_(title)
            btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
            btn.setAlignment_(AppKit.NSTextAlignmentLeft)
            btn.setTarget_(self)
            btn.setAction_("agentClicked:")
            btn.setTag_(i)  # Use index as tag

            # Add tooltip with session info if available
            session_info = session_infos.get(agent.id)
            if session_info:
                tooltip_parts = []
                if session_info.last_file:
                    # Show just filename, not full path
                    from pathlib import Path
                    filename = Path(session_info.last_file).name
                    tooltip_parts.append(f"Last: {filename}")
                if agent.status == "recoverable":
                    tooltip_parts.append("Click to restore session")
                if tooltip_parts:
                    btn.setToolTip_(" | ".join(tooltip_parts))

            self.content_view.addSubview_(btn)
            self.agent_buttons.append(btn)
            y += row_height

        # Resize window to fit content
        min_height = self.agents_start_y + 50
        new_height = max(min_height, y + 20)

        frame = self.window.frame()
        diff = new_height - frame.size.height
        frame.size.height = new_height
        frame.origin.y -= diff
        self.window.setFrame_display_(frame, True)

    @objc.python_method
    def get_agent_by_index(self, index):
        """Get agent by button index (respects current view mode)."""
        agents = self.state.get_all_agents(archived=self.showing_archived)
        if 0 <= index < len(agents):
            return agents[index]
        return None

    def refreshTimer_(self, timer):
        """Timer callback to refresh agent list."""
        self.refresh_agents()

    def agentClicked_(self, sender):
        """Handle agent button click.

        Click = switch to agent (or unarchive if viewing archived)
        Option-click = kill and remove agent
        Cmd-click = archive agent (only in main view)
        """
        index = sender.tag()
        agent = self.get_agent_by_index(index)
        if not agent:
            return

        event = AppKit.NSApp.currentEvent()
        modifiers = event.modifierFlags() if event else 0

        if modifiers & AppKit.NSEventModifierFlagOption:
            # Option-click: kill the tmux session and remove the agent
            self.tmux.kill_session(agent.tmux_session)
            self.state.remove_agent(agent.id)
            self.refresh_agents()
        elif modifiers & AppKit.NSEventModifierFlagCommand and not self.showing_archived:
            # Cmd-click in main view: archive the agent and close iTerm tab
            self.tmux.detach_and_close_tab(agent.tmux_session)
            self.state.archive_agent(agent.id)
            self.refresh_agents()
        elif self.showing_archived:
            # Click in archived view: unarchive, reopen iTerm tab, and switch back to main view
            self.state.unarchive_agent(agent.id)
            self.tmux.attach_session(agent.tmux_session)  # Reopen iTerm tab
            self.showing_archived = False
            self.refresh_agents()
        else:
            # Regular click in main view: activate the agent
            self.activate_agent(agent.id)

    def toggleArchiveView_(self, sender):
        """Toggle between active and archived agents view."""
        self.showing_archived = not self.showing_archived
        self.refresh_agents()

    @objc.python_method
    def activate_agent(self, agent_id: str):
        """Bring the agent's tmux session to front, recovering if needed."""
        agent = self.state.get_agent(agent_id)
        if not agent:
            return

        # Check if tmux session still exists
        if self.tmux.session_exists(agent.tmux_session):
            # Session alive - just activate it
            self.tmux.activate_session(agent.tmux_session)
        else:
            # Session is dead - try to recover
            # For Claude: uses --session-id --resume (primary) or --continue (fallback)
            session_info = self.state.get_session_info(agent.tmux_session)
            conversation_id = session_info.conversation_id if session_info else ""

            print(f"[DEBUG] Recovering session with agent_id: {agent.id}, conversation_id: {conversation_id}")
            self.tmux.recover_session(
                agent.tmux_session,
                agent.agent_type,
                agent.working_dir,
                conversation_id,
                agent_id=agent.id  # Pass agent.id for --session-id
            )

    def newClaudeSession_(self, sender):
        """Launch a new Claude session."""
        print("[DEBUG] newClaudeSession_ clicked!")
        import sys
        sys.stdout.flush()
        self._new_session("claude")

    def newGeminiSession_(self, sender):
        """Launch a new Gemini session."""
        print("[DEBUG] newGeminiSession_ clicked!")
        import sys
        sys.stdout.flush()
        self._new_session("gemini")

    def newCodexSession_(self, sender):
        """Launch a new Codex session."""
        print("[DEBUG] newCodexSession_ clicked!")
        import sys
        sys.stdout.flush()
        self._new_session("codex")

    @objc.python_method
    def _new_session(self, agent_type: str):
        """Create a new agent session."""
        # Run in background thread to not block UI
        def create():
            print(f"[DEBUG] Starting new {agent_type} session...")
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
            working_dir = show_folder_choice_dialog()
            print(f"[DEBUG] Got working_dir: {working_dir}")

            if working_dir is None:
                print("[DEBUG] working_dir is None, returning")
                return

            try:
                # Generate agent ID upfront so we can use it for --session-id
                agent_id = str(uuid.uuid4())
                print(f"[DEBUG] Creating tmux session with agent_id: {agent_id}")
                tmux_session = self.tmux.create_session(
                    agent_type, working_dir, name, session_id=agent_id
                )
                print(f"[DEBUG] Got tmux_session: {tmux_session}")
                if tmux_session:
                    agent = Agent(
                        id=agent_id,
                        name=name,
                        agent_type=agent_type,
                        tmux_session=tmux_session,
                        working_dir=working_dir,
                        status="idle",
                        created_at=__import__("datetime").datetime.now().isoformat()
                    )
                    self.state.add_agent(agent)
                    print(f"[DEBUG] Agent created and saved")
                    # Refresh on main thread
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "refreshAgentsFromThread:", None, False
                    )
                else:
                    print("[DEBUG] tmux_session is None!")
            except Exception as e:
                print(f"[DEBUG] Error creating session: {e}")
                import traceback
                traceback.print_exc()

        threading.Thread(target=create, daemon=True).start()

    def refreshAgentsFromThread_(self, _):
        """Called from background thread to refresh UI."""
        self.refresh_agents()

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        return True


def main():
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    delegate = AgentManagerDelegate.alloc().init()
    app.setDelegate_(delegate)

    app.activateIgnoringOtherApps_(True)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AgentManager - Floating window for managing AI agent sessions."""

import subprocess
import threading
from pathlib import Path

import objc
import AppKit
from Foundation import NSObject
from PyObjCTools import AppHelper

from config import STATUS_ICONS, DEFAULT_WORKING_DIR, PROGRAMS_DIR
from state import StateManager, Agent
from iterm_bridge import ITermManager


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


class AgentManagerDelegate(NSObject):
    """Main app delegate managing the floating window."""

    def init(self):
        self = objc.super(AgentManagerDelegate, self).init()
        if self is None:
            return None
        self.state = StateManager()
        self.iterm = ITermManager()
        self.window = None
        self.content_view = None
        self.agent_buttons = []
        self.agents_start_y = 50
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
        """Create the + Claude and + Gemini buttons at bottom."""
        button_height = 30
        button_width = 120
        margin = 10

        # + Claude button
        claude_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin, margin, button_width, button_height)
        )
        claude_btn.setTitle_("+ Claude")
        claude_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        claude_btn.setTarget_(self)
        claude_btn.setAction_("newClaudeSession:")
        self.content_view.addSubview_(claude_btn)

        # + Gemini button
        gemini_btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(margin + button_width + margin, margin, button_width, button_height)
        )
        gemini_btn.setTitle_("+ Gemini")
        gemini_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        gemini_btn.setTarget_(self)
        gemini_btn.setAction_("newGeminiSession:")
        self.content_view.addSubview_(gemini_btn)

        self.agents_start_y = margin + button_height + margin

    def refresh_agents(self):
        """Refresh the agent list display - runs in background thread."""
        def do_refresh():
            # Get current agents - don't auto-prune as marker detection is unreliable
            agents = self.state.get_all_agents()

            # Update UI on main thread
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "updateAgentList:", agents, False
            )

        threading.Thread(target=do_refresh, daemon=True).start()

    def updateAgentList_(self, agents):
        """Update the agent list UI (must be called on main thread)."""
        # Remove old agent buttons
        for btn in self.agent_buttons:
            btn.removeFromSuperview()
        self.agent_buttons = []

        if agents is None:
            agents = []

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
        """Get agent by button index."""
        agents = self.state.get_all_agents()
        if 0 <= index < len(agents):
            return agents[index]
        return None

    def refreshTimer_(self, timer):
        """Timer callback to refresh agent list."""
        self.refresh_agents()

    def agentClicked_(self, sender):
        """Handle agent button click. Option-click to remove."""
        index = sender.tag()
        agent = self.get_agent_by_index(index)
        if not agent:
            return

        # Check if Option key is held
        event = AppKit.NSApp.currentEvent()
        if event and (event.modifierFlags() & AppKit.NSEventModifierFlagOption):
            # Option-click: close the iTerm tab and remove the agent
            self.iterm.close_session(agent.iterm_session_id)
            self.state.remove_agent(agent.id)
            self.refresh_agents()
        else:
            # Regular click: activate the agent
            self.activate_agent(agent.id)

    @objc.python_method
    def activate_agent(self, agent_id: str):
        """Bring the agent's iTerm session to front."""
        agent = self.state.get_agent(agent_id)
        if agent:
            # Try to find and activate the session, but don't remove if not found
            # The marker may have scrolled off screen - that's OK
            self.iterm.activate_session(agent.iterm_session_id)

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
                print(f"[DEBUG] Creating iTerm session...")
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
                    print(f"[DEBUG] Agent created and saved")
                    # Refresh on main thread
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        "refreshAgentsFromThread:", None, False
                    )
                else:
                    print("[DEBUG] session_id is None!")
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

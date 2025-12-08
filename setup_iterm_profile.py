#!/usr/bin/env python3
"""Create the AgentLarge profile in iTerm2 with 50% larger font."""

import subprocess
import plistlib
from pathlib import Path
import uuid

def get_iterm_prefs_path():
    """Get the path to iTerm2 preferences."""
    return Path.home() / "Library/Preferences/com.googlecode.iterm2.plist"

def create_agent_large_profile():
    """Create or update the AgentLarge profile in iTerm2."""
    prefs_path = get_iterm_prefs_path()

    if not prefs_path.exists():
        print("iTerm2 preferences not found. Please run iTerm2 at least once.")
        return False

    # Read current preferences
    try:
        with open(prefs_path, 'rb') as f:
            prefs = plistlib.load(f)
    except Exception as e:
        print(f"Error reading iTerm2 preferences: {e}")
        return False

    bookmarks = prefs.get("New Bookmarks", [])

    # Check if AgentLarge already exists
    for bookmark in bookmarks:
        if bookmark.get("Name") == "AgentLarge":
            print("AgentLarge profile already exists.")
            # Update font size to ensure it's 50% larger
            bookmark["Normal Font"] = "Monaco 18"
            bookmark["Non Ascii Font"] = "Monaco 18"

            # Write back
            try:
                with open(prefs_path, 'wb') as f:
                    plistlib.dump(prefs, f)
                print("Updated AgentLarge font to Monaco 18.")
                return True
            except Exception as e:
                print(f"Error writing preferences: {e}")
                return False

    # Copy the default profile and modify it
    if not bookmarks:
        print("No existing profiles found.")
        return False

    # Clone the first profile (usually Default)
    default_profile = bookmarks[0].copy()

    # Modify for AgentLarge
    default_profile["Name"] = "AgentLarge"
    default_profile["Guid"] = str(uuid.uuid4()).upper()
    default_profile["Normal Font"] = "Monaco 18"  # 50% larger than 12
    default_profile["Non Ascii Font"] = "Monaco 18"

    # Add to bookmarks
    bookmarks.append(default_profile)
    prefs["New Bookmarks"] = bookmarks

    # Write back
    try:
        with open(prefs_path, 'wb') as f:
            plistlib.dump(prefs, f)
        print("Created AgentLarge profile with Monaco 18 font.")
        print("Please restart iTerm2 for the changes to take effect.")
        return True
    except Exception as e:
        print(f"Error writing preferences: {e}")
        return False

if __name__ == "__main__":
    create_agent_large_profile()

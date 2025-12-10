#!/usr/bin/env python3
"""Minimal test menu bar app."""

import rumps

class TestApp(rumps.App):
    def __init__(self):
        super().__init__(name="Test", title="TEST")
        self.menu = [
            rumps.MenuItem("Click Me", callback=self.on_click),
            rumps.MenuItem("Quit", callback=rumps.quit_application)
        ]

    def on_click(self, _):
        print("CLICKED!")
        rumps.alert("It works!", "The click was registered.")


if __name__ == "__main__":
    TestApp().run()

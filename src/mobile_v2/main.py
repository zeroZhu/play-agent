from __future__ import annotations

import json
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout


KV = """
<RootView>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(8)
    Label:
        text: "Game Bot V2 Config (Prototype)"
        size_hint_y: None
        height: dp(36)
    TextInput:
        id: config_text
        text: root.config_json
        multiline: True
        font_size: "14sp"
    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(8)
        Button:
            text: "Load"
            on_release: root.load_config()
        Button:
            text: "Save"
            on_release: root.save_config()
        Button:
            text: "Reset"
            on_release: root.reset_config()
"""


class RootView(BoxLayout):
    config_json = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_path = Path("task_mobile_config.json")
        self.reset_config()

    def reset_config(self) -> None:
        template = {
            "meta": {
                "name": "Mobile Config",
                "design_resolution": [1280, 720],
                "loop_count": 1,
            },
            "steps": [],
        }
        self.config_json = json.dumps(template, ensure_ascii=False, indent=2)
        if "config_text" in self.ids:
            self.ids.config_text.text = self.config_json

    def load_config(self) -> None:
        if not self.config_path.exists():
            self.reset_config()
            return
        self.config_json = self.config_path.read_text(encoding="utf-8")
        self.ids.config_text.text = self.config_json

    def save_config(self) -> None:
        text = self.ids.config_text.text
        # Validate JSON before save.
        json.loads(text)
        self.config_path.write_text(text, encoding="utf-8")
        self.config_json = text


class MobileConfigApp(App):
    def build(self):
        Builder.load_string(KV)
        return RootView()


if __name__ == "__main__":
    MobileConfigApp().run()

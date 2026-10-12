import json
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
MARKETPLACE = PLUGIN.parents[1] / ".agents" / "plugins" / "marketplace.json"


class PluginRoutingTests(unittest.TestCase):
    def test_tenorshare_identity_and_discovery_are_independent(self):
        plugin = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        self.assertEqual("tenorshare-cms-assistant", plugin["name"])
        self.assertEqual(plugin["name"], marketplace["plugins"][0]["name"])
        skill_root = PLUGIN / plugin["skills"]
        exposed = {path.name for path in skill_root.iterdir() if (path / "SKILL.md").is_file()}
        self.assertEqual({"tenorshare-cms-article-assistant", "cms-site-standard-builder",
                          "cms-site-article-assistant"}, exposed)
        self.assertNotIn("pogoskill-cms-en-publisher", exposed)


if __name__ == "__main__":
    unittest.main()

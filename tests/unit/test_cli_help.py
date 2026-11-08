import unittest
from typer.testing import CliRunner
from winebox.interface.cli import app


class TestCliHelp(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_help_command_root(self):
        result = self.runner.invoke(app, ["help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.output)
        self.assertIn("WineBox", result.output)

    def test_help_command_subcommand(self):
        result = self.runner.invoke(app, ["help", "prefix"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("prefix", result.output)
        self.assertIn("create", result.output)

    def test_help_command_unknown_topic(self):
        result = self.runner.invoke(app, ["help", "unknown_foo"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unknown command or topic", result.output)


if __name__ == "__main__":
    unittest.main()

"""CLI parsing tests — we don't run the network pipeline; we just confirm Typer
wires every mode subcommand and the option set is what the user expects."""

from typer.testing import CliRunner

from researchhq.cli import app

runner = CliRunner()


def test_help_lists_research_subgroup():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "research" in result.output


def test_research_help_lists_all_modes():
    result = runner.invoke(app, ["research", "--help"])
    assert result.exit_code == 0
    for mode in ("topic", "company", "competitor", "tech", "market", "news", "academic"):
        assert mode in result.output


def test_modes_command_runs():
    result = runner.invoke(app, ["modes"])
    assert result.exit_code == 0


def test_each_mode_subcommand_accepts_format_and_verbosity_flags():
    for mode in ("topic", "company", "competitor", "tech", "market", "news", "academic"):
        result = runner.invoke(app, ["research", mode, "--help"])
        assert result.exit_code == 0, result.output
        for flag in ("--format", "--quiet", "--verbose", "--debug"):
            assert flag in result.output, f"{mode} missing {flag}\n{result.output}"


def test_status_command_runs():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0

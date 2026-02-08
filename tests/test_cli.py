import pytest

import puk.__main__ as main_mod
from puk.__main__ import build_parser


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.prompt is None
    assert args.append_to_run is None
    assert args.model is None
    assert args.provider is None
    assert args.temperature is None
    assert args.max_output_tokens is None
    assert args.workspace == "."


def test_parser_one_shot_prompt():
    args = build_parser().parse_args(
        [
            "find powerpoint python files",
            "--append-to-run",
            "abc",
            "--provider",
            "openai",
            "--model",
            "gpt-5-mini",
            "--temperature",
            "0.4",
            "--max-output-tokens",
            "512",
            "--workspace",
            "/tmp/project",
        ]
    )
    assert args.prompt == "find powerpoint python files"
    assert args.append_to_run == "abc"
    assert args.provider == "openai"
    assert args.model == "gpt-5-mini"
    assert args.temperature == 0.4
    assert args.max_output_tokens == 512
    assert args.workspace == "/tmp/project"


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    def _raise_interrupt(config, one_shot_prompt=None, append_to_run=None, argv=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(main_mod, "run_sync", _raise_interrupt)
    monkeypatch.setattr("sys.argv", ["puk", "--provider", "copilot"])

    with pytest.raises(SystemExit) as exc:
        main_mod.main()

    assert exc.value.code == 130
    captured = capsys.readouterr()
    assert "Puk has been interrupted by the user." in captured.err

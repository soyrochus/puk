import pytest

import puk.__main__ as main_mod
from puk.__main__ import build_parser


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.prompt is None
    assert args.model == "gpt-5"
    assert args.workspace == "."


def test_parser_one_shot_prompt():
    args = build_parser().parse_args(
        ["find powerpoint python files", "--model", "gpt-5-mini", "--workspace", "/tmp/project"]
    )
    assert args.prompt == "find powerpoint python files"
    assert args.model == "gpt-5-mini"
    assert args.workspace == "/tmp/project"


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    def _raise_interrupt(config, one_shot_prompt=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(main_mod, "run_sync", _raise_interrupt)
    monkeypatch.setattr("sys.argv", ["puk"])

    with pytest.raises(SystemExit) as exc:
        main_mod.main()

    assert exc.value.code == 130
    captured = capsys.readouterr()
    assert "Puk has been interrupted by the user." in captured.err

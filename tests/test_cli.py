import pytest
from types import SimpleNamespace

import puk.__main__ as main_mod
from puk.__main__ import build_parser, build_run_parser, build_runs_parser


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.prompt is None
    assert args.append_to_run is None
    assert args.model is None
    assert args.provider is None
    assert args.temperature is None
    assert args.max_output_tokens is None
    assert args.workspace_root is None
    assert args.workspace_discover_root is None
    assert args.workspace_allow_outside_root is None
    assert args.workspace_follow_symlinks is None
    assert args.workspace_max_file_bytes is None
    assert args.workspace_ignore is None
    assert args.workspace_allow_globs is None
    assert args.workspace_deny_globs is None
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


def test_runs_list_subcommand():
    parser = build_runs_parser()
    args = parser.parse_args(["list", "--workspace", "/tmp/ws"])
    assert args.command == "list"
    assert args.workspace == "/tmp/ws"


def test_run_subcommand_parsing():
    parser = build_run_parser()
    args = parser.parse_args(
        [
            "specs/playbook.md",
            "--param",
            "target=docs",
            "--param",
            "flag=true",
            "--mode",
            "plan",
            "--append-to-run",
            "run-123",
            "--workspace",
            "/tmp/ws",
        ]
    )
    assert args.playbook_path == "specs/playbook.md"
    assert args.param == ["target=docs", "flag=true"]
    assert args.mode == "plan"
    assert args.append_to_run == "run-123"
    assert args.workspace == "/tmp/ws"


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


def test_run_main_handles_runtime_error_without_traceback(monkeypatch):
    monkeypatch.setattr(main_mod, "resolve_llm_config", lambda workspace, parameters: SimpleNamespace(settings=object()))
    monkeypatch.setattr(main_mod, "log_resolved_llm_config", lambda resolved: None)
    monkeypatch.setattr(
        main_mod,
        "resolve_workspace_config",
        lambda workspace, parameters: SimpleNamespace(settings=SimpleNamespace(root=str(workspace), allow_outside_root=False, follow_symlinks=False)),
    )
    monkeypatch.setattr(main_mod, "log_resolved_workspace_config", lambda resolved: None)
    monkeypatch.setattr(main_mod, "load_playbook", lambda path: SimpleNamespace(parameters={}, run_mode="apply"))
    monkeypatch.setattr(main_mod, "parse_param_assignments", lambda values: {})
    monkeypatch.setattr(main_mod, "resolve_parameters", lambda specs, raw, workspace, **kwargs: {})

    def _raise_runtime(*args, **kwargs):
        raise RuntimeError("Timeout after 600s waiting for session.idle")

    monkeypatch.setattr(main_mod, "run_playbook_sync", _raise_runtime)
    monkeypatch.setattr("sys.argv", ["puk", "run", "playbooks/reverse-engineer-docs.md"])

    with pytest.raises(SystemExit) as exc:
        main_mod.main()

    assert str(exc.value) == "Timeout after 600s waiting for session.idle"


def test_run_main_handles_missing_copilot_binary(monkeypatch):
    monkeypatch.setattr(main_mod, "resolve_llm_config", lambda workspace, parameters: SimpleNamespace(settings=object()))
    monkeypatch.setattr(main_mod, "log_resolved_llm_config", lambda resolved: None)
    monkeypatch.setattr(
        main_mod,
        "resolve_workspace_config",
        lambda workspace, parameters: SimpleNamespace(settings=SimpleNamespace(root=str(workspace), allow_outside_root=False, follow_symlinks=False)),
    )
    monkeypatch.setattr(main_mod, "log_resolved_workspace_config", lambda resolved: None)
    monkeypatch.setattr(main_mod, "load_playbook", lambda path: SimpleNamespace(parameters={}, run_mode="apply"))
    monkeypatch.setattr(main_mod, "parse_param_assignments", lambda values: {})
    monkeypatch.setattr(main_mod, "resolve_parameters", lambda specs, raw, workspace, **kwargs: {})

    def _raise_fnf(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "copilot")

    monkeypatch.setattr(main_mod, "run_playbook_sync", _raise_fnf)
    monkeypatch.setattr("sys.argv", ["puk", "run", "playbooks/reverse-engineer-docs.md"])

    with pytest.raises(SystemExit) as exc:
        main_mod.main()

    assert str(exc.value) == "The `copilot` CLI binary was not found. Install GitHub Copilot CLI first."

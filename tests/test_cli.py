from puk.__main__ import build_parser


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.mode == "fancy"
    assert args.prompt is None


def test_parser_one_shot_prompt():
    args = build_parser().parse_args(["find powerpoint python files", "--mode", "plain"])
    assert args.prompt == "find powerpoint python files"
    assert args.mode == "plain"

from inp_tool.field_help import get_help, known_blocks, known_keywords


def test_get_help_known_field():
    help_zh = get_help("physics", "reftem")
    assert "温度" in help_zh


def test_get_help_unknown_field_returns_empty():
    assert get_help("nonexistent_block", "x") == ""
    assert get_help("physics", "nonexistent_keyword") == ""


def test_known_blocks_includes_physics():
    assert "physics" in known_blocks()


def test_known_keywords_physics_block():
    keys = known_keywords("physics")
    assert "reftem" in keys
    assert "reynolds" in keys


def test_help_text_length_reasonable():
    for block, kw in [("physics", "reftem"), ("guiopts", "aero_ma"),
                      ("guiopts", "aero_alpha"), ("guiopts", "aero_beta")]:
        text = get_help(block, kw)
        assert 0 < len(text) <= 200

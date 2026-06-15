# tests/test_gui_i18n.py
from inp_tool.i18n_gui import MESSAGES_GUI, tg, supported_keys


def test_messages_gui_has_zh_and_en():
    assert "zh" in MESSAGES_GUI
    assert "en" in MESSAGES_GUI


def test_zh_and_en_have_same_keys():
    zh = set(MESSAGES_GUI["zh"].keys())
    en = set(MESSAGES_GUI["en"].keys())
    missing_in_en = zh - en
    missing_in_zh = en - zh
    assert not missing_in_en, f"en 缺 key: {missing_in_en}"
    assert not missing_in_zh, f"zh 缺 key: {missing_in_zh}"


def test_tg_returns_zh_by_default():
    assert tg("menu.file") == "文件(&F)"


def test_tg_returns_en_after_set():
    from inp_tool.i18n_gui import set_gui_lang
    set_gui_lang("en")
    try:
        assert tg("menu.file") == "&File"
    finally:
        set_gui_lang("zh")


def test_tg_with_placeholder():
    assert "{n}".format(n=3) in tg("status.lines", n=3)


def test_supported_keys_returns_zh_keys():
    keys = supported_keys()
    assert "menu.file" in keys
    assert "sweep.btn.load_yaml" in keys

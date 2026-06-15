"""Tests for the FieldSearchBar widget."""
import pytest
from PySide2.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
from inp_tool_gui.widgets.field_search_bar import FieldSearchBar


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_filter_hides_non_matching(qapp):
    tree = QTreeWidget()
    tree.setHeaderLabels(["字段"])
    parent = QTreeWidgetItem(["physics"])
    a = QTreeWidgetItem(["reftem"])
    b = QTreeWidgetItem(["reynolds"])
    parent.addChild(a)
    parent.addChild(b)
    tree.addTopLevelItem(parent)

    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("reftem")
    assert not a.isHidden()
    assert b.isHidden()


def test_filter_substring_match(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["reftem"])
    tree.addTopLevelItem(a)
    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("reft")
    assert not a.isHidden()


def test_filter_empty_shows_all(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["x"])
    b = QTreeWidgetItem(["y"])
    tree.addTopLevelItem(a)
    tree.addTopLevelItem(b)
    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("")
    assert not a.isHidden()
    assert not b.isHidden()


def test_filter_shows_parents_of_matches(qapp):
    tree = QTreeWidget()
    parent = QTreeWidgetItem(["physics"])
    child = QTreeWidgetItem(["reftem"])
    parent.addChild(child)
    tree.addTopLevelItem(parent)

    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("reftem")
    assert not child.isHidden()
    assert not parent.isHidden()


def test_clear_resets(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["x"])
    tree.addTopLevelItem(a)
    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("zzz")
    assert a.isHidden()
    bar.set_query("")
    assert not a.isHidden()


def test_no_match_count_signal(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["x"])
    tree.addTopLevelItem(a)
    bar = FieldSearchBar()
    received = []
    bar.match_count_changed.connect(lambda n: received.append(n))
    bar.attach(tree)
    bar.set_query("zzz")
    assert 0 in received

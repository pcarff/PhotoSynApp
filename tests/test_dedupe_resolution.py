import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from gui.tabs.dedupe_tab import DedupeTab

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_dedupe_advance_after_resolution(qapp, tmp_path):
    # Setup test files
    trash_dir = tmp_path / "trash"
    trash_dir.mkdir()

    img1 = tmp_path / "img1.jpg"
    img1.write_bytes(b"image 1 bytes")
    img2 = tmp_path / "img2.jpg"
    img2.write_bytes(b"image 2 bytes")
    img3 = tmp_path / "img3.jpg"
    img3.write_bytes(b"image 3 bytes")
    img4 = tmp_path / "img4.jpg"
    img4.write_bytes(b"image 4 bytes")

    tab = DedupeTab()
    groups = [
        [
            {"path": str(img1), "filename": "img1.jpg", "width": 1920, "height": 1080, "size": 1000},
            {"path": str(img2), "filename": "img2.jpg", "width": 4032, "height": 3024, "size": 3000},
        ],
        [
            {"path": str(img3), "filename": "img3.jpg", "width": 1000, "height": 1000, "size": 500},
            {"path": str(img4), "filename": "img4.jpg", "width": 800, "height": 800, "size": 400},
        ],
    ]

    tab._on_finished(groups)
    assert tab.list_groups.count() == 2
    assert tab.current_group_idx == 0

    # 1. Test Smart Pick on Group 0:
    # img2 has higher resolution (4032x3024 vs 1920x1080), so img1 should be trashed, img2 kept
    # And the tab MUST automatically advance to the next duplicate group (Set #2)
    tab._keep_higher_res()

    assert len(tab.duplicate_groups) == 1
    assert tab.list_groups.count() == 1
    assert tab.current_group_idx == 0  # Now points to formerly group 1
    assert tab.list_groups.currentRow() == 0
    # Preview cards should now show img3 and img4
    assert "img3.jpg" in tab.lbl_info_left.text()
    assert "img4.jpg" in tab.lbl_info_right.text()

    # 2. Test Keep Left on remaining Group:
    tab._keep_left()
    assert len(tab.duplicate_groups) == 0
    assert tab.list_groups.count() == 0
    assert tab.current_group_idx == -1
    assert "No duplicates" in tab.lbl_preview_left.text()
    assert "No duplicates" in tab.lbl_preview_right.text()


def test_dedupe_multi_item_group(qapp, tmp_path):
    # Group with 3 items
    f1 = tmp_path / "f1.jpg"
    f1.write_bytes(b"1")
    f2 = tmp_path / "f2.jpg"
    f2.write_bytes(b"2")
    f3 = tmp_path / "f3.jpg"
    f3.write_bytes(b"3")

    tab = DedupeTab()
    groups = [
        [
            {"path": str(f1), "filename": "f1.jpg", "width": 100, "height": 100, "size": 10},
            {"path": str(f2), "filename": "f2.jpg", "width": 100, "height": 100, "size": 20},
            {"path": str(f3), "filename": "f3.jpg", "width": 100, "height": 100, "size": 30},
        ]
    ]
    tab._on_finished(groups)
    assert tab.list_groups.count() == 1

    # Compare f1 and f2 -> Keep Right (trash f1)
    tab._keep_right()
    # Should still have 1 group with remaining 2 items (f2 and f3)
    assert len(tab.duplicate_groups) == 1
    assert len(tab.duplicate_groups[0]) == 2
    assert tab.list_groups.count() == 1
    assert "f2.jpg" in tab.lbl_info_left.text()
    assert "f3.jpg" in tab.lbl_info_right.text()


def test_auto_resolve_all_highest_res(qapp, tmp_path, monkeypatch):
    # Mock message boxes to proceed without modal blocking in automated tests
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    # Group 1: 2 files, 4K vs 1080p -> 4K kept
    g1_low = tmp_path / "g1_low.jpg"
    g1_low.write_bytes(b"low")
    g1_high = tmp_path / "g1_high.jpg"
    g1_high.write_bytes(b"high")

    # Group 2: 3 files -> best resolution & size kept
    g2_a = tmp_path / "g2_a.jpg"
    g2_a.write_bytes(b"a")
    g2_b = tmp_path / "g2_b.jpg"
    g2_b.write_bytes(b"b")
    g2_c = tmp_path / "g2_c.jpg"
    g2_c.write_bytes(b"c")

    tab = DedupeTab()
    groups = [
        [
            {"path": str(g1_low), "filename": "g1_low.jpg", "width": 1920, "height": 1080, "size": 1000},
            {"path": str(g1_high), "filename": "g1_high.jpg", "width": 3840, "height": 2160, "size": 4000},
        ],
        [
            {"path": str(g2_a), "filename": "g2_a.jpg", "width": 800, "height": 600, "size": 200},
            {"path": str(g2_b), "filename": "g2_b.jpg", "width": 2048, "height": 1536, "size": 1500},
            {"path": str(g2_c), "filename": "g2_c.jpg", "width": 1024, "height": 768, "size": 500},
        ]
    ]

    tab._on_finished(groups)
    assert tab.list_groups.count() == 2
    assert tab.btn_auto_resolve_all.isEnabled() is True

    # Execute auto-resolve all
    tab._auto_resolve_all_highest_res()

    # All duplicate groups must be completely resolved
    assert len(tab.duplicate_groups) == 0
    assert tab.list_groups.count() == 0
    assert tab.current_group_idx == -1
    assert "No duplicates" in tab.lbl_preview_left.text()
    assert "No duplicates" in tab.lbl_preview_right.text()
    assert tab.btn_auto_resolve_all.isEnabled() is False

    # Check that highest resolution files still exist on disk
    assert g1_high.exists()
    assert g2_b.exists()

    # Check that lower resolution files were moved to trash
    trash_dir = Path("/Workspaces/Photos/_Duplicates_Trash")
    assert not g1_low.exists()
    assert not g2_a.exists()
    assert not g2_c.exists()

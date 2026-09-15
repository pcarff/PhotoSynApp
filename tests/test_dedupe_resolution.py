import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
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
    # Override trash folder to temporary directory for safe testing
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

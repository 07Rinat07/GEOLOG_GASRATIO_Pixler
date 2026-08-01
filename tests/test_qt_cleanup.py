from PySide6.QtWidgets import QWidget


def test_global_cleanup_does_not_call_fragile_close_event(qapp) -> None:
    class FragileWindow(QWidget):
        def closeEvent(self, event) -> None:  # type: ignore[override]
            raise AttributeError("'NoneType' object has no attribute 'close'")

    window = FragileWindow()
    window.show()
    qapp.processEvents()
    assert window.isVisible()
    # The autouse cleanup fixture owns isolation.  It must only hide the window
    # instead of calling close() or forcing DeferredDelete delivery; those paths
    # reproduce the Python teardown errors and the Windows native access violation.

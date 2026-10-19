"""The isolated test harness retains hidden Qt roots until process exit."""
import gc
from weakref import ref

from PySide6.QtWidgets import QWidget
from shiboken6 import isValid
import pytest

import conftest


def test_hidden_window_wrapper_survives_final_python_gc(qapp):
    window = QWidget()
    window.setObjectName("retained-test-root")
    window.show()
    reference = ref(window)
    cleanup = conftest.close_qt_windows_after_test.__wrapped__()
    next(cleanup)
    with pytest.raises(StopIteration):
        next(cleanup)
    assert not window.isVisible()
    del window
    gc.collect()
    retained = reference()
    assert retained is not None
    assert isValid(retained)
    assert retained.objectName() == "retained-test-root"

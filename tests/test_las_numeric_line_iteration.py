import pytest

from geoworkbench.data.las_adapter import _iter_section_payload_lines


@pytest.mark.parametrize("newline", (b"\n", b"\r\n", b"\r"))
@pytest.mark.parametrize("trailing", (False, True))
def test_las_payload_lines_preserve_rows_with_linear_search_work(newline, trailing):
    class MeasuredBytes(bytes):
        searched_bytes = 0

        def find(self, sub, start=0, end=None):
            stop = len(self) if end is None else end
            self.searched_bytes += max(0, stop - start)
            return super().find(sub, start, stop)

    rows = (b"0.0 1.25 -999.25", b"", b"# comment", b"0.2 2.50 3.0") * 250
    section = newline.join((b"~ASCII", *rows)) + (newline if trailing else b"")
    prefix = b"~Version\nVERS. 2.0\n"
    raw = MeasuredBytes(prefix + section + b"\n~Other\nMust not be yielded")
    actual = tuple(_iter_section_payload_lines(raw, len(prefix), len(prefix) + len(section)))
    assert actual == rows
    # Count searched byte ranges, rather than using a machine-dependent timer.
    # The former repeated find of an absent newline exceeded this linear budget.
    assert raw.searched_bytes <= 2 * len(section)


def test_las_payload_lines_accept_mixed_newlines_and_bounded_unterminated_tail():
    section = b"~ASCII\r\n0 1\r1 2\n\n2 3\r\n3 4"
    raw = b"prefix" + section + b"\n~Other\n5 6"
    assert tuple(_iter_section_payload_lines(raw, 6, 6 + len(section))) == (
        b"0 1", b"1 2", b"", b"2 3", b"3 4",
    )
    assert tuple(_iter_section_payload_lines(b"~ASCII", 0, 6)) == ()

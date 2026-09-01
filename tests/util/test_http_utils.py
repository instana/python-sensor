# (c) Copyright IBM Corp. 2026

from typing import Optional
from unittest.mock import MagicMock

from instana.util.http import should_mark_http_exit_as_error


def _opts(classify_all: bool = False, classify_codes: Optional[list] = None) -> MagicMock:
    """Return a minimal options-like object."""
    opts = MagicMock()
    opts.http_exit_classify_all_4xx_as_errors = classify_all
    opts.http_exit_classify_as_errors = classify_codes if classify_codes is not None else []
    return opts


class TestShouldMarkHttpExitAsError:
    # ------------------------------------------------------------------ 5xx
    def test_500_is_always_error(self) -> None:
        assert should_mark_http_exit_as_error(500, _opts())

    def test_503_is_always_error(self) -> None:
        assert should_mark_http_exit_as_error(503, _opts())

    def test_599_is_always_error(self) -> None:
        assert should_mark_http_exit_as_error(599, _opts())

    # ------------------------------------------------------------------ 2xx / 3xx
    def test_200_is_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(200, _opts())

    def test_301_is_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(301, _opts())

    # ------------------------------------------------------------------ 4xx default (opt-in off)
    def test_400_default_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(400, _opts())

    def test_401_default_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(401, _opts())

    def test_403_default_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(403, _opts())

    def test_404_default_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(404, _opts())

    def test_499_default_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(499, _opts())

    # ------------------------------------------------------------------ classify_all_4xx
    def test_400_classify_all_is_error(self) -> None:
        assert should_mark_http_exit_as_error(400, _opts(classify_all=True))

    def test_404_classify_all_is_error(self) -> None:
        assert should_mark_http_exit_as_error(404, _opts(classify_all=True))

    def test_499_classify_all_is_error(self) -> None:
        assert should_mark_http_exit_as_error(499, _opts(classify_all=True))

    def test_399_classify_all_not_error(self) -> None:
        """399 is outside 4xx range — must not be affected by classify_all."""
        assert not should_mark_http_exit_as_error(399, _opts(classify_all=True))

    # ------------------------------------------------------------------ classify_as_errors list
    def test_401_in_list_is_error(self) -> None:
        assert should_mark_http_exit_as_error(401, _opts(classify_codes=[401, 403]))

    def test_403_in_list_is_error(self) -> None:
        assert should_mark_http_exit_as_error(403, _opts(classify_codes=[401, 403]))

    def test_404_not_in_list_not_error(self) -> None:
        assert not should_mark_http_exit_as_error(404, _opts(classify_codes=[401, 403]))

    # ------------------------------------------------------------------ precedence: list wins over classify_all
    def test_list_takes_precedence_over_classify_all(self) -> None:
        """When classify_as_errors is set, classify_all_4xx is ignored."""
        opts = _opts(classify_all=True, classify_codes=[401])
        # 401 is in the list → error
        assert should_mark_http_exit_as_error(401, opts)
        # 404 is NOT in the list → no error, even though classify_all=True
        assert not should_mark_http_exit_as_error(404, opts)

    # ------------------------------------------------------------------ boundary
    def test_boundary_399_not_4xx(self) -> None:
        assert not should_mark_http_exit_as_error(399, _opts(classify_all=True))

    def test_boundary_500_always_error(self) -> None:
        assert should_mark_http_exit_as_error(500, _opts())

    def test_boundary_499_classify_all(self) -> None:
        assert should_mark_http_exit_as_error(499, _opts(classify_all=True))

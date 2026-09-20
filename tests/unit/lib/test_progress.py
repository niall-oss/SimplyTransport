from unittest.mock import MagicMock

import pytest
from SimplyTransport.lib.progress import DEFAULT_ADVANCE_EVERY, ProgressTicker


def test_no_update_until_every_ticks() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=4)
    for _ in range(3):
        ticker.tick()
    progress.update.assert_not_called()


def test_update_fires_once_at_threshold() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=4)
    for _ in range(4):
        ticker.tick()
    progress.update.assert_called_once_with(1, advance=4)


def test_flush_sends_remainder() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=4)
    ticker.tick()
    ticker.tick()
    progress.update.assert_not_called()
    ticker.flush()
    progress.update.assert_called_once_with(1, advance=2)


def test_flush_is_noop_when_empty() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=4)
    ticker.flush()
    progress.update.assert_not_called()


def test_tick_n_crosses_threshold_in_one_call() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=4)
    ticker.tick(5)
    progress.update.assert_called_once_with(1, advance=5)


def test_tick_ignores_non_positive() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=1)
    ticker.tick(0)
    ticker.tick(-3)
    progress.update.assert_not_called()


def test_noop_without_progress() -> None:
    ticker = ProgressTicker(None, task_id=1, every=1)
    ticker.tick()
    ticker.flush()


def test_noop_without_task_id() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=None, every=1)
    ticker.tick()
    ticker.flush()
    progress.update.assert_not_called()


def test_task_id_zero_is_valid() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=0, every=1)
    ticker.tick()
    progress.update.assert_called_once_with(0, advance=1)


def test_context_manager_flushes_remainder() -> None:
    progress = MagicMock()
    with ProgressTicker(progress, task_id=1, every=4) as ticker:
        ticker.tick()
        ticker.tick()
        progress.update.assert_not_called()
    progress.update.assert_called_once_with(1, advance=2)


def test_context_manager_flushes_on_exception() -> None:
    progress = MagicMock()
    with pytest.raises(RuntimeError, match="boom"), ProgressTicker(progress, task_id=1, every=4) as ticker:
        ticker.tick()
        raise RuntimeError("boom")
    progress.update.assert_called_once_with(1, advance=1)


def test_every_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="every must be >= 1"):
        ProgressTicker(MagicMock(), task_id=1, every=0)


def test_default_every_matches_public_constant() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1)
    ticker.tick(DEFAULT_ADVANCE_EVERY - 1)
    progress.update.assert_not_called()
    ticker.tick()
    progress.update.assert_called_once_with(1, advance=DEFAULT_ADVANCE_EVERY)


def test_second_batch_after_threshold() -> None:
    progress = MagicMock()
    ticker = ProgressTicker(progress, task_id=1, every=2)
    ticker.tick()
    ticker.tick()
    ticker.tick()
    ticker.tick()
    assert progress.update.call_count == 2
    progress.update.assert_any_call(1, advance=2)

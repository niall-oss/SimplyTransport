from typing import Any, Self

DEFAULT_ADVANCE_EVERY = 100


class ProgressTicker:
    """Batch Rich ``progress.update`` calls so tight loops don't redraw every item.

    ``tick()`` counts items; ``Progress.update`` runs once at least ``every``
    items have accumulated (100 by default). ``flush()`` sends the remainder.
    Using the ticker as a context manager flushes on the way out.

    Omit ``progress`` or ``task_id`` and every method is a no-op, so callers
    can always construct a ticker.
    """

    def __init__(
        self,
        progress: Any | None = None,
        task_id: int | None = None,
        *,
        every: int = DEFAULT_ADVANCE_EVERY,
    ) -> None:
        if every < 1:
            msg = "every must be >= 1"
            raise ValueError(msg)
        self._progress = progress
        self._task_id = task_id
        self._every = every
        self._pending = 0

    def tick(self, n: int = 1) -> None:
        """Count ``n`` completed items (default 1). Negative or zero is ignored."""
        if self._progress is None or self._task_id is None or n <= 0:
            return
        self._pending += n
        if self._pending >= self._every:
            self._progress.update(self._task_id, advance=self._pending)
            self._pending = 0

    def flush(self) -> None:
        """Send any leftover count that has not reached ``every``."""
        if self._progress is None or self._task_id is None or self._pending == 0:
            return
        self._progress.update(self._task_id, advance=self._pending)
        self._pending = 0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.flush()

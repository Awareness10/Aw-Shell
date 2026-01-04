from typing import Any, Callable, List


class Signal:
    __slots__ = ('_callbacks',)

    def __init__(self):
        self._callbacks: List[Callable] = []

    def connect(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable) -> bool:
        try:
            self._callbacks.remove(callback)
            return True
        except ValueError:
            return False

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for callback in self._callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"Error in signal callback: {e}")

    def clear(self) -> None:
        self._callbacks.clear()

    @property
    def handler_count(self) -> int:
        return len(self._callbacks)

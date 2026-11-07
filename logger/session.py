import time
from enum import Enum, auto

class SessionException(Exception):
    def __init__(self, message, status) -> None:
        super().__init__(message)

        self.state = status

class SessionStatus(Enum):
    NOT_STARTED = auto()
    RUNNING = auto()
    PAUSED = auto()
    IDLE = auto()
    ENDED = auto()

class Session:
    """ Generic, testable base class for tracking time and states. """

    def __init__(self, precision: int = 2) -> None:
        self.precision = precision
        self.start_time: float | None = None
        self.end_time: float | None = None

        self.splits: list[dict] = []
        self._total_pause_time: float = 0.0
        self._pause_start: float | None = None


    def __str__(self):
        return f"Status: {self.status}\nTime Elapsed: {self.elapsed_time}"

    def __repr__(self):
        return f"{self.__class__.__name__}(precision={self.precision!r})"
    
    @property
    def precision(self) -> int:
        return self._precision

    @precision.setter
    def precision(self, value: int) -> None:
        if not 0 <= value <= 9:
            raise SessionException("Value must be between 0 and 9", self.status)
        self._precision = value

    @property
    def status(self) -> SessionStatus:
        if self.start_time is None:
            return SessionStatus.NOT_STARTED
        if self._pause_start is not None:
            return SessionStatus.PAUSED
        if self.end_time is None:
            return SessionStatus.RUNNING
        return SessionStatus.ENDED

    @property
    def elapsed_time(self) -> float:
        if self.status == SessionStatus.NOT_STARTED:
            return 0.0
        
        current = self.end_time or time.perf_counter()
        return round(max(0.0, current - self.start_time), self.precision)

    @property
    def active_time(self) -> float:
        if self.status == SessionStatus.NOT_STARTED:
            return 0.0
        
        if self.status == SessionStatus.ENDED:
            current = self.end_time
        elif self.status == SessionStatus.PAUSED:
            current = self._pause_start
        else:
            current = time.perf_counter()

        active_time = current - self.start_time - self._total_pause_time
        return round(max(0.0, active_time), self.precision)

    def start(self) -> None:
        if self.status != SessionStatus.NOT_STARTED:
            raise SessionException("Session was already started.", self.status)
        self.start_time = time.perf_counter()

    def pause(self) -> None:
        if self.status != SessionStatus.RUNNING:
            raise SessionException("Can only pause a running session.", self.status)
        self._pause_start = time.perf_counter()

    def resume(self) -> None:
        if self.status != SessionStatus.PAUSED:
            raise SessionException("Can only resume a paused session.", self.status)
        self._total_pause_time += time.perf_counter() - self._pause_start
        self._pause_start = None

    def split(self, label: str = "", split_type: str = "active") -> float:
        if self.status not in (SessionStatus.RUNNING, SessionStatus.PAUSED):
            raise SessionException("Cannot split on an inactive session.", self.status)

        split_types = {
            "active": self.active_time,
            "elapsed": self.elapsed_time
        }

        if split_type not in split_types:
            raise SessionException(f"Invalid split type. Value split types: {", ".join(split_types)}.", self.status)

        current_elapsed = split_types.get(split_type)
        self.splits.append({
            "label": label or f"Split {len(self.splits) + 1}",
            "elapsed_time": current_elapsed,
            "timestamp": time.time()
        })
        return current_elapsed

    def end(self) -> None:
        if self.status == SessionStatus.NOT_STARTED:
            raise SessionException("Cannot end a session that has not started.", self.status)
        if self.status == SessionStatus.ENDED:
            raise SessionException("Session already ended.", self.status)

        if self.status == SessionStatus.PAUSED:
            self.resume()
        
        self.end_time = time.perf_counter()

    def to_dict(self) -> dict:
        return {
            "status": self.status.name,
            "total_elapsed_time": self.elapsed_time,
            "total_active_time": self.active_time,
            "splits": self.splits,
            "has_splits": len(self.splits) > 0
        }

    
from collections.abc import Callable
from enum import Enum, auto
from functools import wraps
import time

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

class _SessionTime:
    _METRICS = {"total", "paused", "idle", "active"}
    
    def __init__(self, session: Session) -> None:
        self._s = session

    def __getattribute__(self, name):
        if name in _SessionTime._METRICS:
            session = super().__getattribute__("_s")
            if session.status == SessionStatus.NOT_STARTED:
                return 0.0
            
            raw_value = super().__getattribute__(name)
            if session.precision <= 0:
                return int(max(0.0, raw_value))
            return round(max(0.0, raw_value), session.precision)

        return super().__getattribute__(name)

    @property
    def total(self) -> float | int:
        return (self._s.end_time or self._s.clock()) - self._s.start_time

    @property
    def paused(self) -> float | int:
        return self._s._sum_time_list(self._s.pauses, self._s._pause_start, self._s.clock())

    @property
    def idle(self) -> float | int:
        return self._s._sum_time_list(self._s.idles, self._s._idle_start, self._s.clock())

    @property
    def active(self) -> float | int:
        if self._s.status == SessionStatus.RUNNING:
            current = self._s.clock()
        elif self._s.status == SessionStatus.ENDED:
            current = self._s.end_time
        else:
            current = self._s._pause_start or self._s._idle_start

        non_active_time = self._s.time.paused + self._s.time.idle
        return (current - self._s.start_time) - non_active_time


class Session:
    """ Generic, testable base class for tracking time and states. """

    def __init__(self, precision: int = 2, clock: Callable[[], float | int] = time.perf_counter) -> None:

        self._precision = precision
        self._clock = clock
        self._time = _SessionTime(self)
        
        self.start_time: float | None = None
        self.end_time: float | None = None
        self._pause_start: float | None = None
        self._idle_start: float | None = None

        self.splits: list[dict] = []
        self.pauses: list[dict] = []
        self.idles: list[dict] = []

    def __str__(self):
        return f"Status: {self.status}\nTime Elapsed: {self.total_time}"

    def __repr__(self):
        return f"{self.__class__.__name__}(precision={self.precision!r})"
    
    @property
    def precision(self) -> int:
        return self._precision

    @property
    def clock(self) -> Callable[[], float | int]:
        return self._clock

    @property
    def status(self) -> SessionStatus:
        if self.start_time is None:
            return SessionStatus.NOT_STARTED
        if self.end_time is None:
            if self._pause_start is not None:
                return SessionStatus.PAUSED
            if self._idle_start is not None:
                return SessionStatus.IDLE
            return SessionStatus.RUNNING
        return SessionStatus.ENDED

    @property
    def time(self) -> _SessionTime:
        return self._time

    def start(self) -> None:
        if self.status != SessionStatus.NOT_STARTED:
            raise SessionException("Session was already started.", self.status)
        self.start_time = self.clock()

    def pause(self, reason: str = "manual") -> None:
        if self.status != SessionStatus.RUNNING:
            raise SessionException("Can only pause a running session.", self.status)
        self._pause_start = self.clock()

        self.pauses.append({
            "reason": reason,
            "start_wall_time": time.time(),
            "start_perf": self._pause_start,
            "end_perf": None,
            "duration": 0.0
        })

    def idle(self) -> None:
        if self.status != SessionStatus.RUNNING:
            raise SessionException("Can only declare idle on a running session.", self.status)
        self._idle_start = self.clock()

        self.idles.append({
            "start_wall_time": time.time(),
            "start_perf": self._idle_start,
            "end_perf": None,
            "duration": 0.0
        })

    def resume(self) -> None:
        if self.status not in (SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Can only resume a paused or idle session.", self.status)
        
        now = self.clock()

        if self.status == SessionStatus.PAUSED:
            last_pause = self.pauses[-1]
            last_pause["end_perf"] = now
            last_pause["duration"] = now - self._pause_start
            
            self._pause_start = None
        else:
            last_idle = self.idles[-1]
            last_idle["end_perf"] = now
            last_idle["duration"] = now - self._idle_start
            
            self._idle_start = None



    def split(self, label: str = "", split_type: str = "active") -> float:
        if self.status not in (SessionStatus.RUNNING, SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Cannot split on an inactive session.", self.status)

        split_types = {
            "active": self.total_time_active,
            "elapsed": self.total_time
        }

        if split_type not in split_types:
            raise SessionException(f"Invalid split type. Value split types: {', '.join(split_types)}.", self.status)

        current_elapsed = split_types.get(split_type)
        self.splits.append({
            "label": label or f"Split {len(self.splits) + 1}",
            "total_time": current_elapsed,
            "timestamp": time.time(),
            "time_perf": self.clock()
        })
        return current_elapsed

    def end(self) -> None:
        if self.status == SessionStatus.NOT_STARTED:
            raise SessionException("Cannot end a session that has not started.", self.status)
        if self.status == SessionStatus.ENDED:
            raise SessionException("Session already ended.", self.status)

        now = self.clock()

        if self._pause_start != None:
            last_pause = self.pauses[-1]
            last_pause["end_perf"] = now
            last_pause["duration"] = now - self._pause_start
            self._pause_start = None
        elif self._idle_start != None:
            last_idle = self.idles[-1]
            last_idle["end_perf"] = now
            last_idle["duration"] = now - self._idle_start
            self._idle_start = None

        self.end_time = now

    def to_dict(self) -> dict:
        return {
            "status": self.status.name,
            "total_total_time": self.total_time,
            "total_total_time_active": self.total_time_active,
            "splits": self.splits,
            "has_splits": len(self.splits) > 0
        }

    @staticmethod
    def _sum_time_list(list: list, status_start_time: float | None, current_time: float | None) -> float:
        total_time = sum([i["duration"] for i in list])
        
        if status_start_time is not None:
            total_time += current_time - status_start_time

        return total_time
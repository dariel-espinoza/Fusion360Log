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

        self.start_time: float | None = None
        self.end_time: float | None = None
        self._pause_start: float | None = None
        self._idle_start: float | None = None

        self.splits: list[dict] = []
        self.pauses: list[dict] = []
        self.idles: list[dict] = []

        self.precision = precision
    
    @property
    def precision(self) -> int:
        return self._precision

    @precision.setter
    def precision(self, value: int) -> None:
        current_status = getattr(self, "status", SessionStatus.NOT_STARTED)
        if not 0 <= value <= 9:
            raise SessionException("Value must be between 0 and 9", current_status)
        
        self._precision = value

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
    def total_time(self) -> float:
        if self.status == SessionStatus.NOT_STARTED:
            return 0.0
        
        current = self.end_time or time.perf_counter()
        return round(max(0.0, current - self.start_time), self.precision)

    @property
    def total_time_paused(self) -> float:
        if self.status == SessionStatus.NOT_STARTED:
            return 0.0

        total_time_paused = sum([pause["duration"] for pause in self.pauses])

        if self._pause_start is not None:
            current_pause_time = time.perf_counter() - self._pause_start
            total_time_paused += current_pause_time

        return round(total_time_paused, self.precision)

    @property
    def total_time_idle(self) -> float:
        if self.status == SessionStatus.NOT_STARTED:
            return 0.0

        total_time_idle = sum([idle["duration"] for idle in self.idles])
        
        if self._idle_start is not None:
            current_idle_time = time.perf_counter() - self._idle_start
            total_time_idle += current_idle_time

        return round(total_time_idle, self.precision)

    @property
    def total_time_active(self) -> float:
        if self.status == SessionStatus.NOT_STARTED:
            return 0.0
        
        if self.status == SessionStatus.RUNNING:
            current = time.perf_counter()
        elif self.status == SessionStatus.ENDED:
            current = self.end_time
        else:
            current = self._pause_start or self._idle_start

        non_active_time = self.total_time_paused + self.total_time_idle
        current_total_time = current - self.start_time
        total_time_active = current_total_time - non_active_time
        return round(max(0.0, total_time_active), self.precision)

    def start(self) -> None:
        if self.status != SessionStatus.NOT_STARTED:
            raise SessionException("Session was already started.", self.status)
        self.start_time = time.perf_counter()

    def pause(self, reason: str = "manual") -> None:
        if self.status != SessionStatus.RUNNING:
            raise SessionException("Can only pause a running session.", self.status)
        self._pause_start = time.perf_counter()

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
        self._idle_start = time.perf_counter()

        self.idles.append({
            "start_wall_time": time.time(),
            "start_perf": self._idle_start,
            "end_perf": None,
            "duration": 0.0
        })

    def resume(self) -> None:
        if self.status not in (SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Can only resume a paused or idle session.", self.status)
        
        now = time.perf_counter()

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
            "time_perf": time.perf_counter()
        })
        return current_elapsed

    def end(self) -> None:
        if self.status == SessionStatus.NOT_STARTED:
            raise SessionException("Cannot end a session that has not started.", self.status)
        if self.status == SessionStatus.ENDED:
            raise SessionException("Session already ended.", self.status)

        now = time.perf_counter()

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

    def __str__(self):
        return f"Status: {self.status}\nTime Elapsed: {self.total_time}"

    def __repr__(self):
        return f"{self.__class__.__name__}(precision={self.precision!r})"
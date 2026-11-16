import time
from enum import Enum, auto
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Optional, Self


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

@dataclass(frozen=True, slots=True)
class Clock:
    monotonic: Callable[[], float] = time.perf_counter
    wall: Optional[Callable[[], float]] = time.time

    def __call__(self) -> float:
        return self.monotonic()

    def __str__(self) -> str:
        monotonic, wall = self.now()
        return f'Monotonic: {monotonic}\nWall: {wall}'

    def now(self) -> tuple[float, Optional[float]]:
        return (
            self.monotonic(), 
            self.wall() if self.wall is not None else None,
            )

    def utc_now(self) -> datetime | None:
        if self.wall is None:
            return None
        return datetime.fromtimestamp(self.wall(), tz=timezone.utc)

@dataclass(frozen=True, slots=True)
class _SessionStatus:
    _history: list[SessionStatus] = field(default_factory=list)

    def __call__(self) -> Optional[SessionStatus]:
        return self.current

    def __str__(self) -> str:
        return f'Current: {self.current}\nPrevious: {self.previous}'

    @property
    def history(self) -> list[SessionStatus]:
        return self._history

    @property
    def current(self) -> Optional[SessionStatus]:
        return self.history[-1] if self.history else None

    @property
    def previous(self) -> Optional[SessionStatus]:
        return self.history[-2] if self.history else None

    @property
    def add(self) -> _AddStatus:
        return self._AddStatus(history=self.history, ss_instance=self)

    @property
    def is_not_started(self) -> bool: return self.current == SessionStatus.NOT_STARTED
    @property
    def is_running(self) -> bool: return self.current == SessionStatus.RUNNING
    @property
    def is_paused(self) -> bool: return self.current == SessionStatus.PAUSED
    @property
    def is_idle(self) -> bool: return self.current == SessionStatus.IDLE
    @property
    def is_ended(self) -> bool: return self.current == SessionStatus.ENDED

    @dataclass(frozen=True, slots=True)
    class _AddStatus:
        history: list[SessionStatus]
        ss_instance: _SessionStatus

        @property
        def not_started(self) -> _SessionStatus: 
            return self._replace(self._append(SessionStatus.NOT_STARTED))

        @property
        def running(self) -> _SessionStatus: 
            return self._replace(self._append(SessionStatus.RUNNING))

        @property
        def paused(self) -> _SessionStatus: 
            return self._replace(self._append(SessionStatus.PAUSED))

        @property
        def idle(self) -> _SessionStatus: 
            return self._replace(self._append(SessionStatus.IDLE))

        @property
        def ended(self) -> _SessionStatus: 
            return self._replace(self._append(SessionStatus.ENDED))

        def _replace(self, new_history: list[SessionStatus], ss_instance: Optional[_SessionStatus] = None) -> _SessionStatus:
            return replace(ss_instance or self.ss_instance, _history=new_history)

        def _append(self, status: SessionStatus) -> list[SessionStatus]:
            self.history.append(status)
            return self.history

class _SessionTime:
    _METRICS = {"total", "paused", "idle", "active"}
    
    def __init__(self, session: Session) -> None:
        self._s = session

    def __getattribute__(self, name):
        if name in _SessionTime._METRICS:
            session = super().__getattribute__("_s")
            if session.status.is_not_started:
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
        if self._s.status.is_running:
            current = self._s.clock()
        elif self._s.status.is_ended:
            current = self._s.end_time
        else:
            current = self._s._pause_start or self._s._idle_start

        non_active_time = self._s.time.paused + self._s.time.idle
        return (current - self._s.start_time) - non_active_time


class Session:
    """ Generic, testable base class for tracking time and states. """

    def __init__(
            self, 
            precision: int = 2,
            mono_clock: Callable[[], float | int] = time.perf_counter,
            wall_clock: Optional[Callable[[], float | int]] = time.time 
        ) -> None:

        self._precision = precision
        self._clock: Clock = Clock(monotonic=mono_clock, wall=wall_clock)
        self._time: _SessionTime = _SessionTime(self)
        self._status: _SessionStatus = _SessionStatus().add.not_started
        
        self.start_time: float | None = None
        self.end_time: float | None = None
        self._pause_start: float | None = None
        self._idle_start: float | None = None

        self.splits: list[dict] = []
        self.pauses: list[dict] = []
        self.idles: list[dict] = []

    def __str__(self):
        return f"Status: {self.status.current}\nTime Elapsed: {self.time.total}"

    def __repr__(self):
        return f"{self.__class__.__name__}(precision={self.precision!r})"
    
    @property
    def precision(self) -> int:
        return self._precision

    @property
    def clock(self) -> Clock:
        return self._clock

    @property
    def status(self) -> _SessionStatus:
        return self._status

    @status.setter
    def status(self, status) -> None:
        self._status = status

    @property
    def time(self) -> _SessionTime:
        return self._time

    def start(self) -> None:
        if not self.status.is_not_started:
            raise SessionException("Session was already started.", self.status.current)
        self.start_time = self.clock()

        self.status = self.status.add.running

    def pause(self, reason: str = "manual") -> None:
        if not self.status.is_running:
            raise SessionException("Can only pause a running session.", self.status.current)
        self._pause_start = self.clock()

        self.pauses.append({
            "reason": reason,
            "start_wall_time": time.time(),
            "start_perf": self._pause_start,
            "end_perf": None,
            "duration": 0.0
        })

        self.status = self.status.add.paused

    def idle(self) -> None:
        if not self.status.is_running:
            raise SessionException("Can only declare idle on a running session.", self.status.current)
        self._idle_start = self.clock()

        self.idles.append({
            "start_wall_time": time.time(),
            "start_perf": self._idle_start,
            "end_perf": None,
            "duration": 0.0
        })

        self.status = self.status.add.idle

    def resume(self) -> None:
        if self.status.current not in (SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Can only resume a paused or idle session.", self.status.current)
        
        now = self.clock()

        if self.status.is_paused:
            last_pause = self.pauses[-1]
            last_pause["end_perf"] = now
            last_pause["duration"] = now - self._pause_start
            
            self._pause_start = None
        else:
            last_idle = self.idles[-1]
            last_idle["end_perf"] = now
            last_idle["duration"] = now - self._idle_start
            
            self._idle_start = None

        self.status = self.status.add.running



    def split(self, label: str = "", split_type: str = "active") -> float:
        if self.status.current not in (SessionStatus.RUNNING, SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Cannot split on an inactive session.", self.status.current)

        split_types = {
            "active": self.time.active,
            "elapsed": self.time.total
        }

        if split_type not in split_types:
            raise SessionException(f"Invalid split type. Value split types: {', '.join(split_types)}.", self.status.current)

        current_elapsed = split_types.get(split_type)
        self.splits.append({
            "label": label or f"Split {len(self.splits) + 1}",
            "total_time": current_elapsed,
            "timestamp": time.time(),
            "time_perf": self.clock()
        })
        return current_elapsed

    def end(self) -> None:
        if self.status.is_not_started:
            raise SessionException("Cannot end a session that has not started.", self.status.current)
        if self.status.is_ended:
            raise SessionException("Session already ended.", self.status.current)

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
        self.status = self.status.add.ended

    def to_dict(self) -> dict:
        return {
            "status": self.status.current,
            "total_total_time": self.time.total,
            "total_total_time_active": self.time.active,
            "splits": self.splits,
            "has_splits": len(self.splits) > 0
        }

    @staticmethod
    def _sum_time_list(list: list, status_start_time: float | None, current_time: float | None) -> float:
        total_time = sum([i["duration"] for i in list])
        
        if status_start_time is not None:
            total_time += current_time - status_start_time

        return total_time
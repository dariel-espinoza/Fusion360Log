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

class FormatableFloat(float):
    def format(self, precision: int) -> float:
        return round(max(0.0, self), precision)

@dataclass(frozen=True, slots=True)
class Clock:
    monotonic: Callable[[], float] = time.perf_counter
    wall: Optional[Callable[[], float]] = time.time

    def __call__(self) -> FormatableFloat:
        return FormatableFloat(self.monotonic())

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
    history: list[SessionStatus] = field(default_factory=list)

    def __call__(self) -> Optional[SessionStatus]:
        return self.current

    def __str__(self) -> str:
        return f'Current: {self.current}\nPrevious: {self.previous}'

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
            return replace(ss_instance or self.ss_instance, history=new_history)

        def _append(self, status: SessionStatus) -> list[SessionStatus]:
            self.history.append(status)
            return self.history

@dataclass(slots=True)
class _SessionTime:
    clock: Clock
    preicsion: int
    _history: Intervals
    _actives: Intervals
    _pauses: Intervals
    _idles: Intervals
    _splits: Splits

    def __call__(self) -> Optional[Intervals.Interval]:
        return self.current

    def __str__(self) -> str:
        return f'Current: {self.current}\nPrevious: {self.previous}'

    @property
    def clock(self) -> Clock:
        return self.clock

    @property
    def complete(self) -> Intervals: return self._history
    @property
    def actives(self) -> Intervals: return self._actives
    @property
    def pauses(self) -> Intervals: return self._pauses
    @property
    def idles(self) -> Intervals: return self._pauses
    @property
    def splits(self) -> Splits: return self._splits
    
    @property
    def current(self) -> Optional[Intervals.Interval]:
        return self.complete.current

    @property
    def previous(self) -> Optional[Intervals.Interval]:
        return self.complete.previous

    @property
    def add(self) -> _AppendHistory:
        return self._AppendHistory(th_instance=self)

    @classmethod
    def new(cls, clock: Clock, precision: int) -> _SessionTime:
        return cls(
            clock=clock,
            precision=precision,
            _history=cls.Intervals.new(clock=clock),
            _actives=cls.Intervals.new(clock=clock),
            _pauses=cls.Intervals.new(clock=clock),
            _idles=cls.Intervals.new(clock=clock),
            _splits=cls.Splits.new(clock=clock)
            )

    @dataclass(slots=True)
    class Intervals:
        clock: Clock
        history: list[Interval]

        def __call__(self) -> Optional[Interval]:
            return self.current

        def __str__(self) -> str:
            return f'Current: {self.current}\nPrevious: {self.previous}'

        @property
        def start(self) -> Optional[Interval.Stamp]:
            return self.history[0].start if self.history else None

        @property
        def end(self) -> Optional[Interval.Stamp]:
            return self.history[-1].end if self.history else None

        @property
        def current(self) -> Optional[Interval]:
            return self.history[-1] if self.history else None

        @property
        def previous(self) -> Optional[Interval]:
            return self.history[-2] if len(self.history) >= 2 else None

        @property
        def duration(self) -> FormatableFloat:
            return FormatableFloat(sum([interval.duration for interval in self.history]))

        @classmethod
        def new(cls, clock: Clock) -> Self:
            return cls(clock=clock, history=[])

        @dataclass(slots=True)
        class Interval:
            clock: Clock
            start: Stamp
            end: Stamp
            reason: Optional[str] = field(default=None)

            def __call__(self) -> Stamp:
                return self.start if self.end.monotonic is None else self.end

            def __str__(self) -> str:
                return f'''
                Start:\n
                Monotonic: {self.start.monotonic}\n
                Wall: {self.start.wall}\n\n
                End:\n
                Monotonic: {self.end.monotonic}\n
                Wall: {self.end.wall}'''

            @property
            def duration(self) -> FormatableFloat:
                if self.start.monotonic:
                    return FormatableFloat((self.end.monotonic() or self.clock.monotonic()) - self.start.monotonic)
                return 0.0

            def stop(self, clock: Clock) -> Self:
                self.end.now(clock=clock)
                return self

            @classmethod
            def now(cls, clock: Clock) -> Self:
                return cls(clock=clock, start=cls.Stamp().now(clock=clock), end=cls.Stamp())

            @classmethod
            def _add(
                    cls, 
                    history: list[Self], 
                    clock: Clock, 
                    start: Optional[Stamp] = None, 
                    end: Optional[Stamp] = None, 
                    reason: Optional[str] = None
                ) -> list[Self]:
                    history.append(
                        cls(
                            clock=clock,
                            start=start or cls.Stamp().now(clock=clock),
                            end=end or cls.Stamp(),
                            reason=reason
                        )
                    )
                    return history

            @dataclass(slots=True)
            class Stamp:
                monotonic: Optional[FormatableFloat] = field(default=None)
                wall: Optional[FormatableFloat] = field(default=None)

                def __post_init__(self) -> None:
                    self.monotonic = FormatableFloat(self.monotonic)
                    self.wall = FormatableFloat(self.wall)

                def __call__(self) -> Optional[FormatableFloat]:
                    return self.monotonic

                def __str__(self) -> str:
                    return f'Monotonic: {self.monotonic}\nWall: {self.wall}'

                def now(self, clock: Clock) -> Self:
                    self.monotonic, self.wall = clock.now()
                    return self

    @dataclass(slots=True)
    class Splits:
        clock: Clock
        history: list[Split]

        def __call__(self) -> Optional[Split]:
            return self.recent

        def __str__(self) -> str:
            return f'Recent: {self.recent}\nPrevious: {self.previous}'

        @property
        def recent(self) -> Optional[Split]:
            return self.history[-1] if self.history else None

        @property
        def previous(self) -> Optional[Split]:
            return self.history[-2] if len(self.history) >= 2 else None

        @classmethod
        def new(cls, clock: Clock) -> Self:
            return cls(clock=clock, history=[])

        @dataclass(slots=True)
        class Split:
            label: str
            monotonic: FormatableFloat
            wall: Optional[FormatableFloat] = None
            reason: Optional[str] = None

            def __call__(self):
                return self.monotonic

            def __str__(self):
                return f'Monotonic: {self.monotonic}\nWall: {self.wall}\nReason: {self.reason}'

            @classmethod
            def now(cls, clock: Clock, reason: Optional[str] = None) -> Self:
                return cls(
                    monotonic=clock.monotonic(),
                    wall=clock.wall() if clock.wall else None,
                    reason=reason
                )

            @classmethod
            def _add(
                cls, 
                history: list[Self],
                label: str,
                monotonic: FormatableFloat,
                wall: Optional[FormatableFloat],
                reason: Optional[str]
                ) -> list[Self]:
                history.append(cls(
                    label=label,
                    monotonic=monotonic,
                    wall=wall,
                    reason=reason
                    )
                )
                return history

    @dataclass(slots=True)
    class _AppendHistory:
        th_instance: _SessionTime

        def active(self, clock: Optional[Clock] = None) -> _SessionTime:
            actives = self.th_instance.actives.Interval._add(
                    history=self.th_instance.actives.history,
                    clock=clock or self.th_instance.clock.monotonic,
                    reason="activity"
                )
            return self._append(actives)
        
        def pause(self, reason: str, clock: Optional[Clock] = None) -> _SessionTime:
            pauses = self.th_instance.pauses.Interval._add(
                    history=self.th_instance.pauses.history,
                    clock=clock or self.th_instance.clock.monotonic,
                    reason=reason
                )
            return self._append(pauses)

        def idle(self, clock: Optional[Clock] = None) -> _SessionTime:
            idles = self.th_instance.idles.Interval._add(
                    history=self.th_instance.idles.history,
                    clock=clock or self.th_instance.clock.monotonic,
                    reason="inactivity"
                )
            return self._append(idles)

        def split(self, label: str = "", clock: Optional[Clock] = None) -> list[Self]:
            splits = self.th_instance.splits.history.append(
                self.th_instance.splits.Split._add(
                    history=self.th_instance.splits.history,
                    label=label,
                    monotonic=clock or self.th_instance.clock.monotonic,
                    wall=self.th_instance.clock.wall,
                    reason="manual"
                )
            )
            return self._append(splits)

        def _append(self, intervals: list[_SessionTime.Intervals.Interval]) -> _SessionTime:
            self.th_instance.complete.history.append(intervals[-1])
            return self.th_instance


class Session:
    """ Generic, testable base class for tracking time and states. """

    def __init__(
            self, 
            precision: int = 2,
            mono_clock: Callable[[], float | int] = time.perf_counter,
            wall_clock: Optional[Callable[[], float | int]] = time.time 
        ) -> None:

        clock: Clock = Clock(monotonic=mono_clock, wall=wall_clock)
        self._time: _SessionTime = _SessionTime.new(clock=clock, precision=precision)
        self._status: _SessionStatus = _SessionStatus().add.not_started

    def __str__(self):
        return f"Status: {self.status.current}\nTime Elapsed: {self.time.complete.duration}"

    def __repr__(self):
        return f"{self.__class__.__name__}(precision={self.precision!r})"

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

        self.time.add.active()
        self.status = self.status.add.running

    def pause(self, reason: str = "manual") -> None:
        if not self.status.is_running:
            raise SessionException("Can only pause a running session.", self.status.current)

        self.time.add.pause(reason=reason)
        self.status = self.status.add.paused

    def idle(self) -> None:
        if not self.status.is_running:
            raise SessionException("Can only declare idle on a running session.", self.status.current)
        
        self.time.add.idle()
        self.status = self.status.add.idle

    def resume(self) -> None:
        if self.status.current not in (SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Can only resume a paused or idle session.", self.status.current)
        
        self.time.current.stop(clock=self.time.clock)
        self.time.add.active()
        self.status = self.status.add.running

    def split(self, label: str = "") -> FormatableFloat:
        if self.status.current not in (SessionStatus.RUNNING, SessionStatus.PAUSED, SessionStatus.IDLE):
            raise SessionException("Cannot split on an inactive session.", self.status.current)

        self.time.add.split(label=label)
        return self.time.splits.recent.monotonic

    def end(self) -> None:
        if self.status.is_not_started:
            raise SessionException("Cannot end a session that has not started.", self.status.current)
        if self.status.is_ended:
            raise SessionException("Session already ended.", self.status.current)

        self.time.current.end.now()
        self.status = self.status.add.ended

    def to_dict(self) -> dict:
        return {
            "status": self.status.current,
            "total_total_time": self.time.complete.duration,
            "total_total_time_active": self.time.actives.duration,
            "splits": self.time.splits.history,
            "has_splits": len(self.time.splits.history) > 0
        }
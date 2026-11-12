import pytest
from dataclasses import dataclass
from Fusion360Log.logger.session import Session, SessionStatus, SessionException

INVALID_ACTIONS: dict[SessionStatus, list[str]] = {
    SessionStatus.NOT_STARTED: ["pause", "idle", "resume", "split", "end"],
    SessionStatus.RUNNING: ["start", "resume"],
    SessionStatus.PAUSED: ["start","pause", "idle"],
    SessionStatus.IDLE: ["start","pause", "idle"],
    SessionStatus.ENDED: ["start", "pause", "idle", "resume", "split", "end"]
}

INVALID_STATE_ACTION_PAIRS: list[tuple[SessionStatus, str]] = [
    (state, action) 
    for state, action_list in INVALID_ACTIONS.items()
    for action in action_list
]

class MockTime:
    def __init__(self, start_time: float | int = 100):
        self._time = start_time

    def time(self) -> float | int:
        return self._time

    def advance(self, value: float | int = 1) -> None:
        if value < 0:
            raise ValueError("Cannot advance in negative time.")
        self._time += value

@dataclass
class MockSession:
    session: Session
    clock: MockTime

    @classmethod
    def create(cls, start_time: float | int = 100) -> MockSession:
        clock = MockTime(start_time)
        return cls(clock=clock, session=Session(clock=clock.time))

    @staticmethod
    def _set_state(instance: MockSession, state: SessionStatus) -> MockTime:
        if state == SessionStatus.NOT_STARTED:
            return instance
        
        instance.session.start()    

        match state:
            case SessionStatus.RUNNING:
                pass
            case SessionStatus.PAUSED:
                instance.session.pause()
            case SessionStatus.IDLE:
                instance.session.idle()
            case SessionStatus.ENDED:
                instance.session.end()
        return instance


@pytest.fixture
def mock_session() -> MockSession:
    return MockSession.create()

def test_initial_state(mock_session):
    assert mock_session.session.status == SessionStatus.NOT_STARTED
    assert mock_session.session.total_time == 0.0
    assert mock_session.session.total_time_paused == 0.0
    assert mock_session.session.total_time_idle == 0.0
    assert mock_session.session.total_time_active == 0.0

@pytest.mark.parametrize("state, action", INVALID_STATE_ACTION_PAIRS)
def test_invalid_actions(mock_session, state, action):
    MockSession._set_state(mock_session, state=state)

    with pytest.raises(SessionException) as exc_info:
        getattr(mock_session.session, action)()

    assert exc_info.value.state == state
    assert mock_session.session.status == state




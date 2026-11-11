import pytest
from dataclasses import dataclass
from Fusion360Log.logger.session import Session, SessionStatus, SessionException

actions: dict[SessionStatus, list] = {
    SessionStatus.NOT_STARTED: ["pause", "idle", "resume", "split", "end"],
    SessionStatus.RUNNING: ["start", "resume"],
    SessionStatus.PAUSED: ["start","pause", "idle"],
    SessionStatus.IDLE: ["start","pause", "idle"],
    SessionStatus.ENDED: ["start", "pause", "idle", "resume", "split", "end"]
}

state_action_pairs: list[tuple[SessionStatus, str]] = [
    (state, action) 
    for state, action_list in actions.items()
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

    def __post_init__(self):
        self.session._clock = self.clock.time

@pytest.fixture
def mock_session() -> MockSession:
    return MockSession(Session(), MockTime())

@pytest.fixture
def configured_mock_session(mock_session, state) -> MockSession:
    if state != SessionStatus.NOT_STARTED:
        mock_session.session.start()
        if state != SessionStatus.RUNNING:
            if state == SessionStatus.PAUSED:
                mock_session.session.pause()
            if state == SessionStatus.IDLE:
                mock_session.session.idle()
            if state == SessionStatus.ENDED:
                mock_session.session.end()
    return mock_session

def test_initial_state(mock_session):
    assert mock_session.session.status == SessionStatus.NOT_STARTED
    assert mock_session.session.total_time == 0.0
    assert mock_session.session.total_time_paused == 0.0
    assert mock_session.session.total_time_idle == 0.0
    assert mock_session.session.total_time_active == 0.0

@pytest.mark.parametrize("state, action", state_action_pairs)
def test_invalid_actions(configured_mock_session, state, action):

    with pytest.raises(SessionException) as exc_info:
        getattr(configured_mock_session.session, action)()

    assert exc_info.value.state == state




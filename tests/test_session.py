import pytest
from Fusion360Log.logger.session import Session, SessionStatus, SessionException

class MockTime():
    def __init__(self, start_time: float | int = 100):
        self._time = start_time

    @property
    def time(self) -> float | int:
        return self._time

    def advance(self, value: float | int = 1) -> None:
        if value < 0:
            raise ValueError("Cannot advance in negative time.")
        self._time += value

@pytest.fixture
def session():
    return Session()

def test_initial_state(session):
    assert session.status == SessionStatus.NOT_STARTED
    assert session.total_time == 0.0
    assert session.total_time_paused == 0.0
    assert session.total_time_idle == 0.0
    assert session.total_time_active == 0.0
    
@pytest.mark.parametrize(
        "action", [
            "pause",
            "idle",
            "resume",
            "split",
            "end"
        ])
def test_initial_invalid_actions(session, action):
    with pytest.raises(SessionException) as exc_info:
        getattr(session, action)()

    assert exc_info.value.state == SessionStatus.NOT_STARTED


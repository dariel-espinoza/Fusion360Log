import pytest
from Fusion360Log.logger.session import Session, SessionStatus, SessionException

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

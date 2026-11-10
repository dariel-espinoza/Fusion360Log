import pytest
from ..Fusion360Log.logger.session import Session, SessionStatus, SessionException

def test_initial_state():
    session = Session()

    assert session.status == SessionStatus.NOT_STARTED
    assert session.total_time == 0.0
    assert session.total_time_paused == 0.0
    assert session.total_time_idle == 0.0
    assert session.total_time_active == 0.0

    with pytest.raises(SessionException):
        session.pause()
        session.idle()
        session.resume()
        session.split()
        session.end()

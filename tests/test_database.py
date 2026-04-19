from backend.services import db_service


def test_db_init():
    db_service.init_db_if_missing()
    assert True

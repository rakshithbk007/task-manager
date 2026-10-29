import os

# Must happen BEFORE importing app, so the tests use the test database.
# (load_dotenv() does not override variables that are already set.)
os.environ["DB_NAME"] = "taskdb_test"

import pytest

import app as app_module

# Safety check: refuse to run if we are not connected to a test database
with app_module.app.app_context():
    assert app_module.db.engine.url.database.endswith("_test")


@pytest.fixture(autouse=True)
def clean_db():
    """Empty the tables before every test so tests don't affect each other."""
    with app_module.app.app_context():
        app_module.db.session.execute(app_module.db.delete(app_module.Task))
        app_module.db.session.execute(app_module.db.delete(app_module.User))
        app_module.db.session.commit()
    yield


@pytest.fixture
def client():
    """A fake browser. It keeps cookies, so login works between requests."""
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


@pytest.fixture
def other_client():
    """A second fake browser, for a second user."""
    return app_module.app.test_client()
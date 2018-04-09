import pytest
from flask import Flask

from api_utils.flask import Swagger


@pytest.fixture(scope='function')
def app():
    app = Flask(__name__)

    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "TEST-SECRET"

    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def swagger(app):
    yield Swagger(app)

import pytest
from flask import Flask
from pytest_mock import MockFixture

from apistrap.flask import Swagger
from apistrap.aiohttp import AioHTTPApistrap


@pytest.fixture(scope='function')
def app():
    app = Flask(__name__)
    app.testing = True
    app.debug = True

    app.config["SECRET_KEY"] = "TEST-SECRET"

    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def swagger(app):
    yield Swagger(app)


@pytest.fixture()
def aiohttp_apistrap():
    yield AioHTTPApistrap()


@pytest.fixture(scope='function')
def propagate_exceptions(app, mocker: MockFixture):
    def reraise(e):
        raise e

    handle = mocker.patch.object(app, "handle_user_exception", autospec=True)
    handle.side_effect = reraise


@pytest.fixture(scope='function')
def app_in_production(app):
    app.debug = False
    app.testing = False

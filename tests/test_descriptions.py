import pytest

from apistrap.flask import FlaskApistrap


def test_title_in_spec_json(app, client):
    oapi = FlaskApistrap()
    oapi.init_app(app)
    oapi.title = "A title"

    response = client.get("/spec.json")
    assert response.json["info"]["title"] == "A title"


def test_description_in_spec_json(app, client):
    oapi = FlaskApistrap()
    oapi.init_app(app)
    oapi.description = "A description"

    response = client.get("/spec.json")
    assert response.json["info"]["description"] == "A description"

import pytest
from apistrap.flask import FlaskApistrap


def test_title_in_swagger_json(app, client):
    swagger = FlaskApistrap()
    swagger.init_app(app)
    swagger.title = "A title"

    response = client.get("/swagger.json")
    assert response.json["info"]["title"] == "A title"


def test_description_in_swagger_json(app, client):
    swagger = FlaskApistrap()
    swagger.init_app(app)
    swagger.description = "A description"

    response = client.get("/swagger.json")
    assert response.json["info"]["description"] == "A description"

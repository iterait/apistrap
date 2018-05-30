import pytest
from apistrap.flask import Swagger


def test_title_in_swagger_json(app, client):
    swagger = Swagger(app)
    swagger.title = "A title"

    response = client.get("/swagger.json")
    assert response.json["info"]["title"] == "A title"


def test_description_in_swagger_json(app, client):
    swagger = Swagger(app)
    swagger.description = "A description"

    response = client.get("/swagger.json")
    assert response.json["info"]["description"] == "A description"

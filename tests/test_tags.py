import pytest
from flask import jsonify


@pytest.fixture()
def app_with_tags(app, flask_apistrap):
    @app.route("/", methods=["GET"])
    @flask_apistrap.tags("Hello", "World")
    def view():
        return jsonify()


def test_simple_tags(app_with_tags, client):
    response = client.get("/swagger.json")
    path = response.json["paths"]["/"]["get"]

    assert "tags" in path
    assert path["tags"] == ["Hello", "World"]


@pytest.fixture()
def app_with_repeated_tags(app, flask_apistrap):
    @app.route("/", methods=["GET"])
    @flask_apistrap.tags("Tag 1", "Tag 2")
    @flask_apistrap.tags("Tag 3", "Tag 4")
    def view():
        return jsonify()


def test_repeated_tags(app_with_repeated_tags, client):
    response = client.get("/swagger.json")
    path = response.json["paths"]["/"]["get"]

    assert "tags" in path
    assert sorted(path["tags"]) == ["Tag 1", "Tag 2", "Tag 3", "Tag 4"]

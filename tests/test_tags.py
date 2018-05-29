import pytest
from flask import jsonify


@pytest.fixture()
def app_with_tags(app, swagger):
    @app.route("/", methods=["GET"])
    @swagger.autodoc()
    @swagger.tags("Hello", "World")
    def view():
        return jsonify()


def test_simple_tags(app_with_tags, client):
    response = client.get("/swagger.json")
    path = response.json["paths"]["/"]["get"]

    assert "tags" in path
    assert path["tags"] == ["Hello", "World"]


@pytest.fixture()
def app_with_repeated_tags(app, swagger):
    @app.route("/", methods=["GET"])
    @swagger.autodoc()
    @swagger.tags("Tag 1", "Tag 2")
    @swagger.tags("Tag 3", "Tag 4")
    def view():
        return jsonify()


def test_repeated_tags(app_with_repeated_tags, client):
    response = client.get("/swagger.json")
    path = response.json["paths"]["/"]["get"]

    assert "tags" in path
    assert sorted(path["tags"]) == ["Tag 1", "Tag 2", "Tag 3", "Tag 4"]

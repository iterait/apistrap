import pytest
from flask import jsonify


@pytest.fixture()
def app_with_accepts_file(app, flask_apistrap):
    @app.route("/", methods=["POST"])
    @flask_apistrap.accepts_file()
    def view():
        return jsonify()

    @app.route("/image", methods=["POST"])
    @flask_apistrap.accepts_file(mime_type="image/png")
    def view_mimetype():
        return jsonify()


def test_accepts_file_spec(app_with_accepts_file, client):
    response = client.get("/spec.json")

    assert response.status_code == 200

    paths = response.json["paths"]

    assert paths["/"]["post"]["requestBody"]["content"] == {
        "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
    }

    assert paths["/image"]["post"]["requestBody"]["content"] == {
        "image/png": {"schema": {"type": "string", "format": "binary"}}
    }

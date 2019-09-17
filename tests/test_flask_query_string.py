import pytest
from flask import jsonify


@pytest.fixture(scope="function")
def app_with_qs_params(app, flask_apistrap):
    @app.route("/", methods=["get"])
    @flask_apistrap.accepts_qs("param_a", "param_b")
    def view(param_a: str, param_b: int = 999):
        """
        A cool view handler.
        :param param_a: Parameter A
        :param param_b: Parameter B
        """

        return jsonify({"a": param_a, "b": param_b})

    yield app


def test_flask_query_string_spec(app_with_qs_params, client):
    response = client.get("/spec.json")

    assert response.status_code == 200

    params = response.json["paths"]["/"]["get"]["parameters"]
    params.sort(key=lambda p: p["name"])

    assert len(params) == 2
    assert params[0] == {
        "name": "param_a",
        "in": "query",
        "description": "Parameter A",
        "required": True,
        "schema": {"type": "string"},
    }

    assert params[1] == {
        "name": "param_b",
        "in": "query",
        "description": "Parameter B",
        "required": False,
        "schema": {"type": "integer"},
    }


def test_flask_query_string_passing(app_with_qs_params, client):
    response = client.get("/?param_a=hello&param_b=42")

    assert response.status_code == 200

    assert response.json["a"] == "hello"
    assert response.json["b"] == 42


def test_flask_query_string_optional_params(app_with_qs_params, client):
    response = client.get("/?param_a=hello")

    assert response.status_code == 200

    assert response.json["a"] == "hello"
    assert response.json["b"] == 999

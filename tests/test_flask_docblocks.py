import pytest
from flask import jsonify


@pytest.fixture(scope="function")
def app_with_params_as_args(app, flask_apistrap):
    @app.route('/<param_a>/<param_b>', methods=["get"])
    def view(param_a: str, param_b: int):
        """
        A cool view handler.

        :param param_a: Parameter A
        :param param_b: Parameter B
        """

        return jsonify({
            "a": param_a,
            "b": param_b
        })

    yield app


def test_summary_from_docblock(app_with_params_as_args, client):
    response = client.get("/spec.json")

    assert response.status_code == 200
    path = response.json["paths"]["/{param_a}/{param_b}"]["get"]

    assert path["summary"] == "A cool view handler."


def test_parameters_from_docblock(app_with_params_as_args, client):
    response = client.get("/spec.json")

    assert response.status_code == 200
    path = response.json["paths"]["/{param_a}/{param_b}"]["get"]

    param_a = next(filter(lambda p: p["name"] == "param_a", path["parameters"]), None)
    param_b = next(filter(lambda p: p["name"] == "param_b", path["parameters"]), None)

    assert param_a["description"] == "Parameter A"
    assert param_b["description"] == "Parameter B"

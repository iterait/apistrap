import pytest
from flask import jsonify
from schematics import Model


class Request(Model):
    """
    Request body
    """


class Response(Model):
    """
    Response body
    """


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

    @app.route('/extended', methods=["get"])
    def view_extended():
        """
        A summary.

        An extended description.
        """

    @app.route('/body', methods=["post"])
    def view_body(body: Request):
        """
        A summary.

        An extended description.

        :param body: Request body description
        """

    @app.route('/response', methods=["get"])
    def view_response() -> Response:
        """
        A summary.

        An extended description.

        :return: Response description
        """

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


def test_extended_description_from_docblock(app_with_params_as_args, client):
    response = client.get("/spec.json")

    assert response.status_code == 200
    path = response.json["paths"]["/extended"]["get"]

    assert path["summary"] == "A summary."
    assert path["description"] == "An extended description."


def test_request_body_description_from_docblock(app_with_params_as_args, client):
    response = client.get("/spec.json")

    assert response.status_code == 200
    path = response.json["paths"]["/body"]["post"]

    assert path["requestBody"]["description"] == "Request body description"


def test_response_description_from_docblock(app_with_params_as_args, client):
    response = client.get("/spec.json")

    assert response.status_code == 200
    path = response.json["paths"]["/response"]["get"]

    assert path["responses"]["200"]["description"] == "Response description"

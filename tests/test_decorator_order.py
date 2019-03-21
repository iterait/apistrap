import itertools

import pytest
from flask import jsonify
from schematics import Model
from schematics.types import StringType


class Request(Model):
    message = StringType()


class Response(Model):
    message = StringType()


decorators = [
    lambda oapi: oapi.responds_with(Response, code=201),
    lambda oapi: oapi.accepts(Request),
    lambda oapi: oapi.tags("Tag 1", "Tag 2")
]


@pytest.fixture(params=list(itertools.permutations(decorators)))
def decorated_app(app, flask_apistrap, request):
    """
    An app fixture parametrized with all possible orders of different kinds of Apistrap decorators
    """

    # Prepare a bare view function body
    def view(path_arg: str, request_arg: Request):
        return jsonify()

    # Apply our permutation of decorators
    for decorator in request.param:
        view = decorator(flask_apistrap)(view)

    # Register the view function with our Flask app
    app.route("/<path_arg>")(view)


def test_decorator_order(decorated_app, client):
    response = client.get("/spec.json")
    path = response.json["paths"]["/{path_arg}"]["get"]

    assert len(path["parameters"]) == 1
    assert path["parameters"][0]["in"] == "path"

    assert path["requestBody"] is not None

    assert "201" in path["responses"]

    assert len(path["tags"]) == 2

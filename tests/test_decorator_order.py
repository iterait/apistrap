import pytest
import itertools

from flask import jsonify
from schematics import Model
from schematics.types import StringType


class Request(Model):
    message = StringType()


class Response(Model):
    message = StringType()


decorators = [
    lambda swagger: swagger.responds_with(Response, code=201),
    lambda swagger: swagger.accepts(Request),
    lambda swagger: swagger.tags("Tag 1", "Tag 2")
]


@pytest.fixture(params=list(itertools.permutations(decorators)))
def decorated_app(app, swagger, request):
    """
    An app fixture parametrized with all possible orders of different kinds of swagger decorators
    """

    # Prepare a bare view function body
    def view(path_arg: str, request_arg: Request):
        return jsonify()

    # Apply our permutation of decorators
    for decorator in request.param:
        view = decorator(swagger)(view)

    # Add the autodoc decorator and register the view function with our Flask app
    view = swagger.autodoc()(view)
    app.route("/<path_arg>")(view)


def test_decorator_order(decorated_app, client):
    response = client.get("/swagger.json")
    path = response.json["paths"]["/{path_arg}"]["get"]

    assert len(path["parameters"]) == 2
    assert next(filter(lambda param: param["in"] == "body", path["parameters"]), None) is not None
    assert next(filter(lambda param: param["in"] == "path", path["parameters"]), None) is not None

    assert "201" in path["responses"]

    assert len(path["tags"]) == 2

from __future__ import annotations

from typing import List

import pytest
from flask import jsonify
from pydantic import BaseModel

from apistrap.examples import ExamplesMixin, ModelExample
from apistrap.flask import FlaskApistrap


class ModelWithExamples(BaseModel, ExamplesMixin):
    string: str
    int: int

    @classmethod
    def get_examples(cls) -> List[ModelExample[ModelWithExamples]]:
        return [
            ModelExample(
                "a", cls(**{"string": "Lorem Ipsum", "int": 42}), summary="Summary", description="Description"
            ),
            ModelExample("b", cls(**{"string": "Dolor Sit Amet", "int": 999})),
        ]


@pytest.fixture(scope="function")
def app_with_examples(app):
    oapi = FlaskApistrap()
    oapi.init_app(app)

    @app.route("/view", methods=["GET"])
    @oapi.accepts(ModelWithExamples)
    @oapi.responds_with(ModelWithExamples)
    def view(body: ModelWithExamples):
        return jsonify()


def test_examples(client, app_with_examples):
    response = client.get("/spec.json")
    assert response.status_code == 200

    expected = {
        "a": {"summary": "Summary", "description": "Description", "value": {"string": "Lorem Ipsum", "int": 42}},
        "b": {"value": {"string": "Dolor Sit Amet", "int": 999}},
    }
    assert response.json["paths"]["/view"]["get"]["requestBody"]["content"]["application/json"]["examples"] == expected
    assert (
        response.json["paths"]["/view"]["get"]["responses"]["200"]["content"]["application/json"]["examples"]
        == expected
    )

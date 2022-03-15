from enum import Enum
from typing import List

import pytest
from aiohttp import web
from pydantic import BaseModel


class InnerModel(BaseModel):
    field: int


class ModelWithReuse(BaseModel):
    model_field: InnerModel
    model_list_field: List[InnerModel]


class ExampleEnum(Enum):
    choice_a = "choice_a"
    choice_b = "choice_b"


class NestedModelWithEnums(BaseModel):
    enum_field: ExampleEnum


class ModelWithEnums(BaseModel):
    enum_field: ExampleEnum
    nested_field: NestedModelWithEnums


@pytest.fixture
async def app_with_model_reuse(aiohttp_apistrap):
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/")
    async def view(req: ModelWithReuse):
        return None

    @routes.post("/enum")
    async def view_enum(req: ModelWithEnums):
        return None

    app.add_routes(routes)
    aiohttp_apistrap.init_app(app)
    yield app


async def test_spec_with_model_reuse(app_with_model_reuse, aiohttp_initialized_client):
    client = await aiohttp_initialized_client(app_with_model_reuse)
    response = await client.get("/spec.json")
    json = await response.json()

    assert json["components"]["schemas"]["ModelWithReuse"]["type"] == "object"
    assert json["components"]["schemas"]["ModelWithEnums"]["type"] == "object"

    assert json["components"]["schemas"]["ModelWithReuse"]["properties"]["model_field"] == {
        "$ref": "#/components/schemas/InnerModel"
    }

    assert json["paths"]["/"]["post"]["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ModelWithReuse"
    }

    assert json["paths"]["/enum"]["post"]["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ModelWithEnums"
    }

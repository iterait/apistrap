from apistrap.flask import FlaskApistrap
from apistrap.tags import TagData


def test_tag_data(client, app):
    oapi = FlaskApistrap()
    oapi.add_tag_data(TagData("Tag"))
    oapi.add_tag_data(TagData("Tag with description", "Description"))
    oapi.init_app(app)

    response = client.get("/spec.json")

    assert len(response.json["tags"]) == 2

    assert response.json["tags"][0] == {
        "name": "Tag"
    }

    assert response.json["tags"][1] == {
        "name": "Tag with description",
        "description": "Description"
    }

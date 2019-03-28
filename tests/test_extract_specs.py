import pytest
from flask import jsonify

from apistrap.flask import FlaskApistrap


def test_spec_url_repeated_call(app, client):
    oapi = FlaskApistrap()

    oapi.spec_url = "/myspecurl.json"
    assert oapi.spec_url == "/myspecurl.json"

    oapi.init_app(app)

    @app.route("/")
    def view():
        return jsonify()

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert 'paths' in response.json
    assert '/' in response.json['paths']

    response = client.get("/myspecurl.json")
    assert response.status_code == 200
    assert 'paths' in response.json
    assert '/' in response.json['paths']


def test_spec_url_ignore_params(app, client):
    oapi = FlaskApistrap()
    oapi.init_app(app)

    @app.route('/view/<param>')
    @oapi.ignore_params('param')
    def view(param):
        return jsonify()

    response = client.get('/spec.json')
    assert response.status_code == 200
    assert 'paths' in response.json
    assert response.json['paths']['/view/{param}']['get']['parameters'] == []


def test_spec_url_ignore_endpoint(app, client):
    oapi = FlaskApistrap()
    oapi.init_app(app)

    @app.route('/')
    @oapi.ignore()
    def view():
        return jsonify()

    response = client.get('/spec.json')
    assert response.status_code == 200
    assert 'paths' in response.json
    assert '/' not in response.json['paths']

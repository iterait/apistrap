# Cognexa HTTP API utilities

[![Development Status](https://img.shields.io/badge/status-CX%20Regular-brightgreen.svg?style=flat)]()
[![Master Developer](https://img.shields.io/badge/master-Jan%20Buchar-lightgrey.svg?style=flat)]()

This package contains utilities that take care of most of the tedious tasks in the implementation of an HTTP API with 
Flask:

- request body validation
- response serialization and validation
- API documentation generation using OpenAPI v2 specifications

## Usage

First, you need to initialize the extension and bind it to your Flask app.

```python
from flask import Flask
from api_utils import Swagger
app = Flask(__name__)
swagger = Swagger(app)
swagger.title = "Some title for your API"
swagger.description = "A description of the API"
```

You will probably want to put this to a separate module so that you can import it in your blueprint files. In this case,
you can omit the `app` argument and call `Swagger.init_app(app)` later when you create the Flask app.

**Important**: A big part of the functionality is exposed using decorators on Flask view functions. Make sure that the 
Flask `route()` decorator is always the last applied one (the one on the top). Otherwise, the HTTP handler might not 
call some of our functions.

### Request Body Parsing

```python
from schematics import Model
from schematics.types import StringType
from flask import Flask, jsonify
from api_utils import Swagger

app = Flask(__name__)
swagger = Swagger(app)

class Request(Model):
    some_field = StringType(required=True)

@app.route("/<param>")
@swagger.autodoc()
@swagger.accepts(Request)
def view(param: str, request: Request):
    """
    A description of the endpoint
    """
    return jsonify({})
```

In this example, the request is automatically de-serialized from JSON, validated according to the Schematics model and 
passed to the view function in a parameter with a type annotation that matches that of the Schematics model. If the 
validation fails, error 400 is returned with a list of validation errors (the exact format is described in the API 
specification).

Note that the doc block will be parsed and used in the API specification as a description of the endpoint.

### Response Declaration and Validation

```python
from schematics import Model
from schematics.types import StringType
from flask import Flask
from api_utils import Swagger

app = Flask(__name__)
swagger = Swagger(app)

class MyResponse(Model):
    some_field = StringType(required=True)

class NotReadyResponse(Model):
    status = StringType(required=True)

@app.route("/")
@swagger.autodoc()
@swagger.responds_with(MyResponse, code=201)  # Code is optional
@swagger.responds_with(NotReadyResponse, code=202)
def view():
    return MyResponse(some_field="Some value")
```

In this example, the response format is inferred from the model and added to the specification. Also, the return values
from the view function are automatically validated and serialized to JSON. If an undeclared response type is returned,
an error (code 500) is returned.

### Working with the Specification File

You can obtain the OpenAPI specification through `http://yourapi.tld/apispec_1.json`. This file can be used by 
Swagger-related utilities.

The extension also serves the Swagger UI automatically. You can browse it on `http://yourapi.tld/apidocs`.

### Organizing Endpoints Using Tags

```python
from flask import Flask, jsonify
from api_utils import Swagger

app = Flask(__name__)
swagger = Swagger(app)
@app.route("/")
@swagger.autodoc()
@swagger.tags("Tag 1", "Tag 2")
def view():
    return jsonify({})
```

In this example, you can see how to organize the endpoints in Swagger UI into categories determined by tags.

## Running Tests

In a cloned repository, run `python setup.py test` after installing both regular and development requirements with 
`pip`.
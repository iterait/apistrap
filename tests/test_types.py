import pytest

import numpy as np
from schematics import Model
from schematics.exceptions import DataError
from schematics.types import IntType, ModelType, StringType, FloatType

from apistrap.types import TupleType, NonNanFloatType


class Inner(Model):
    s: str = StringType(required=True)
    i: int = IntType(required=True)


class SimpleTuple(Model):
    x: str = StringType(required=True)
    t: (str, str) = TupleType(StringType, 2)


class SimpleLargerTuple(Model):
    x: str = StringType(required=True)
    t: (str, str, str, str) = TupleType(StringType, 4, required=True)
    d: (float, float, float) = TupleType(FloatType, 3, required=True)


class ModelInTuple(Model):
    x: str = StringType(required=True)
    t: (Inner, Inner) = TupleType(ModelType(Inner), 2, required=True)


SIMPLE_OK_INPUTS = [
    {'x': 'hello', 't': ['dolly', 'how-are-you']},
]


@pytest.mark.parametrize('payload', SIMPLE_OK_INPUTS)
def test_simple_ok(payload):
    model = SimpleTuple(payload)
    model.validate()
    assert model.t == tuple(payload['t'])


@pytest.mark.parametrize('payload', SIMPLE_OK_INPUTS)
def test_simple_to_primitive(payload):
    model = SimpleTuple(payload)
    serialized = model.to_primitive()
    assert payload == serialized
    assert set(serialized.keys()) == {'x', 't'}


SIMPLE_WRONG_INPUTS = [
    {'x': 'hello', 't': 42},  # not a tuple
    {'x': 'hello', 't': {}},  # not a tuple
    {'x': 'hello', 't': [{}, ""]},  # first position (dict instead of string)
    {'x': 'hello', 't': ['dolly', 42.2]},  # second position (float instead of int)
    {'x': 'hello', 't': ['dolly', 'spam', 1]},  # too long
    {'x': 'hello', 't': ['dolly']},  # too short
]


@pytest.mark.parametrize('payload', SIMPLE_WRONG_INPUTS)
def test_simple_wrong(payload):
    with pytest.raises(DataError):
        model = SimpleTuple(payload)
        model.validate()


LARGER_OK_INPUTS = [
    {'x': 'hello', 't': ['dolly', 'spam', 'eggs', 'sausage'], 'd': [0.01, 0.2, 0.42]},
]


@pytest.mark.parametrize('payload', LARGER_OK_INPUTS)
def test_larger_ok(payload):
    model = SimpleLargerTuple(payload)
    model.validate()
    assert model.t == tuple(payload['t'])


@pytest.mark.parametrize('payload', LARGER_OK_INPUTS)
def test_larger_to_primitive(payload):
    model = SimpleLargerTuple(payload)
    serialized = model.to_primitive()
    assert payload == serialized
    assert set(serialized.keys()) == {'x', 't', 'd'}


LARGER_WRONG_INPUTS = [
    {'x': 'hello', 't': ['dolly', 42, True, [1, 2], [0]], 'd': [0.01, [0, 5]]},  # incorrect list type
    {'x': 'hello', 't': 0, 'd': [0.1, 0.2, 0.3]},  # second position (not a tuple)
    {'x': 'hello', 't': ['w', 'x', 'y', 'z'], 'd': {}},  # third position (not a tuple)
    {'x': 'hey', 't': ['dolly', 42, 'spam', 'eggs'], 'd': [0.01, 0.02, 0.03]},  # second position (int instead of str)
    {'x': 'hey', 't': ['dolly', 'spam', 'eggs', 'sausage', 'spam'], 'd': [0.01, 0.02, 0.03]},  # second position (too long)
    {'x': 'hey', 't': [0.01, 0.02, 0.03], 'd': ['dolly', 'spam', 'eggs', 'sausage']},  # reversed second and third
]


@pytest.mark.parametrize('payload', SIMPLE_WRONG_INPUTS)
def test_simple_wrong(payload):
    with pytest.raises(DataError):
        model = SimpleTuple(payload)
        model.validate()


MODELINTUPLE_OK_INPUTS = [
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, {'s': 'aa', 'i': 12}]},
]


@pytest.mark.parametrize('payload', MODELINTUPLE_OK_INPUTS)
def test_modelintuple_ok(payload):
    model = ModelInTuple(payload)
    model.validate()
    assert model.x == payload['x']
    assert set(model.t[0]) == set(payload['t'][0])
    assert model.t[1]["s"] == payload['t'][1]["s"]
    assert model.t[1]["i"] == payload['t'][1]["i"]


@pytest.mark.parametrize('payload', MODELINTUPLE_OK_INPUTS)
def test_modelintuple_to_primitive(payload):
    model = ModelInTuple(payload)
    serialized = model.to_primitive()
    assert payload == serialized
    assert set(serialized.keys()) == {'x', 't'}
    assert set(serialized['t'][0].keys()) == {'s', 'i'}


MODELINTUPLE_WRONG_INPUTS = [
    {'x': 'hello', 't': [[], {'s': 'aa', 'i': 12}]},  # first position (list instead of dict)
    {'x': 'hello', 't': [{'s': 'aa'}, {'s': 'aa', 'i': 12}]},  # first position (incomplete first position)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 'a'}, {'s': 'aa', 'i': 12}]},  # first position (string instead of int)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12, 'a': 'a'}, {'s': 'aa', 'i': 12}]},  # first position (too long)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, {'s': 'aa', 'i': "spam"}]},  # second position (str instead of int)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, {'s': 'aa', 'i': 12}, 42]},  # second position (too long)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, {'s': 'aa', 'i': 12}, {'s': 'aa', 'i': 12}]},  # second position (too long)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}]},  # second position (missing)
]


@pytest.mark.parametrize('payload', MODELINTUPLE_WRONG_INPUTS)
def test_modelintuple_wrong(payload):
    with pytest.raises(DataError):
        model = ModelInTuple(payload)
        model.validate()


def test_mock():
    tt = TupleType(IntType, 2, required=True).mock()
    assert len(tt) == 2
    assert isinstance(tt[0], int)
    assert isinstance(tt[1], int)


def test_repr():
    tt = TupleType(StringType, 4, required=True)
    assert tt._repr_info() == 'TupleType(StringType, 4)'


class NonNanModel(Model):
    x: float = NonNanFloatType(required=True)
    y: float = NonNanFloatType(required=True)


def test_nonnan_float():
    payload = {'x': 12.5, 'y': np.nan}
    model = NonNanModel(payload)
    model.validate()

    assert model.x == payload['x']
    assert model.y == 0.0

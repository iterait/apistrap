import pytest

from apistrap.types import TupleType

from schematics import Model
from schematics.exceptions import DataError
from schematics.types import IntType, ModelType, StringType, BooleanType, ListType, FloatType
from typing import List


class Inner(Model):
    s: str = StringType(required=True)
    i: int = IntType(required=True)


class SimpleTuple(Model):
    x: str = StringType(required=True)
    t: (str, int) = TupleType([StringType, IntType])


class SimpleLargerTuple(Model):
    x: str = StringType(required=True)
    t: (str, int, bool, List[int], List[int]) = \
        TupleType([StringType, IntType, BooleanType, ListType(IntType), ListType(IntType)], required=True)
    d: (float, List[str]) = TupleType([FloatType, ListType(StringType)], required=True)


class ModelInTuple(Model):
    x: str = StringType(required=True)
    t: (Inner, int) = TupleType([ModelType(Inner), IntType], required=True)


SIMPLE_OK_INPUTS = [
    {'x': 'hello', 't': ['dolly', 42]},
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
    {'x': 'hello', 't': [{}, 42.2]},  # first position (dict instead of string)
    {'x': 'hello', 't': ['dolly', 42.2]},  # second position (float instead of int)
    {'x': 'hello', 't': ['dolly', 42, 1]},  # too long
    {'x': 'hello', 't': [42, 'dolly']},  # reversed types
    {'x': 'hello', 't': ['dolly']},  # too short
]


@pytest.mark.parametrize('payload', SIMPLE_WRONG_INPUTS)
def test_simple_wrong(payload):
    with pytest.raises(DataError):
        model = SimpleTuple(payload)
        model.validate()


LARGER_OK_INPUTS = [
    {'x': 'hello', 't': ['dolly', 42, True, [1, 2], [0]], 'd': [0.01, ['x', 'y']]},
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
    {'x': 'hello', 't': 0, 'd': [0.01, ['x', 'y']]},  # second position (not a tuple)
    {'x': 'hello', 't': ['dolly', 42, True, [1, 2], [0]], 'd': {}},  # third position (not a tuple)
    {'x': 'hey', 't': ['dolly', 42, True, 0, [0]], 'd': [0.01, ['x', 'y']]},  # second position (int instead of list)
    {'x': 'hey', 't': ['dolly', 42, True, [1, 2], [0], 2], 'd': [0.01, ['x', 'y']]},  # second position (too long)
    {'x': 'hey', 't': [0.01, ['x', 'y']], 'd': ['dolly', 42, True, [1, 2], [0]]},  # reversed second and third
]


@pytest.mark.parametrize('payload', SIMPLE_WRONG_INPUTS)
def test_simple_wrong(payload):
    with pytest.raises(DataError):
        model = SimpleTuple(payload)
        model.validate()


MODELINTUPLE_OK_INPUTS = [
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, 42]},
]


@pytest.mark.parametrize('payload', MODELINTUPLE_OK_INPUTS)
def test_modelintuple_ok(payload):
    model = ModelInTuple(payload)
    model.validate()
    assert model.x == payload['x']
    assert set(model.t[0]) == set(payload['t'][0])
    assert model.t[1] == payload['t'][1]


@pytest.mark.parametrize('payload', MODELINTUPLE_OK_INPUTS)
def test_modelintuple_to_primitive(payload):
    model = ModelInTuple(payload)
    serialized = model.to_primitive()
    assert payload == serialized
    assert set(serialized.keys()) == {'x', 't'}
    assert set(serialized['t'][0].keys()) == {'s', 'i'}


MODELINTUPLE_WRONG_INPUTS = [
    {'x': 'hello', 't': [[], 42]},  # first position (list instead of dict)
    {'x': 'hello', 't': [{'s': 'aa'}, 42]},  # first position (incomplete first position)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 'a'}, 42]},  # first position (string instead of int)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12, 'a': 'a'}, 42]},  # first position (too long)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, 42.1]},  # second position (float instead of int)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}, 42, 5]},  # second position (too long)
    {'x': 'hello', 't': [{'s': 'aa', 'i': 12}]},  # second position (missing)
]


@pytest.mark.parametrize('payload', MODELINTUPLE_WRONG_INPUTS)
def test_modelintuple_wrong(payload):
    with pytest.raises(DataError):
        model = ModelInTuple(payload)
        model.validate()


def test_mock():
    tt = TupleType([ModelType(Inner), IntType], required=True).mock()
    assert len(tt) == 2
    assert isinstance(tt[0], Inner)
    assert isinstance(tt[1], int)


def test_repr():
    tt = TupleType([StringType, IntType], required=True)
    assert tt._repr_info() == 'TupleType(StringType, IntType)'

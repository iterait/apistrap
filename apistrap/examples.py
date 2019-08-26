from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from schematics import Model

T = TypeVar("T", bound=Model)


@dataclass
class ModelExample(Generic[T]):
    name: str
    value: T
    summary: Optional[str] = None
    description: Optional[str] = None


class ExamplesMixin:
    """
    A mixin that declares that the implementing schema class can supply example objects
    """

    @classmethod
    def get_examples(cls: __class__) -> List[ModelExample[__class__]]:
        """
        Get a collection of examples

        :return: a list of example objects of this class
        """

        # Using abc would lead to metaclass conflicts with Schematics
        raise NotImplementedError()  # pragma: no cover


def model_examples_to_openapi_dict(model: Type[ExamplesMixin]) -> Dict[str, Any]:
    """
    Take examples from a model and convert them to OpenAPI examples section.

    :param model: a model to extract
    :return: an OpenAPI examples section
    """

    examples = {}

    for example in model.get_examples():
        examples[example.name] = {"value": example.value.to_primitive()}

        if example.summary is not None:
            examples[example.name]["summary"] = example.summary

        if example.description is not None:
            examples[example.name]["description"] = example.description

    return examples

"""
Unit tests for pyeuropepmc.processing.extensions.pydantic_helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pyeuropepmc.processing.extensions.pydantic_helpers import (
    PydanticModelGenerator,
    dataclass_to_pydantic,
    has_pydantic,
)

pytestmark = pytest.mark.unit

pydantic_missing = not has_pydantic()

skip_no_pydantic = pytest.mark.skipif(pydantic_missing, reason="pydantic not installed")


@skip_no_pydantic
class TestHasPydantic:
    def test_returns_true(self) -> None:
        assert has_pydantic() is True


@skip_no_pydantic
class TestDataclassToPydanticBasic:
    def test_simple_dataclass_conversion(self) -> None:
        @dataclass
        class Article:
            title: str
            year: int

        Model = dataclass_to_pydantic(Article)
        instance = Model(title="Test", year=2024)
        assert instance.title == "Test"
        assert instance.year == 2024
        assert instance.model_dump() == {"title": "Test", "year": 2024}

    def test_default_model_name_matches_dataclass_name(self) -> None:
        @dataclass
        class Book:
            title: str

        Model = dataclass_to_pydantic(Book)
        assert Model.__name__ == "Book"

    def test_custom_model_name(self) -> None:
        @dataclass
        class Book:
            title: str

        Model = dataclass_to_pydantic(Book, model_name="CustomBook")
        assert Model.__name__ == "CustomBook"

    def test_field_with_default(self) -> None:
        @dataclass
        class Item:
            name: str
            count: int = 0

        Model = dataclass_to_pydantic(Item)
        instance = Model(name="Widget")
        assert instance.count == 0


@skip_no_pydantic
class TestDataclassToPydanticFiltering:
    def test_include_fields(self) -> None:
        @dataclass
        class Person:
            name: str
            age: int
            email: str

        Model = dataclass_to_pydantic(Person, include_fields=["name", "email"])
        fields = list(Model.model_fields.keys())
        assert "name" in fields
        assert "email" in fields
        assert "age" not in fields

    def test_exclude_fields(self) -> None:
        @dataclass
        class Person:
            name: str
            age: int
            email: str

        Model = dataclass_to_pydantic(Person, exclude_fields=["email"])
        fields = list(Model.model_fields.keys())
        assert "name" in fields
        assert "age" in fields
        assert "email" not in fields

    def test_include_and_exclude_combined(self) -> None:
        @dataclass
        class Person:
            name: str
            age: int
            email: str

        Model = dataclass_to_pydantic(
            Person, include_fields=["name", "age", "email"], exclude_fields=["age"]
        )
        fields = list(Model.model_fields.keys())
        assert "name" in fields
        assert "email" in fields
        assert "age" not in fields


@skip_no_pydantic
class TestDataclassToPydanticDefaultFactory:
    def test_default_factory_list_independent_instances(self) -> None:
        @dataclass
        class Config:
            tags: list[str] = field(default_factory=list)

        Model = dataclass_to_pydantic(Config)
        a = Model()
        b = Model()
        a.tags.append("x")
        assert a.tags == ["x"]
        assert b.tags == []

    def test_default_factory_dict_independent_instances(self) -> None:
        @dataclass
        class Config:
            options: dict[str, int] = field(default_factory=dict)

        Model = dataclass_to_pydantic(Config)
        a = Model()
        b = Model()
        a.options["key"] = 42
        assert a.options == {"key": 42}
        assert b.options == {}


@skip_no_pydantic
class TestDataclassToPydanticMetadata:
    def test_field_with_metadata(self) -> None:
        @dataclass
        class Doc:
            title: str = field(metadata={"description": "test"})

        Model = dataclass_to_pydantic(Doc)
        assert "title" in Model.model_fields
        assert Model.model_fields["title"].description == "test"


@skip_no_pydantic
class TestPydanticModelGeneratorInit:
    def test_init_success(self) -> None:
        gen = PydanticModelGenerator()
        assert gen is not None


@skip_no_pydantic
class TestPydanticModelGeneratorGenerateModel:
    def test_from_sample_data(self) -> None:
        sample = {
            "title": "Hello",
            "year": 2024,
            "tags": ["a", "b"],
            "meta": {"k": "v"},
        }
        Model = PydanticModelGenerator.generate_model("Article", sample_data=sample)
        instance = Model(**sample)
        assert instance.title == "Hello"
        assert instance.year == 2024
        assert instance.tags == ["a", "b"]
        assert instance.meta == {"k": "v"}

    def test_from_field_types_optional_defaults_true(self) -> None:
        types = {"id": int, "title": str}
        Model = PydanticModelGenerator.generate_model(
            "Item", field_types=types, optional_defaults=True
        )
        instance = Model()
        assert instance.id is None
        assert instance.title is None

    def test_from_field_types_optional_defaults_false(self) -> None:
        types = {"id": int, "title": str}
        Model = PydanticModelGenerator.generate_model(
            "Item", field_types=types, optional_defaults=False
        )
        instance = Model(id=1, title="X")
        assert instance.id == 1
        assert instance.title == "X"
        with pytest.raises(Exception):
            Model()

    def test_explicit_field_types_take_precedence(self) -> None:
        sample = {"id": "123"}
        types = {"id": int}
        Model = PydanticModelGenerator.generate_model(
            "Thing", sample_data=sample, field_types=types
        )
        fields = Model.model_fields
        assert fields["id"].annotation is int

    def test_from_sample_data_none_value_inferred_as_str(self) -> None:
        sample = {"missing": None}
        Model = PydanticModelGenerator.generate_model("Article", sample_data=sample)
        assert "missing" in Model.model_fields
        assert Model.model_fields["missing"].annotation is str
        instance = Model(missing="fallback")
        assert instance.missing == "fallback"

    def test_from_sample_data_empty_list(self) -> None:
        sample = {"items": []}
        Model = PydanticModelGenerator.generate_model("ListHolder", sample_data=sample)
        instance = Model(items=[])
        assert instance.items == []


@skip_no_pydantic
class TestPydanticModelGeneratorFromDataclass:
    def test_delegates_to_dataclass_to_pydantic(self) -> None:
        @dataclass
        class Sample:
            name: str
            value: int

        Model = PydanticModelGenerator.from_dataclass(Sample, model_name="FromDC")
        assert Model.__name__ == "FromDC"
        instance = Model(name="a", value=1)
        assert instance.model_dump() == {"name": "a", "value": 1}

    def test_from_dataclass_with_include_fields(self) -> None:
        @dataclass
        class Sample:
            a: str
            b: int

        Model = PydanticModelGenerator.from_dataclass(
            Sample, include_fields=["a"]
        )
        assert list(Model.model_fields.keys()) == ["a"]

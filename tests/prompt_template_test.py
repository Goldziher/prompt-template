from uuid import UUID

import pytest
from prompt_template import (
    InvalidTemplateKeysError,
    MissingTemplateValuesError,
    PromptTemplate,
    TemplateError,
    TemplateSerializationError,
)


def test_basic_variable_substitution() -> None:
    """Test basic variable substitution works."""
    template = PromptTemplate("Hello ${name}!")
    result = template.to_string(name="World")
    assert result == "Hello World!"


def test_multiple_variables() -> None:
    """Test handling multiple variables."""
    template = PromptTemplate("${greeting} ${name}! How is ${location}?")
    result = template.to_string(greeting="Hello", name="Alice", location="London")
    assert result == "Hello Alice! How is London?"


def test_json_with_variables() -> None:
    """Test template with JSON structure and variables."""
    template = PromptTemplate("""
    {
        "name": "${user_name}",
        "age": ${age},
        "city": "${city}"
    }
    """)

    result = template.to_string(user_name="John", age="30", city="New York")
    assert '"name": "John"' in result
    assert '"age": 30' in result
    assert '"city": "New York"' in result


def test_missing_variables() -> None:
    """Test error when variables are missing."""
    template = PromptTemplate("Hello ${name}!")
    with pytest.raises(MissingTemplateValuesError) as exc_info:
        template.to_string()
    assert "name" in str(exc_info.value)


def test_invalid_keys() -> None:
    """Test error when invalid keys are provided."""
    template = PromptTemplate("Hello ${name}!")
    with pytest.raises(InvalidTemplateKeysError) as exc_info:
        template.to_string(name="World", invalid_key="Value")
    assert "invalid_key" in str(exc_info.value)


def test_nested_braces() -> None:
    """Test handling of nested braces."""
    template = PromptTemplate("""
    {
        "query": {
            "name": "${name}",
            "nested": {
                "value": "${value}"
            }
        }
    }
    """)
    result = template.to_string(name="test", value="nested_value")
    assert '"name": "test"' in result
    assert '"value": "nested_value"' in result


def test_escaping() -> None:
    """Test escaping of special characters."""
    cases = [
        ('{"key": "$5.00"}', set()),  # Plain $ without braces
        ('{"key": "\\${not_var}"}', set()),  # Escaped ${
        ('{"key": "${var}"}', {"var"}),  # Normal variable
        ('{"key": "\\\\${var}"}', {"var"}),  # Escaped backslash
        ('{"key": "\\{not_var}"}', set()),  # Escaped brace
    ]

    for template_str, expected_vars in cases:
        template = PromptTemplate(template_str)
        assert template.variables == expected_vars


def test_template_validation_errors() -> None:
    """Test various template validation error cases."""
    error_cases = [
        ("Hello ${", "Unclosed variable declaration"),
        ("Hello }", "Unmatched closing brace"),
        ("${${name}}", "Nested variable declaration"),
        ("Hello ${}", "Empty variable name"),
        ("${123name}", "Invalid variable name"),
        ("${invalid@name}", "Invalid variable name"),
        ("{unclosed", "Unclosed brace"),
    ]

    for template_str, expected_error in error_cases:
        with pytest.raises(TemplateError) as exc_info:
            PromptTemplate(template_str)
        assert expected_error in str(exc_info.value)


def test_valid_variable_names() -> None:
    """Test valid variable name patterns."""
    valid_cases = [
        "${valid}",
        "${_valid}",
        "${valid123}",
        "${VALID_NAME}",
        "${camelCase}",
        "${snake_case}",
    ]

    for template_str in valid_cases:
        template = PromptTemplate(template_str)
        assert len(template.variables) == 1


def test_template_reuse() -> None:
    """Test template can be reused with different values."""
    template = PromptTemplate("Hello ${name}!")
    result1 = template.to_string(name="Alice")
    result2 = template.to_string(name="Bob")
    assert result1 == "Hello Alice!"
    assert result2 == "Hello Bob!"


def test_template_equality() -> None:
    """Test template equality comparison."""
    template1 = PromptTemplate("Hello ${name}!", "greeting")
    template2 = PromptTemplate("Hello ${name}!", "greeting")
    template3 = PromptTemplate("Hello ${name}!", "different")
    template4 = PromptTemplate("Different ${name}!", "greeting")

    assert template1 == template2
    assert template1 != template3
    assert template1 != template4
    assert template1 != "Hello ${name}!"


def test_value_serialization() -> None:
    """Test serialization of different value types."""
    from datetime import datetime, timezone
    from decimal import Decimal

    template = PromptTemplate("${a}, ${b}, ${c}, ${d}, ${e}, ${f}, ${g}, ${h}")
    test_datetime = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    test_uuid = UUID("550e8400-e29b-41d4-a716-446655440000")
    test_decimal = Decimal("45.67")
    test_bytes = b"Hello World"

    result = template.to_string(
        a=123,  # int
        b=[1, 2, 3],  # list
        c={"key": "value"},  # dict
        d=test_datetime,  # datetime
        e=test_decimal,  # Decimal
        f=test_uuid,  # UUID
        g=True,  # bool
        h=test_bytes,  # bytes
    )

    # Basic JSON types
    assert "123" in result
    assert "[1, 2, 3]" in result
    assert '{"key": "value"}' in result
    assert "true" in result  # JSON uses lowercase for booleans

    # Special types with custom serialization
    assert "2024-01-01T12:00:00+00:00" in result  # datetime in ISO format
    assert "45.67" in result  # Decimal as string
    assert "550e8400-e29b-41d4-a716-446655440000" in result  # UUID as string
    assert "Hello World" in result  # UTF-8 decoded bytes


def test_complex_template() -> None:
    complex_template = PromptTemplate(
        name="complex",
        template="""
    Your task is to evaluate output that was generated by an LLM following this prompt:
        <prompt>
        ${prompt}
        </prompt>


    This is the model output that should be evaluated:
        <model_output>
        ${model_output}
        </model_output>

    Evaluation Criteria:

    1. Relevance (0-100)
        - Direct correspondence to the task outlined in the prompt
        - Appropriate scope and focus
        - Meaningful connection to the requested task
        - Draws relevant information from the provided sources

    2. Accuracy (0-100)
        - Factual correctness of statements
        - Proper use of any technical terms
        - Consistency with information given in the prompt
        - Consistency with information provided in the sources

    3. Completeness (0-100)
        - Coverage of all prompt requirements
        - Sufficient depth of response
        - No missing critical elements
        - Utilizes effectively the available information

    4. Instruction Adherence (0-100)
        - Following explicit directions
        - Respecting stated constraints
        - Maintaining requested format/structure

    5. Coherence and Clarity (0-100)
        - Logical flow and organization
        - Clear expression of ideas
        - Appropriate transitions and connections

    6. Hallucination Assessment (0-100)
        - Sticking to available information
        - No unsupported claims
        - Appropriate qualification of uncertainties
        - Uses information strictly provided in the prompt and/or sources

    Analysis Process:
        1. First read both prompt and output carefully
        2. Begin analysis in <scratchpad>
        3. Evaluate each criterion separately
        4. Cite specific examples for each score
        5. Synthesize overall assessment
        6. Score each criterion from 0-100, where 0 is worst and 100 is best

    Based on your analysis, respond using the provided tool with a JSON object.

    Example:

    ```jsonc
    {
        "relevance": {
            "score": 91,
            "reasoning": "The output directly addresses all key aspects of the prompt, staying focused on the requested task with clear connections to requirements"
        },
        "accuracy": {
            "score": 83,
            "reasoning": "Technical terms are used correctly and statements align with given information, with minor imprecisions in domain-specific details"
        },
        "completeness": {
            "score": 100,
            "reasoning": "All prompt requirements are thoroughly addressed with appropriate depth and no missing elements"
        },
        "instruction_adherence": {
            "score": 70,
            "reasoning": "Follows all explicit directions and maintains requested format throughout, with careful attention to constraints"
        },
        "coherence_clarity": {
            "score": 80,
            "reasoning": "Well-organized response with clear logical flow and effective transitions between ideas"
        },
        "hallucination": {
            "score": 100,
            "reasoning": "Stays strictly within provided information, appropriately qualifies uncertainties, and makes no unsupported claims"
        }
    }
    """,
    )
    assert complex_template.to_string(
        prompt="Write a short story about a detective solving a mystery",
        model_output="The detective solved the mystery by finding the missing clue",
    )


def test_set_default_basic() -> None:
    """Test basic default value setting works."""
    template = PromptTemplate("Hello ${name}!")
    template.set_default(name="World")
    result = template.to_string()
    assert result == "Hello World!"


def test_set_default_with_override() -> None:
    """Test that explicitly provided values override defaults."""
    template = PromptTemplate("Hello ${name}!")
    template.set_default(name="World")
    result = template.to_string(name="Alice")
    assert result == "Hello Alice!"


def test_set_default_invalid_keys() -> None:
    """Test error when invalid keys are provided to set_default."""
    template = PromptTemplate("Hello ${name}!")
    with pytest.raises(InvalidTemplateKeysError) as exc_info:
        template.set_default(name="World", invalid_key="Value")
    assert "invalid_key" in str(exc_info.value)


def test_set_default_multiple() -> None:
    """Test setting multiple default values."""
    template = PromptTemplate("${greeting} ${name}! How is ${location}?")
    template.set_default(greeting="Hello", location="London")

    # Test with just the required non-default value
    result = template.to_string(name="Alice")
    assert result == "Hello Alice! How is London?"

    # Test overriding some defaults but not others
    result = template.to_string(name="Bob", greeting="Hi")
    assert result == "Hi Bob! How is London?"


def test_mutable_default_safety() -> None:
    """Test that mutable defaults are properly deep copied."""
    template = PromptTemplate("${config}")
    default_config = {"theme": "dark", "settings": {"language": "en"}}
    template.set_default(config=default_config)

    # Modify the original dict
    default_config["theme"] = "light"
    default_config["settings"]["language"] = "fr"  # type: ignore[index]

    # The template should maintain the original values
    result = template.to_string()
    assert '"theme": "dark"' in result
    assert '"language": "en"' in result


def test_defaults_in_substitution() -> None:
    """Test that defaults are properly carried over in substitution."""
    template = PromptTemplate("${greeting} ${name}! Settings: ${config}")
    template.set_default(greeting="Hello", config={"theme": "dark"})

    # Create a new template via substitution
    new_template = template.substitute(name="Alice")

    # The new template should have its own copy of defaults
    result = new_template.to_string()
    assert "Hello Alice!" in result
    assert '"theme": "dark"' in result

    # Modifying original template defaults shouldn't affect the new template
    template.set_default(greeting="Hi")
    assert "Hello Alice!" in new_template.to_string()


def test_list_default_safety() -> None:
    """Test that list defaults are properly deep copied."""
    template = PromptTemplate("${items}")
    default_items = [1, [2, 3], {"nested": 4}]
    template.set_default(items=default_items)

    # Modify the original list deeply
    default_items[0] = 9
    default_items[1][0] = 8  # type: ignore[index]
    default_items[2]["nested"] = 7  # type: ignore[index]

    # The template should maintain the original values
    result = template.to_string()
    assert '[1, [2, 3], {"nested": 4}]' in result


def test_multiple_substitutions_with_defaults() -> None:
    """Test that multiple substitutions maintain proper default isolation."""
    template = PromptTemplate("${config} - ${name}")
    template.set_default(config={"setting": "original"})

    template1 = template.substitute(name="Alice")
    template2 = template.substitute(name="Bob")

    # Modify template1's defaults
    template1.set_default(config={"setting": "modified"})

    # template2 should maintain original defaults
    assert '"setting": "original"' in template2.to_string()
    assert '"setting": "modified"' in template1.to_string()


def test_nested_template_defaults() -> None:
    """Test defaults with nested template structures."""
    template = PromptTemplate("""
    {
        "user": {
            "name": "${name}",
            "settings": ${settings}
        }
    }
    """)

    template.set_default(settings={"theme": "dark", "nested": {"option": "value"}})
    result = template.to_string(name="Alice")

    assert '"name": "Alice"' in result
    assert '"theme": "dark"' in result
    assert '"option": "value"' in result


def test_default_value_serialization() -> None:
    """Test that default values are properly serialized."""
    template = PromptTemplate("${number}, ${decimal}, ${uuid_val}, ${bytes_val}")

    from decimal import Decimal

    template.set_default(
        number=42,
        decimal=Decimal("3.14"),
        uuid_val=UUID("550e8400-e29b-41d4-a716-446655440000"),
        bytes_val=b"binary data",
    )

    result = template.to_string()
    assert "42" in result
    assert "3.14" in result
    assert "550e8400-e29b-41d4-a716-446655440000" in result
    assert "binary data" in result or "YmluYXJ5IGRhdGE=" in result  # base64 encoded if can't decode


def test_template_equality_with_defaults() -> None:
    """Test that templates with different defaults are still equal if template strings match."""
    template1 = PromptTemplate("Hello ${name}!", "greeting")
    template2 = PromptTemplate("Hello ${name}!", "greeting")

    template1.set_default(name="Alice")
    template2.set_default(name="Bob")

    # Templates should be equal despite different defaults
    assert template1 == template2


def test_template_constructor_validation() -> None:
    """Test validation of constructor arguments."""
    with pytest.raises(TypeError, match="template must be a string"):
        PromptTemplate(123)  # type: ignore

    with pytest.raises(TypeError, match="name must be a string"):
        PromptTemplate("${a}", name=123)  # type: ignore


def test_serialization_errors() -> None:
    """Test error handling during value serialization."""

    class Unserializable:
        pass

    template = PromptTemplate("${a}")
    with pytest.raises(TemplateSerializationError) as exc_info:
        template.to_string(a=Unserializable())

    assert "Failed to serialize value for key 'a'" in str(exc_info.value)
    assert isinstance(exc_info.value.original_error, TypeError)


def test_template_name_in_errors() -> None:
    """Test that template name is included in error messages."""
    template = PromptTemplate("${a}", name="test_template")

    with pytest.raises(MissingTemplateValuesError) as exc_info_missing:
        template.to_string()
    assert "[Template: test_template]" in str(exc_info_missing.value)

    with pytest.raises(InvalidTemplateKeysError) as exc_info_invalid:
        template.to_string(a="value", invalid_key="value")
    assert "[Template: test_template]" in str(exc_info_invalid.value)


def test_variables_caching() -> None:
    """Test that variables property caches its results."""
    template = PromptTemplate("${a} ${b} ${c}")

    # First access should compute the variables
    vars1 = template.variables
    assert vars1 == {"a", "b", "c"}

    # Second access should use cached value
    vars2 = template.variables
    assert vars2 == {"a", "b", "c"}

    # Modifying the returned set shouldn't affect the cache
    vars1.add("d")
    assert template.variables == {"a", "b", "c"}


def test_serializer_edge_cases() -> None:
    """Test edge cases in the serializer method."""
    # Test bytes serialization with different encodings
    assert PromptTemplate.serializer(b"hello") == "hello"  # UTF-8 decodable
    assert PromptTemplate.serializer(b"\xff\xff") == "ÿÿ"  # Latin1 fallback

    # Test various Python types
    assert PromptTemplate.serializer(None) == "null"
    assert PromptTemplate.serializer(True) == "true"
    assert PromptTemplate.serializer(123) == "123"
    assert PromptTemplate.serializer([1, 2, 3]) == "[1, 2, 3]"


def test_prepare_edge_cases() -> None:
    """Test edge cases in prepare method."""
    template = PromptTemplate("${var}")

    # Test empty string value
    result = template.prepare(True, var="")
    assert result["var"] == ""

    # Test None value
    result = template.prepare(True, var=None)
    assert result["var"] == "null"

    # Test nested template with substitute=False
    nested = PromptTemplate("${inner}")
    result = template.prepare(False, var=nested)
    assert "PromptTemplate" in result["var"]


def test_template_equality_edge_cases() -> None:
    """Test edge cases in template equality comparison."""
    template1 = PromptTemplate("test", name="name1")
    template2 = PromptTemplate("test", name="name1")  # Same name
    template3 = PromptTemplate("different", name="name1")

    # Test same template and name
    assert template1 == template2

    # Test different templates
    assert template1 != template3

    # Test comparison with non-PromptTemplate
    assert template1 != "test"

    # Test hash equality
    assert hash(template1) == hash(template2)
    assert hash(template1) != hash(template3)


def test_template_equality_different_types() -> None:
    """Test template equality with different types."""
    template = PromptTemplate("test")
    # Test comparison with None
    assert template != None  # noqa: E711
    # Test comparison with different type
    assert template != 42


def test_prepare_complex_cases() -> None:
    """Test complex cases in prepare method."""
    template = PromptTemplate("${var}")
    nested = PromptTemplate("${inner}")
    nested.set_default(inner="value")

    # Test nested template with substitute=True
    result = template.prepare(True, var=nested)
    assert result["var"] == "value"  # Substituted value

    # Test with non-string, non-template value that needs JSON serialization
    result = template.prepare(True, var={"key": "value"})
    assert result["var"] == '{"key": "value"}'

    # Test with invalid value that can't be serialized
    class UnserializableObject:
        pass

    with pytest.raises(TemplateSerializationError):
        template.prepare(True, var=UnserializableObject())

    # Test with invalid key
    with pytest.raises(InvalidTemplateKeysError):
        template.prepare(True, invalid_key="value")

    # Test with nested template and substitute=False
    result = template.prepare(False, var=nested)
    assert isinstance(result["var"], str)
    assert "PromptTemplate" in result["var"]

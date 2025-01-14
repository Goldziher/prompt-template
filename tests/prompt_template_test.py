from uuid import UUID

import pytest
from prompt_template import (
    InvalidTemplateKeysError,
    MissingTemplateValuesError,
    PromptTemplate,
    TemplateError,
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
    template = PromptTemplate("${a}, ${b}, ${c}, ${d}")
    result = template.to_string(a=123, b=45.67, c=UUID("550e8400-e29b-41d4-a716-446655440000"), d=b"binary data")
    assert "123" in result
    assert "45.67" in result
    assert "550e8400-e29b-41d4-a716-446655440000" in result

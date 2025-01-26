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

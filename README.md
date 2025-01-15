# Prompt Template

This is a lightweight zero-dependency Python library for managing LLM prompt template. Its modelled on the stdlib `string.Template` but with more robust features.

## Features

    - Template validation
    - Support for nested braces and JSON structures
    - Automatic value serialization
    - Incremental template population
    - Clear error messages with detailed context
    - Type hints for better IDE support
    - Extensible design

## Installation

Install using pip:

    ```bash
    pip install prompt-template
    ```

## Usage

### Basic Usage

    ```python
    from prompt_template import PromptTemplate

    # Create a template
    template = PromptTemplate("Hello ${name}! Welcome to ${location}.")

    # Render the template
    result = template.to_string(name="Alice", location="Wonderland")
    print(result)  # Hello Alice! Welcome to Wonderland.
    ```

### Working with JSON Templates

    ```python
    template = PromptTemplate("""
    {
        "user": "${username}",
        "settings": {
            "theme": "${theme}",
            "notifications": ${notifications}
        }
    }
    """)

    # Values are automatically serialized
    result = template.to_string(
        username="john_doe",
        theme="dark",
        notifications={"email": True, "push": False}
    )
    ```

### Incremental Template Population

You can populate template values incrementally using the `substitute` method:

    ```python
    # Start with a base template
    base = PromptTemplate("The ${animal} jumped over the ${obstacle} in ${location}.")

    # Partially populate values
    partial = base.substitute(animal="fox", obstacle="fence")

    # Complete the template later
    final = partial.to_string(location="garden")
    print(final)  # The fox jumped over the fence in garden.
    ```

### Validation Features

The library includes built-in validation to catch common issues:

    ```python
    # Missing variables raise MissingTemplateValuesError
    template = PromptTemplate("Hello ${name}!")
    try:
        template.to_string()  # Raises MissingTemplateValuesError
    except MissingTemplateValuesError as e:
        print(f"Missing values: {e.missing_values}")

    # Invalid keys raise InvalidTemplateKeysError
    try:
        template.to_string(name="World", invalid_key="value")  # Raises InvalidTemplateKeysError
    except InvalidTemplateKeysError as e:
        print(f"Invalid keys: {e.invalid_keys}")
    ```

### Automatic Value Serialization

The library handles various Python types automatically:

    ```python
    from uuid import UUID
    from decimal import Decimal

    template = PromptTemplate("ID: ${id}, Amount: ${amount}, Data: ${data}")
    result = template.to_string(
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        amount=Decimal("45.67"),
        data={"key": "value"}
    )
    ```

### Custom Serialization

You can customize how values are serialized by subclassing `PromptTemplate`:

    ```python
    from datetime import datetime
    import json

    class CustomTemplate(PromptTemplate):
        @staticmethod
        def serializer(value: Any) -> str:
            if isinstance(value, datetime):
                return value.isoformat()
            return json.dumps(value, default=str)

    # Use custom serialization
    template = CustomTemplate("Time: ${current_time}, Data: ${data}")
    result = template.to_string(
        current_time=datetime.now(),
        data={"complex": "object"}
    )
    ```

## Error Handling

The library provides specific exception classes for different error cases:

- `TemplateError`: Base exception for all template-related errors
- `InvalidTemplateKeysError`: Raised when invalid keys are provided
- `MissingTemplateValuesError`: Raised when required template values are missing
- `TemplateSerializationError`: Raised when value serialization fails

## License

MIT License

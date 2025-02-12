# Prompt Template

A lightweight, zero-dependency Python library for managing LLM prompt templates. Built on the design principles of
`string.Template` but with enhanced features specifically designed for LLM prompt engineering.

## Features

- Strong template validation with detailed error messages
- Support for nested braces and complex JSON structures
- Automatic value serialization for common Python types
- Default value support with deep copying for mutable types
- Incremental template population with value inheritance
- Type hints for enhanced IDE support
- Zero dependencies - just pure Python
- 100% test coverage

## Installation

```bash
pip install prompt-template
```

## Usage

The library is intentionally very simple to use.
The idea is to keep it simple, have validation and serialization builtin, and make debugging simple.

### Simple Templates

```python
from prompt_template import PromptTemplate

# Create a template
template = PromptTemplate("Hello ${name}! Welcome to ${location}.")

# Render with values
result = template.to_string(name="Alice", location="Wonderland")
print(result)  # Hello Alice! Welcome to Wonderland.
```

### Default Values

```python
# Set default values that can be overridden later
template = PromptTemplate("Hello ${name}! Your settings are: ${settings}")

# Set default values - they're safely deep copied
template.set_default(
    name="Guest",
    settings={"theme": "light", "language": "en"}
)

# Use with defaults
print(template.to_string())
# Hello Guest! Your settings are: {"theme": "light", "language": "en"}

# Override specific values
print(template.to_string(name="Alice"))
# Hello Alice! Your settings are: {"theme": "light", "language": "en"}

# Override everything
print(template.to_string(
    name="Bob",
    settings={"theme": "dark", "language": "fr"}
))
# Hello Bob! Your settings are: {"theme": "dark", "language": "fr"}
```

### Named Templates

Adding a name to your template enhances error messages with context:

```python
template = PromptTemplate(
    name="user_greeting",
    template="Hello ${name}! Welcome to ${location}."
)
```

### Complex JSON Templates

The library handles nested structures elegantly:

```python
template = PromptTemplate("""
{
    "user": {
        "name": "${username}",
        "role": "${role}"
    },
    "settings": {
        "theme": "${theme}",
        "notifications": ${notifications},
        "preferences": ${preferences}
    }
}
""")

# Values are automatically serialized
result = template.to_string(
    username="john_doe",
    role="admin",
    theme="dark",
    notifications={"email": True, "push": False},
    preferences=["daily_digest", "weekly_report"]
)
```

### Incremental Template Population

You can build templates incrementally, preserving defaults along the way:

```python
# Start with a base template
base = PromptTemplate("""
Query parameters:
    Model: ${model}
    Temperature: ${temperature}
    User: ${user}
    Prompt: ${prompt}
""")

# Set some defaults
base.set_default(
    model="gpt-4",
    temperature=0.7
)

# Create a partially populated template
user_template = base.substitute(user="alice")

# Complete the template later
final = user_template.to_string(prompt="Tell me a story")
```

### Type Handling and Automatic Serialization

The library automatically handles various Python types:

```python
from uuid import UUID
from decimal import Decimal
from datetime import datetime

template = PromptTemplate("""
{
    "id": "${id}",
    "amount": "${amount}",
    "metadata": ${metadata}
}
""")

result = template.to_string(
    id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    amount=Decimal("45.67"),
    metadata={
        "timestamp": datetime.now(),  # Serialized via JSON
        "values": [1, 2, 3]
    }
)
```

### Custom Serialization

Extend the base class to customize value serialization with proper error handling:

```python
from typing import Any
from datetime import datetime
from decimal import Decimal
from prompt_template import PromptTemplate as BasePromptTemplate
import orjson


class PromptTemplate(BasePromptTemplate):
    @staticmethod
    def serializer(value: Any) -> str:
        """Custom serializer with orjson for better performance.

        Handles special cases and provides detailed error messages.
        """
        try:
            # Handle special types first
            if isinstance(value, (datetime, Decimal)):
                return str(value)

            # Use orjson for everything else
            return orjson.dumps(value).decode('utf-8')
        except (TypeError, ValueError) as e:
            raise TypeError(
                f"Failed to serialize value of type {type(value).__name__}: {e}"
            ) from e
```

The custom serializer will be used automatically:

```python
template = PromptTemplate("""
{
    "timestamp": "${time}",
    "amount": "${price}",
    "data": ${complex_data}
}
""")

result = template.to_string(
    time=datetime.now(),
    price=Decimal("45.67"),
    complex_data={"nested": [1, 2, 3]}
)
```

## Error Handling

The library provides specific extensive errors:

### Missing Values

```python
from prompt_template import MissingTemplateValuesError

template = PromptTemplate("Hello ${name}!")
try:
    template.to_string()  # No values provided
except MissingTemplateValuesError as e:
    print(f"Missing values: {e.missing_values}")  # {'name'}
```

### Invalid Keys

```python
from prompt_template import InvalidTemplateKeysError

template = PromptTemplate("Hello ${name}!")
try:
    template.to_string(name="World", invalid_key="value")
except InvalidTemplateKeysError as e:
    print(f"Invalid keys: {e.invalid_keys}")  # ['invalid_key']
    print(f"Valid keys: {e.valid_keys}")  # {'name'}
```

### Serialization Errors

```python
from prompt_template import TemplateSerializationError

template = PromptTemplate("Value: ${value}")
try:
    template.to_string(value=object())  # Non-serializable object
except TemplateSerializationError as e:
    print(f"Failed to serialize key '{e.key}': {e.original_error}")
```

## License

MIT License

---

If you find the library useful, please star it on [GitHub](https://github.com/Goldziher/prompt-template).

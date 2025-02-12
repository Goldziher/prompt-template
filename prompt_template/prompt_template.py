from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from json import dumps
from re import Pattern
from re import compile as compile_re
from textwrap import dedent
from typing import Any, Final, Self, cast
from uuid import UUID

VALID_NAME_PATTERN: Final[Pattern[str]] = compile_re(r"^[_a-zA-Z][_a-zA-Z0-9]*$")


class TemplateError(Exception):
    """Base exception for template-related errors."""

    def __init__(self, message: str, template_name: str | None = None) -> None:
        self.template_name = template_name
        prefix = f"[Template: {template_name}] " if template_name else ""
        super().__init__(f"{prefix}{message}")


class InvalidTemplateKeysError(TemplateError):
    """Raised when invalid keys are provided to a template."""

    def __init__(self, invalid_keys: list[str], valid_keys: set[str], template_name: str | None = None) -> None:
        message = (
            f"Invalid keys provided to PromptTemplate: {','.join(invalid_keys)}\n\n"
            f"Note: the template defines the following variables: {','.join(valid_keys)}"
        )
        super().__init__(message, template_name)
        self.invalid_keys = invalid_keys
        self.valid_keys = valid_keys


class MissingTemplateValuesError(TemplateError):
    """Raised when required template values are missing."""

    def __init__(self, missing_values: set[str], template_name: str | None = None) -> None:
        message = f"Missing values for variables: {','.join(missing_values)}"
        super().__init__(message, template_name)
        self.missing_values = missing_values


class TemplateSerializationError(TemplateError):
    """Raised when template value serialization fails.

    Args:
        key: The template variable key that failed to serialize.
        error: The underlying error that caused serialization to fail.
        template_name: Optional name of the template where the error occurred.
    """

    def __init__(self, key: str, error: Exception, template_name: str | None = None) -> None:
        self.key = key
        self.original_error: Exception = error
        self.template_name = template_name

        details = [
            f"Failed to serialize value for key '{key}':",
            f"Error type: {error.__class__.__name__}",
            f"Error message: {error!s}",
        ]
        message = "\n".join(details)
        super().__init__(message, template_name)


class PromptTemplate:
    """A string template with variable validation.

    This class provides a template engine with strong validation and serialization support.
    It allows defining templates with ${variable} syntax and supports nested JSON structures.

    Args:
        template: The template string using ${variable} syntax.
        name: Optional name for the template, used in error messages.

    Raises:
        TypeError: If template or name are not strings.
    """

    def __init__(self, template: str, name: str | None = None) -> None:
        if not isinstance(template, str):
            raise TypeError(f"template must be a string, got {type(template)}")
        if name is not None and not isinstance(name, str):
            raise TypeError(f"name must be a string or None, got {type(name)}")

        self.name = name or ""
        self.template = self._validate_template(template)
        self._defaults: dict[str, Any] = {}
        self._variables: set[str] | None = None  # Cache for variables property

    def _validate_template(self, template: str) -> str:  # noqa: C901
        """Validate the template format.

        Args:
            template: The template string.

        Raises:
            TemplateError: If the template format is invalid.

        Returns:
            The validated template.
        """
        stack: list[tuple[int, bool]] = []
        i = 0

        while i < len(template):
            if template[i : i + 2] == "${" and i < len(template) - 1:
                if stack and stack[-1][1]:  # Inside a variable declaration
                    raise TemplateError("Nested variable declaration", self.name)
                stack.append((i, True))  # True for ${var}
                i += 2
            elif template[i] == "{" and (i == 0 or (template[i - 1] != "$" and (i < 2 or template[i - 2] != "\\"))):  # noqa: PLR2004
                stack.append((i, False))
                i += 1
            elif template[i] == "}":
                if not stack:
                    raise TemplateError("Unmatched closing brace", self.name)

                start_pos, is_var = stack.pop()
                if is_var:
                    var_name = template[start_pos + 2 : i]
                    if not var_name:
                        raise TemplateError("Empty variable name", self.name)
                    if not VALID_NAME_PATTERN.match(var_name):
                        raise TemplateError(f"Invalid variable name: '{var_name}'", self.name)
                i += 1
            else:
                i += 1

        if stack:
            _, is_var = stack.pop()
            if is_var:
                raise TemplateError("Unclosed variable declaration", self.name)
            raise TemplateError("Unclosed brace", self.name)

        return template

    @staticmethod
    def serializer(value: Any) -> str:
        """Serialize values into strings suitable for template substitution.

        This method handles special cases for common Python types and falls back to JSON
        serialization for other types. Special handling is provided for:
        - str: Used as-is without quoting
        - datetime: Converted to ISO format
        - Decimal: Converted to string to preserve precision
        - UUID: Converted to string representation
        - bytes: Safely decoded to string (utf-8 -> latin1 -> base64)

        Args:
            value: The value to serialize.

        Returns:
            The serialized value as a string.

        Raises:
            TypeError: If the value cannot be serialized.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                # Latin1 can decode any byte sequence
                return value.decode("latin1")
        try:
            return dumps(value)
        except Exception as e:
            raise TypeError(f"Could not serialize value of type {type(value)}: {e}") from e

    @property
    def variables(self) -> set[str]:
        """Get the set of variable names in the template.

        This property parses the template to find all ${variable} occurrences.
        The result is cached for performance.

        Returns:
            A set of variable names found in the template.
        """
        if self._variables is None:
            self._variables = self._find_variables()
        return self._variables.copy()

    def _find_variables(self) -> set[str]:
        """Parse the template to find all variable names.

        Returns:
            A set of variable names found in the template.
        """
        variables = set()
        i = 0

        while i < len(self.template):
            if i < len(self.template) - 1 and self.template[i] == "\\":
                i += 2
                continue

            if i + 1 < len(self.template) and self.template[i : i + 2] == "${":
                j = i + 2
                while j < len(self.template) and self.template[j] != "}":
                    j += 1
                if j < len(self.template) and VALID_NAME_PATTERN.match(self.template[i + 2 : j]):  # pragma: no cover
                    variables.add(self.template[i + 2 : j])
                i = j + 1
            else:
                i += 1

        return variables

    def prepare(self, substitute: bool, **kwargs: Any) -> dict[str, Any]:
        """Prepare the keyword arguments for substitution.

        Args:
            substitute: Whether to substitute PromptTemplate instances.
            **kwargs: The values to substitute.

        Raises:
            InvalidTemplateKeysError: If invalid keys are provided.
            TemplateSerializationError: If value serialization fails.

        Returns:
            The prepared mapping.
        """
        if invalid_keys := [key for key in kwargs if key not in self.variables]:
            raise InvalidTemplateKeysError(invalid_keys, self.variables, self.name)

        mapping: dict[str, Any] = {}

        for key, value in kwargs.items():
            try:
                if isinstance(value, PromptTemplate):
                    # When substituting, render the template with its defaults
                    mapping[key] = value.to_string() if substitute else str(value)
                else:
                    mapping[key] = self.serializer(value)
            except Exception as e:  # noqa: PERF203
                raise TemplateSerializationError(key, e, self.name) from e

        return mapping

    def substitute(self, **kwargs: Any) -> Self:
        """Substitute the template.

        This is a private method used by to_string. It assumes that all keys have been
        validated and all values have been serialized to strings.

        Args:
            **kwargs: The values to substitute. Must be valid template variables and
                     must already be serialized to strings.

        Returns:
            The substituted template.
        """
        mapping = self.prepare(True, **kwargs)

        template = self.template
        for k, v in mapping.items():
            template = template.replace(f"${{{k}}}", v)

        new_name = f"{self.name}_substitution" if self.name else None

        new_template = cast(Self, PromptTemplate(template=template, name=new_name))
        new_template._defaults = deepcopy(self._defaults)  # noqa: SLF001
        return new_template

    def set_default(self, **kwargs: Any) -> None:
        """Set default values for the passed keyword arguments.

        Raises:
            InvalidTemplateKeysError: If invalid keys are provided.

        Args:
            **kwargs: The default values.

        Returns:
            None
        """
        if wrong_kwargs := [key for key in kwargs if key not in self.variables]:
            raise InvalidTemplateKeysError(wrong_kwargs, self.variables, self.name)

        self._defaults.update({k: deepcopy(v) for k, v in kwargs.items()})

    def to_string(self, **kwargs: Any) -> str:
        """Render the template by substituting all variables with their values.

        This is the main method for converting a template to its final string form.
        It will:
        1. Validate all required variables are provided
        2. Use default values for any missing variables
        3. Serialize all values to strings
        4. Perform the template substitution

        Args:
            **kwargs: Values to substitute into the template. These take precedence
                     over any default values.

        Raises:
            MissingTemplateValuesError: If any required variables are missing and have no default value.
            InvalidTemplateKeysError: If invalid keys are provided.

        Returns:
            The fully rendered template with all variables substituted.
        """
        # Check for invalid keys before merging with defaults
        if wrong_keys := [key for key in kwargs if key not in self.variables]:
            raise InvalidTemplateKeysError(wrong_keys, self.variables, self.name)

        values = {**self._defaults, **kwargs}
        if missing_values := self.variables - set(values):
            raise MissingTemplateValuesError(missing_values, self.name)

        mapping = self.prepare(False, **values)
        template_string = self.template

        for key, value in mapping.items():
            template_string = template_string.replace(f"${{{key}}}", value)

        return dedent(template_string).strip()

    def __str__(self) -> str:
        """Return a human-readable string representation of the template.

        Returns:
            A string in the format 'PromptTemplate [name]: template'
        """
        name_str = f" [{self.name}]" if self.name else ""
        return f"{self.__class__.__name__}{name_str}:\n\n{self.template}"

    def __repr__(self) -> str:  # pragma: no cover
        """Return the string representation."""
        return self.__str__()

    def __hash__(self) -> int:
        """Return the hash of the template."""
        return hash((self.name, self.template))

    def __eq__(self, other: object) -> bool:
        """Check if two templates are equal."""
        if not isinstance(other, PromptTemplate):
            return NotImplemented
        return self.template == other.template and self.name == other.name

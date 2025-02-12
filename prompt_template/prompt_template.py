from __future__ import annotations

from base64 import b64encode
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
    """Raised when template value serialization fails."""

    def __init__(self, key: str, error: Exception, template_name: str | None = None) -> None:
        message = f"Failed to serialize value for key '{key}': {error}"
        super().__init__(message, template_name)
        self.key = key
        self.original_error = error


class PromptTemplate:
    """A string template with variable validation.

    Args:
        template: The template string.
        name: Optional name for the template.
    """

    def __init__(self, template: str, name: str | None = None) -> None:
        self.name = name or ""
        self.template = self._validate_template(template)
        self._defaults: dict[str, Any] = {}

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
        """Serializer values into JSON.

        Args:
            value: The value to serialize.

        Returns:
            The serialized value.
        """
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        return dumps(value)

    @property
    def variables(self) -> set[str]:
        """Get the variables in the template.

        Returns:
            The variables in the template.
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
                if j < len(self.template) and VALID_NAME_PATTERN.match(self.template[i + 2 : j]):
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
                    mapping[key] = value.template if substitute else str(value)
                elif isinstance(value, str):
                    mapping[key] = value
                elif isinstance(value, (int | float | Decimal | UUID)):
                    mapping[key] = str(value)
                elif isinstance(value, bytes):
                    try:
                        mapping[key] = value.decode()
                    except UnicodeDecodeError:
                        mapping[key] = b64encode(value).decode("ascii")
                else:
                    mapping[key] = self.serializer(value)
            except Exception as e:  # noqa: PERF203
                raise TemplateSerializationError(key, e, self.name) from e

        return mapping

    def substitute(self, **kwargs: Any) -> Self:
        """Substitute the template.

        Args:
            **kwargs: The values to substitute.

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
        """Convert the template to a string with substituted values.

        Args:
            **kwargs: The values to substitute.

        Raises:
            MissingTemplateValuesError: If required values are missing.

        Returns:
            The template string with substituted values.
        """
        values = {**self._defaults, **kwargs}
        if missing_values := self.variables - set(values):
            raise MissingTemplateValuesError(missing_values, self.name)

        mapping = self.prepare(False, **values)
        template_string = self.template

        for key, value in mapping.items():
            template_string = template_string.replace(f"${{{key}}}", value)

        return dedent(template_string).strip()

    def __str__(self) -> str:
        """Return the string representation."""
        name_str = f" [{self.name}]" if hasattr(self, "name") else ""
        template_str = self.template if hasattr(self, "template") else ""
        return f"{self.__class__.__name__}{name_str}:\n\n{template_str}"

    def __repr__(self) -> str:
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

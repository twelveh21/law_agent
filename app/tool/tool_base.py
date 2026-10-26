"""Shared interfaces and registry for the application's tools."""

from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """A machine-readable description of one tool parameter."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class Tool(ABC):
    """Base class that gives every tool the same interface."""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, parameters: dict[str, Any]) -> str:
        """Execute the tool with a dictionary of parameters."""

    @abstractmethod
    def get_parameters(self) -> list[ToolParameter]:
        """Return this tool's parameter descriptions."""

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert this tool's metadata to a Function Calling schema."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for parameter in self.get_parameters():
            description = parameter.description
            if parameter.default is not None:
                description = f"{description} (默认: {parameter.default})"

            property_schema: dict[str, Any] = {
                "type": parameter.type,
                "description": description,
            }
            if parameter.type == "array":
                property_schema["items"] = {"type": "string"}

            properties[parameter.name] = property_schema
            if parameter.required:
                required.append(parameter.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    """Register, discover, describe, and execute tool objects."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._functions: dict[str, dict[str, Any]] = {}

    def register(self, tool: Tool) -> None:
        """Register a Tool instance, rejecting accidental name collisions."""
        if tool.name in self._tools or tool.name in self._functions:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool

    def register_function(
        self, name: str, description: str, func: Callable[[str], str]
    ) -> None:
        """Register a simple string-in/string-out function."""
        if name in self._tools or name in self._functions:
            raise ValueError(f"工具 '{name}' 已注册")
        self._functions[name] = {"description": description, "func": func}

    def get_tool(self, name: str) -> Tool:
        """Find a registered Tool object by name."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"未注册工具: {name}") from exc

    def list_tools(self) -> list[str]:
        """List registered object and function tool names."""
        return [*self._tools, *self._functions]

    def execute_tool(self, name: str, parameters: Any) -> str:
        """Execute a registered tool or simple function."""
        if name in self._tools:
            if not isinstance(parameters, dict):
                raise TypeError("Tool.run 的参数必须是字典")
            return self._tools[name].run(parameters)

        if name in self._functions:
            if not isinstance(parameters, str):
                raise TypeError("函数工具的参数必须是字符串")
            return self._functions[name]["func"](parameters)

        raise KeyError(f"未注册工具: {name}")

    def get_tools_description(self) -> str:
        """Return a compact human-readable list of available tools."""
        descriptions = [
            f"-{tool.name}: {tool.description}" for tool in self._tools.values()
        ]
        descriptions.extend(
            f"-{name}: {info['description']}" for name, info in self._functions.items()
        )
        return "\n".join(descriptions) if descriptions else "暂无可用工具"

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        """Return Function Calling schemas for registered Tool instances."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

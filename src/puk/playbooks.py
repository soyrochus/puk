from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_FRONT_MATTER_BOUNDARY = "---"
_JSON_FENCE = re.compile(r"```(?:json)?\n(.*?)```", re.DOTALL | re.IGNORECASE)


class PlaybookValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    type: str
    required: bool = False
    default: Any | None = None
    description: str = ""
    enum_values: list[str] | None = None


@dataclass(frozen=True)
class Playbook:
    id: str
    version: str
    description: str
    parameters: dict[str, ParameterSpec]
    allowed_tools: list[str]
    write_scope: list[str]
    run_mode: str
    body: str
    path: Path


def load_playbook(path: Path) -> Playbook:
    if not path.exists():
        raise PlaybookValidationError(f"Playbook file '{path}' does not exist.")
    text = path.read_text(encoding="utf-8")
    front_matter, body = _split_front_matter(text, path)
    data = yaml.safe_load(front_matter) or {}
    if not isinstance(data, dict):
        raise PlaybookValidationError("Playbook front-matter must be a YAML mapping.")
    required = ["id", "version", "description", "parameters", "allowed_tools", "write_scope", "run_mode"]
    missing = [key for key in required if key not in data]
    if missing:
        raise PlaybookValidationError(f"Playbook front-matter missing required fields: {', '.join(missing)}.")
    parameters = _parse_parameters(data.get("parameters", {}))
    allowed_tools = _ensure_list("allowed_tools", data["allowed_tools"])
    write_scope = _ensure_list("write_scope", data["write_scope"])
    run_mode = data["run_mode"]
    if run_mode not in {"plan", "apply"}:
        raise PlaybookValidationError("Playbook run_mode must be 'plan' or 'apply'.")
    return Playbook(
        id=str(data["id"]),
        version=str(data["version"]),
        description=str(data["description"]),
        parameters=parameters,
        allowed_tools=allowed_tools,
        write_scope=write_scope,
        run_mode=run_mode,
        body=body,
        path=path,
    )


def resolve_parameters(
    specs: dict[str, ParameterSpec],
    raw_params: dict[str, str],
    workspace: Path,
    *,
    allow_outside_root: bool = False,
    follow_symlinks: bool = False,
) -> dict[str, Any]:
    unknown = [key for key in raw_params if key not in specs]
    if unknown:
        raise PlaybookValidationError(f"Unknown parameter(s): {', '.join(sorted(unknown))}.")
    resolved: dict[str, Any] = {}
    for name, spec in specs.items():
        if name in raw_params:
            value = raw_params[name]
        elif spec.default is not None:
            value = spec.default
        elif spec.required:
            raise PlaybookValidationError(f"Missing required parameter '{name}'.")
        else:
            continue
        resolved[name] = _convert_param_value(
            spec,
            value,
            workspace,
            allow_outside_root=allow_outside_root,
            follow_symlinks=follow_symlinks,
        )
    return resolved


def render_body(body: str, params: dict[str, Any]) -> str:
    rendered = body
    for key, value in params.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered


def extract_plan_from_text(text: str) -> dict[str, Any]:
    payload = _extract_json(text)
    if not isinstance(payload, dict) or "steps" not in payload:
        raise PlaybookValidationError("Plan output must be a JSON object containing a 'steps' list.")
    if not isinstance(payload["steps"], list):
        raise PlaybookValidationError("Plan output 'steps' must be a list.")
    return payload


def is_path_within_scope(path: str, workspace: Path, write_scope: list[str]) -> bool:
    if not write_scope:
        return False
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = (workspace / resolved).resolve()
    workspace_resolved = workspace.resolve()
    if not _is_relative_to(resolved, workspace_resolved):
        return False
    rel = resolved.relative_to(workspace_resolved).as_posix()
    for pattern in write_scope:
        if fnmatch.fnmatch(rel, pattern):
            return True
        if pattern.endswith("/**"):
            base = pattern[:-3].rstrip("/")
            if base and (rel == base or rel.startswith(f"{base}/")):
                return True
    return False


def parse_param_assignments(assignments: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in assignments:
        if "=" not in item:
            raise PlaybookValidationError("Parameters must be provided as key=value.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise PlaybookValidationError("Parameter name cannot be empty.")
        parsed[key] = value
    return parsed


def _split_front_matter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONT_MATTER_BOUNDARY:
        raise PlaybookValidationError(f"Playbook '{path}' missing YAML front-matter.")
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONT_MATTER_BOUNDARY:
            front = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1 :]).lstrip("\n")
            return front, body
    raise PlaybookValidationError(f"Playbook '{path}' front-matter is not closed.")


def _parse_parameters(raw: Any) -> dict[str, ParameterSpec]:
    if not isinstance(raw, dict):
        raise PlaybookValidationError("Playbook parameters must be a mapping.")
    specs: dict[str, ParameterSpec] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise PlaybookValidationError(f"Parameter '{name}' definition must be a mapping.")
        param_type = value.get("type")
        if param_type not in {"string", "int", "float", "bool", "enum", "path"}:
            raise PlaybookValidationError(f"Parameter '{name}' has invalid type '{param_type}'.")
        enum_values = value.get("enum_values")
        if param_type == "enum":
            if not isinstance(enum_values, list) or not enum_values:
                raise PlaybookValidationError(f"Parameter '{name}' enum_values must be a non-empty list.")
            enum_values = [str(v) for v in enum_values]
        specs[name] = ParameterSpec(
            name=name,
            type=param_type,
            required=bool(value.get("required", False)),
            default=value.get("default"),
            description=str(value.get("description", "")),
            enum_values=enum_values,
        )
    return specs


def _ensure_list(field: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        raise PlaybookValidationError(f"Playbook field '{field}' must be a list.")
    return [str(v) for v in value]


def _convert_param_value(
    spec: ParameterSpec,
    value: Any,
    workspace: Path,
    *,
    allow_outside_root: bool,
    follow_symlinks: bool,
) -> Any:
    if spec.type == "string":
        return str(value)
    if spec.type == "int":
        try:
            return int(value)
        except Exception as exc:
            raise PlaybookValidationError(f"Parameter '{spec.name}' must be an int.") from exc
    if spec.type == "float":
        try:
            return float(value)
        except Exception as exc:
            raise PlaybookValidationError(f"Parameter '{spec.name}' must be a float.") from exc
    if spec.type == "bool":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
        raise PlaybookValidationError(f"Parameter '{spec.name}' must be a boolean.")
    if spec.type == "enum":
        if spec.enum_values is None:
            raise PlaybookValidationError(f"Parameter '{spec.name}' missing enum_values.")
        value_str = str(value)
        if value_str not in spec.enum_values:
            raise PlaybookValidationError(
                f"Parameter '{spec.name}' must be one of {', '.join(spec.enum_values)}."
            )
        return value_str
    if spec.type == "path":
        resolved = Path(value)
        if not resolved.is_absolute():
            candidate = workspace / resolved
        else:
            candidate = resolved
        resolved = candidate.resolve()
        workspace_resolved = workspace.resolve()
        if not allow_outside_root and not _is_relative_to(resolved, workspace_resolved):
            raise PlaybookValidationError(
                f"Parameter '{spec.name}' must resolve within the workspace."
            )
        if (
            not follow_symlinks
            and candidate.is_relative_to(workspace_resolved)
            and not _is_relative_to(resolved, workspace_resolved)
        ):
            raise PlaybookValidationError(
                f"Parameter '{spec.name}' escapes the workspace via symlink."
            )
        return str(resolved)
    raise PlaybookValidationError(f"Parameter '{spec.name}' has unsupported type '{spec.type}'.")


def _extract_json(text: str) -> Any:
    text = text.strip()
    if not text:
        raise PlaybookValidationError("Plan output is empty.")
    fenced = _JSON_FENCE.findall(text)
    candidates = []
    if fenced:
        candidates.extend(fenced)
    candidates.append(text)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception as exc:
            raise PlaybookValidationError("Plan output is not valid JSON.") from exc
    raise PlaybookValidationError("Plan output is not valid JSON.")


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

# Copilot SDK — Setup & Pinned Version

## Pinned submodule

| Field      | Value                                              |
|------------|----------------------------------------------------|
| Path       | `vendor/copilot-sdk/`                              |
| Commit     | `a552ae497313143e2426d6ff7e99b2632ab573dd`         |
| Nearest tag| `go/v0.1.20-9-ga552ae4`                            |
| Summary    | Cache list_models across all SDK languages to prevent rate limiting under concurrency (#300) |

## Python package

| Field           | Value                    |
|-----------------|--------------------------|
| Package name    | `github-copilot-sdk`     |
| Version         | `0.1.0`                  |
| Python requires | `>=3.9`                  |
| License         | MIT                      |

## Install (editable, dev extras)

```bash
pip install -e "./vendor/copilot-sdk/python[dev]"
# or
uv pip install -e "./vendor/copilot-sdk/python[dev]"
```

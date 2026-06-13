# Releasing alphai-sdk

The package builds to `alphai_sdk-<version>` (sdist + wheel) and publishes to
PyPI as **`alphai-sdk`** (import name `alphai`). The name is currently free on
PyPI.

## 1. Pre-flight

```bash
uv venv && uv pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src/alphai && pytest
```

Bump the version in `src/alphai/_version.py` and add a dated section to
`CHANGELOG.md`.

## 2. Build & check

```bash
rm -rf dist && uv build
uvx twine check dist/*
```

Verify a clean install:

```bash
uv venv /tmp/verify && /tmp/verify/bin/python -m pip install dist/*.whl
/tmp/verify/bin/python -c "import alphai; print(alphai.__version__)"
```

## 3. TestPyPI dry run (recommended)

```bash
uvx twine upload --repository testpypi dist/*
# then in a clean venv:
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ alphai-sdk
ALPHAI_API_KEY=ak_live_... python examples/quickstart.py
```

## 4. Publish

**Preferred — Trusted Publishing (OIDC), no tokens.** Configure the publisher
once at <https://pypi.org/manage/account/publishing/> (project `alphai-sdk`,
workflow `release.yml`, environment `pypi`), then:

```bash
git tag v0.1.0 && git push origin v0.1.0   # release.yml builds + publishes
```

**Fallback — manual upload with an API token:**

```bash
uvx twine upload dist/*    # uses ~/.pypirc or TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-...
```

## 5. After publishing

- Smoke-test `pip install alphai-sdk` in a clean venv against prod.
- (In the main `alphai_io` repo) add `pip install alphai-sdk` to `/developers`
  and a `/changelog` entry if it's consumer-actionable — run the `changelog`
  skill.

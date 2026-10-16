"""Build-time patch for the upstream Mem0 v2.2.1 REST server (server/).

Upstream builds the Mem0 runtime (LLM + embedder + pgvector) at import time, so the
API crash-loops with "Missing credentials" when OPENAI_API_KEY is empty. This patch
makes that one step lazy and non-fatal:

* boot never fails because the LLM/embedder key is missing: the API, auth, API keys
  and the dashboard all work, and the reason is logged once;
* every memory endpoint retries the runtime on demand, so a key added later (Railway
  variable + redeploy, or the dashboard Configuration page) works without a rebuild;
* until then memory endpoints answer 502 with code "provider_not_configured" and a
  message that says exactly what to set.

Every replacement asserts its anchor, so a changed upstream file fails the build
instead of silently shipping an unpatched server.
"""

import os
from pathlib import Path

APP = Path(os.environ.get("MEM0_APP_DIR", "/app"))


def patch(path: str, old: str, new: str) -> None:
    file = APP / path
    text = file.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"patch_upstream: anchor not found exactly once in {path}: {old[:60]!r}")
    file.write_text(text.replace(old, new))
    print(f"patch_upstream: patched {path}")


HINT = (
    "No LLM/embedding provider is configured yet. Set OPENAI_API_KEY on the mem0-api "
    "service (or pick a provider and key on the dashboard Configuration page), then retry."
)

patch(
    "server_state.py",
    "_session_factory: Callable | None = None\n",
    "_session_factory: Callable | None = None\n"
    "_init_error: str | None = None\n"
    "\n"
    "\n"
    "class ProviderNotConfigured(RuntimeError):\n"
    "    \"\"\"Raised by get_memory_instance() while the Mem0 runtime cannot be built (e.g. no LLM key).\"\"\"\n"
    "\n"
    "\n"
    "def _try_build_memory() -> None:\n"
    "    global _memory_instance, _init_error\n"
    "    try:\n"
    "        _memory_instance = Memory.from_config(_current_config)\n"
    "        if _init_error is not None:\n"
    "            logging.info(\"[railway] Mem0 memory runtime initialised.\")\n"
    "        _init_error = None\n"
    "    except Exception as exc:  # noqa: BLE001 - surfaced to clients via ProviderNotConfigured\n"
    "        _memory_instance = None\n"
    "        first = _init_error is None\n"
    "        _init_error = f\"{type(exc).__name__}: {exc}\"\n"
    "        if first:\n"
    "            logging.warning(\n"
    f"                \"[railway] Mem0 memory runtime not initialised (%s). The API is up; memory endpoints \"\n"
    f"                \"return provider_not_configured until this is fixed. {HINT}\",\n"
    "                _init_error,\n"
    "            )\n",
)

patch(
    "server_state.py",
    "            _current_config = _merge_config(_current_config, overrides)\n"
    "        _memory_instance = Memory.from_config(_current_config)\n",
    "            _current_config = _merge_config(_current_config, overrides)\n"
    "        _try_build_memory()\n",
)

patch(
    "server_state.py",
    "        if _memory_instance is None:\n"
    "            raise RuntimeError(\"Mem0 runtime has not been initialized.\")\n"
    "        return _memory_instance\n",
    "        if _memory_instance is None:\n"
    "            _try_build_memory()\n"
    "        if _memory_instance is None:\n"
    f"            raise ProviderNotConfigured({HINT!r} + \" Last error: \" + str(_init_error))\n"
    "        return _memory_instance\n",
)

patch(
    "errors.py",
    "    name = type(exc).__name__\n",
    "    name = type(exc).__name__\n"
    "    if name == \"ProviderNotConfigured\":\n"
    f"        return (\"provider_not_configured\", {HINT!r})\n",
)

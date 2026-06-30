"""Fixtures pytest para evaluación del grafo e-commerce."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Raíz del proyecto en PYTHONPATH
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMINI_API_KEY", "test-local-key")
os.environ.setdefault("SHOPIFY_STORE_URL", "tienda-demo.myshopify.com")
os.environ.setdefault("SHOPIFY_ACCESS_TOKEN", "shpat_test")
os.environ.setdefault("WHATSAPP_TOKEN", "test")
os.environ.setdefault("WHATSAPP_PHONE_ID", "100")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test")
os.environ.setdefault("REDIS_URL", "redis://fake:6379/0")

# Compat langchain
try:
    import langchain

    if not hasattr(langchain, "debug"):
        langchain.debug = False  # type: ignore
    if not hasattr(langchain, "verbose"):
        langchain.verbose = False  # type: ignore
except ImportError:
    pass

from eval.dataset_builder import load_dataset
from eval.mocks import apply_eval_patches
from eval.results_collector import RESULTS
from eval.tracer import EvalTracer


@pytest.fixture(scope="session", autouse=True)
def _setup_mocks():
    apply_eval_patches()
    yield


@pytest.fixture(scope="session")
def dataset(request):
    quick = request.config.getoption("--quick", default=False)
    category = request.config.getoption("--category", default=None)
    return load_dataset(quick=quick, category=category or None)


@pytest.fixture
def langsmith_tracer():
    return EvalTracer.create_experiment("pytest_case")


@pytest.fixture
def graph_with_mocks():
    from eval.mocks import build_eval_graph

    return build_eval_graph()


@pytest.fixture
def gemini_judge():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("test"):
        from eval.mocks import DeterministicTestLLM

        return DeterministicTestLLM()
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=os.environ.get("GEMINI_MODEL", "gemini-1.5-pro"),
        google_api_key=api_key,
        temperature=0.0,
    )


@pytest.fixture(scope="session")
def eval_results():
    return RESULTS


def pytest_addoption(parser):
    parser.addoption("--quick", action="store_true", default=False, help="Solo 10 casos")
    parser.addoption("--category", action="store", default=None, help="Filtrar categoría")
    parser.addoption("--report", action="store_true", default=False, help="Generar HTML")


@pytest.fixture
async def run_case_fn():
    from eval.runner import run_case

    async def _run(case, tracer=None):
        return await run_case(case, tracer)

    return _run

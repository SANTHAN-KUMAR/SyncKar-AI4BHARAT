"""
Combined Mock Systems — single FastAPI application that hosts all three
mock department systems on separate URL prefixes.

  /sws/*         → Mock SWS (Single Window System)
  /shop/*        → Mock Shop Establishment Department
  /factories/*   → Mock Factories Department

Railway free-plan consolidation: instead of three separate services
(mock-sws, mock-shop, mock-factories) this single app runs all of them
in one Railway service, listening on PORT (default 8000).

The SyncKar adapters reach each system via:
  MOCK_SWS_BASE_URL      = https://<this-service>/sws
  MOCK_SHOP_BASE_URL     = https://<this-service>/shop
  MOCK_FACTORIES_BASE_URL = https://<this-service>/factories
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Import the three individual mock apps ──────────────────────────────────
# Each sub-app is a self-contained FastAPI instance defined in its own module.
# We mount them under path prefixes so their routes don't collide.
from mock_systems.mock_sws.app import app as sws_app
from mock_systems.mock_dept_shop.app import app as shop_app
from mock_systems.mock_dept_factories.app import app as factories_app

# ── Root app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SyncKar — Combined Mock Systems",
    description=(
        "Single service hosting all three mock department systems. "
        "Prefixes: /sws, /shop, /factories"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "healthy",
        "systems": ["mock_sws", "mock_shop_establishment", "mock_factories"],
    }


# Mount each sub-app under its own prefix.
# FastAPI sub-application mounting preserves all routes defined inside each app.
app.mount("/sws", sws_app)
app.mount("/shop", shop_app)
app.mount("/factories", factories_app)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)

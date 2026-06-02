import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from routes import health, riftbound, scan, scan_jobs

logging.basicConfig(level=logging.INFO)

_cors_origins, _cors_allow_credentials = config.parse_cors_origins()

app = FastAPI(title="Pokemon Card Scan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(scan.router)
app.include_router(scan_jobs.router)
app.include_router(riftbound.router)

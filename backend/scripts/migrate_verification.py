"""Add verification_results table without touching existing data."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.database import engine
from backend.app.models.models import VerificationResult  # noqa: ensure model is loaded

VerificationResult.__table__.create(bind=engine, checkfirst=True)
print("verification_results table ready.")

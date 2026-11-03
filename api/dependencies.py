"""Load the exact legacy modules using their established sibling imports."""
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1] / "medisaathi"
sys.path.insert(0, str(MODULE_DIR))
from ai_integration import AIIntegration, IntegrationError  # noqa: E402
import assistant  # noqa: E402
import reader  # noqa: E402

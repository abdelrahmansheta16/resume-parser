import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


SAMPLE_RESUME_1 = project_root / "data" / "samples" / "sample_resume_1.txt"
SAMPLE_RESUME_2 = project_root / "data" / "samples" / "sample_resume_2.txt"
SAMPLE_JD_1 = project_root / "data" / "samples" / "sample_jd_1.txt"


@pytest.fixture
def sample_resume_text():
    return SAMPLE_RESUME_1.read_text(encoding="utf-8")


@pytest.fixture
def sample_resume_text_2():
    return SAMPLE_RESUME_2.read_text(encoding="utf-8")


@pytest.fixture
def sample_jd_text():
    return SAMPLE_JD_1.read_text(encoding="utf-8")

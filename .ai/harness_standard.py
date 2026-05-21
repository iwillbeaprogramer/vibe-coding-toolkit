#!/usr/bin/env python
from __future__ import annotations

import harness as base


base.PIPELINE_MODE = "standard"
base.PRESETS_DIR = base.ROOT / "presets" / "standard"

base.STAGES = [
    "00_specify",
    "01_develop",
    "02_review",
    "03_fix",
    "04_verify",
]

base.STAGE_OUTPUTS = {
    "00_specify": "00_spec.md",
    "01_develop": "01_dev.md",
    "02_review": "02_review.md",
    "03_fix": "03_fix.md",
    "04_verify": "04_verify.md",
}

base.COMMIT_STAGES = {"01_develop", "03_fix", "04_verify"}
base.NO_COMMIT_STAGES = {"00_specify", "02_review"}

base.START_STAGE = "00_specify"
base.DEVELOP_STAGE = "01_develop"
base.VERIFY_STAGE = "04_verify"
base.VERIFY_RETRY_TARGET_STAGE = "03_fix"
base.FIX_STAGE = "03_fix"
base.DOCUMENT_STAGE = None


if __name__ == "__main__":
    raise SystemExit(base.main())

#!/usr/bin/env python
from __future__ import annotations

import harness as base


base.PIPELINE_MODE = "fast"
base.PRESETS_DIR = base.ROOT / "presets" / "fast"

base.STAGES = [
    "00_specify",
    "01_develop",
    "02_verify",
]

base.STAGE_OUTPUTS = {
    "00_specify": "00_spec.md",
    "01_develop": "01_dev.md",
    "02_verify": "02_verify.md",
}

base.COMMIT_STAGES = {"01_develop", "02_verify"}
base.NO_COMMIT_STAGES = {"00_specify"}

base.START_STAGE = "00_specify"
base.DEVELOP_STAGE = "01_develop"
base.VERIFY_STAGE = "02_verify"
base.VERIFY_RETRY_TARGET_STAGE = "01_develop"
base.FIX_STAGE = None
base.DOCUMENT_STAGE = None


if __name__ == "__main__":
    raise SystemExit(base.main())

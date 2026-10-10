"""Windows: cho ctranslate2 (faster-whisper) tìm thấy DLL CUDA cài qua pip.

pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"  ->  DLL nằm trong site-packages/nvidia/*/bin.
Gọi add() TRƯỚC khi import faster_whisper.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def add() -> None:
    root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for bin_dir in root.glob("*/bin"):
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(bin_dir))

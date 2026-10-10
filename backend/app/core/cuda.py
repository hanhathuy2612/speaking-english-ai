"""Windows: let ctranslate2 (faster-whisper) find the CUDA DLLs installed via pip.

pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"  ->  DLLs live in site-packages/nvidia/*/bin.
Call add_cuda_dlls() BEFORE importing faster_whisper.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def add_cuda_dlls() -> None:
    root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for bin_dir in root.glob("*/bin"):
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(bin_dir))

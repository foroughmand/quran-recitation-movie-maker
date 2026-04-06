from __future__ import annotations

import ctypes
import platform
import subprocess
from pathlib import Path


_HERE = Path(__file__).resolve().parent


def native_library_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return _HERE / "libdp_kernel.dylib"
    if system == "Windows":
        return _HERE / "dp_kernel.dll"
    return _HERE / "libdp_kernel.so"


def build_native_library() -> Path:
    source = _HERE / "dp_kernel.cpp"
    target = native_library_path()
    system = platform.system()
    if system == "Darwin":
        cmd = ["clang++", "-O3", "-std=c++17", "-dynamiclib", "-o", str(target), str(source)]
    elif system == "Windows":
        raise RuntimeError("Windows build is not implemented for dp_kernel yet.")
    else:
        cmd = ["clang++", "-O3", "-std=c++17", "-shared", "-fPIC", "-o", str(target), str(source)]
    subprocess.run(cmd, check=True)
    return target


def load_native_library() -> ctypes.CDLL:
    target = native_library_path()
    if not target.exists():
        raise RuntimeError(
            f"Native DP library is missing at {target}. "
            "Build it first with `python -m quran_aligner.native.dp_kernel` or pass `--state-dp-engine python`."
        )
    library = ctypes.CDLL(str(target))
    library.decode_state_dp_native.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_void_p,
    ]
    library.decode_state_dp_native.restype = ctypes.c_int
    return library


if __name__ == "__main__":
    path = build_native_library()
    print(path)

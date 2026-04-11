"""Private ctypes bindings for BlurlyEngine.dll.

This module is an internal implementation detail.  Do not import directly;
use ``blurly.BlurlyEngine`` instead.
"""

import ctypes
import os
import sys

# ─── Platform Validation ──────────────────────────────────────────────────

if sys.platform != "win32" or sys.getwindowsversion().build < 22000:
    raise ImportError(
        "Blurly requires Windows 11. "
        "Older versions of Windows or non-Windows systems are not supported."
    )

class BlurlyError(Exception):
    """Raised when the native engine reports an error."""


# ─── Locate resources relative to *this* file, not CWD ──────────────────────

_PKG_DIR    = os.path.dirname(os.path.abspath(__file__))
_DLL_PATH   = os.path.join(_PKG_DIR, "bin", "BlurlyEngine.dll")
SHADER_DIR  = os.path.join(_PKG_DIR, "shaders")
ASSETS_DIR  = os.path.join(_PKG_DIR, "assets", "presets")

if not os.path.exists(_DLL_PATH):
    raise FileNotFoundError(
        f"BlurlyEngine.dll not found at: {_DLL_PATH}\n"
        f"Run build_engine.bat to compile the native engine."
    )

_lib = ctypes.CDLL(_DLL_PATH)

# ─── Function signatures ────────────────────────────────────────────────────

# void* Blurly_Create(HWND, const char* shaderDir, const char* normalMapPath)
_lib.Blurly_Create.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
_lib.Blurly_Create.restype  = ctypes.c_void_p

# void Blurly_Destroy(void*)
_lib.Blurly_Destroy.argtypes = [ctypes.c_void_p]
_lib.Blurly_Destroy.restype  = None

# void Blurly_UpdatePosition(void*, int x, int y, int w, int h)
_lib.Blurly_UpdatePosition.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
]
_lib.Blurly_UpdatePosition.restype = None

# void Blurly_SetParams(void*, float refraction, float blur, int type, float frost)
_lib.Blurly_SetParams.argtypes = [
    ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.c_float
]
_lib.Blurly_SetParams.restype = None

# void Blurly_SetConfig(void*, int vsync, int quality, float targetFPS)
_lib.Blurly_SetConfig.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_float
]
_lib.Blurly_SetConfig.restype = None

# bool Blurly_LoadNormalMap(void*, const char* path)
_lib.Blurly_LoadNormalMap.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_lib.Blurly_LoadNormalMap.restype  = ctypes.c_bool

# void Blurly_Render(void*)
_lib.Blurly_Render.argtypes = [ctypes.c_void_p]
_lib.Blurly_Render.restype  = None

# void Blurly_RenderAt(void*, int x, int y, int w, int h)
_lib.Blurly_RenderAt.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
]
_lib.Blurly_RenderAt.restype = None

# const char* Blurly_GetError()
_lib.Blurly_GetError.argtypes = []
_lib.Blurly_GetError.restype  = ctypes.c_char_p

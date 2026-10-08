# SPDX-License-Identifier: GPL-3.0-or-later
"""Run a Pd patch headlessly through a desktop libpd build and measure its output.

Usage from a test script:
    from pdtest import Engine
    e = Engine("path/to/libpd.so", "path/to/patch.pd")
    e.send("gain", 3.0)
    out = e.run(mic_signal)        # mono float array in, (n, 2) float array out

Build libpd for Linux with `make` inside libpd's source folder (see README).
"""
import ctypes, os
import numpy as np

SR = 48000
BLOCK = 64


class Engine:
    _current = None   # libpd is one global instance: only one patch may be open at a time

    def __init__(self, lib_path, patch_path, sr=SR, search_path=()):
        if Engine._current is not None:
            Engine._current.close()
        self.sr = sr
        self.handle = None
        L = self.lib = ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)   # compiled externals need libpd's symbols
        L.libpd_init.restype = ctypes.c_int
        L.libpd_closefile.argtypes = [ctypes.c_void_p]
        L.libpd_init_audio.argtypes = [ctypes.c_int] * 3
        L.libpd_process_float.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
        L.libpd_float.argtypes = [ctypes.c_char_p, ctypes.c_float]
        L.libpd_openfile.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        L.libpd_openfile.restype = ctypes.c_void_p
        L.libpd_start_message.argtypes = [ctypes.c_int]
        L.libpd_add_float.argtypes = [ctypes.c_float]
        L.libpd_finish_message.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.log = []
        self.heard = {}   # receiver name -> list of floats, filled by listen()
        PRINT = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        self._hook = PRINT(lambda m: self.log.append(m.decode(errors="replace").strip()))
        L.libpd_set_printhook.argtypes = [PRINT]
        L.libpd_set_printhook(self._hook)
        L.libpd_init()
        L.libpd_init_audio(1, 2, sr)
        L.libpd_start_message(1)
        L.libpd_add_float(1.0)
        L.libpd_finish_message(b"pd", b"dsp")
        L.libpd_add_to_search_path.argtypes = [ctypes.c_char_p]
        for extra in search_path:   # like PdBase.addToSearchPath: folders every patch can use
            L.libpd_add_to_search_path(os.path.abspath(extra).encode())
        d, f = os.path.split(os.path.abspath(patch_path))
        self.handle = L.libpd_openfile(f.encode(), d.encode())
        if not self.handle:
            raise RuntimeError("could not open patch " + patch_path)
        Engine._current = self

    def listen(self, *names):
        """Record every float sent to the Pd receivers `names` in self.heard[name]."""
        L = self.lib
        FLOAT = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_float)
        self._float_hook = FLOAT(lambda src, x: self.heard.setdefault(src.decode(), []).append(x))
        L.libpd_set_floathook.argtypes = [FLOAT]
        L.libpd_set_floathook(self._float_hook)
        # [route] and friends hand a lone number on as a one-element list, so record those too.
        LIST = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        L.libpd_is_float.argtypes = [ctypes.c_void_p]
        L.libpd_get_float.argtypes = [ctypes.c_void_p]
        L.libpd_get_float.restype = ctypes.c_float
        def on_list(src, argc, argv):
            if argc == 1 and L.libpd_is_float(argv):
                self.heard.setdefault(src.decode(), []).append(L.libpd_get_float(argv))
        self._list_hook = LIST(on_list)
        L.libpd_set_listhook.argtypes = [LIST]
        L.libpd_set_listhook(self._list_hook)
        L.libpd_bind.argtypes = [ctypes.c_char_p]
        L.libpd_bind.restype = ctypes.c_void_p
        self._bound = []
        for name in names:
            self._bound.append(L.libpd_bind(name.encode()))
            self.heard[name] = []

    def close(self):
        if getattr(self, "_bound", None):   # the hook must not outlive its Python callback
            self.lib.libpd_unbind.argtypes = [ctypes.c_void_p]
            for b in self._bound:
                self.lib.libpd_unbind(ctypes.c_void_p(b))
            self.lib.libpd_set_floathook(ctypes.cast(None, type(self._float_hook)))
            self.lib.libpd_set_listhook(ctypes.cast(None, type(self._list_hook)))
            self._bound = None
        if self.handle:
            self.lib.libpd_closefile(ctypes.c_void_p(self.handle))
            self.handle = None
        if Engine._current is self:
            Engine._current = None

    def send(self, name, value):
        self.lib.libpd_float(name.encode(), float(value))

    def send_list(self, name, *values):
        """Send a list of floats to a receiver, like PdBase.sendList."""
        L = self.lib
        L.libpd_start_message(len(values))
        for v in values:
            L.libpd_add_float(float(v))
        L.libpd_finish_list.argtypes = [ctypes.c_char_p]
        L.libpd_finish_list(name.encode())

    def send_msg(self, name, selector, *values):
        """Send `selector v1 v2 ...` to a receiver, like PdBase.sendMessage (floats only)."""
        L = self.lib
        L.libpd_start_message(len(values))
        for v in values:
            L.libpd_add_float(float(v))
        L.libpd_finish_message(name.encode(), selector.encode())

    def run(self, mic):
        """mic: 1-D float32 array; length is rounded down to whole 64-sample blocks."""
        n = (len(mic) // BLOCK) * BLOCK
        mic = np.ascontiguousarray(mic[:n], dtype=np.float32)
        out = np.zeros(n * 2, dtype=np.float32)
        ticks = n // BLOCK
        self.lib.libpd_process_float(ticks, mic.ctypes.data, out.ctypes.data)
        return out.reshape(n, 2)  # interleaved L,R

    def silence(self, seconds):
        return np.zeros(int(seconds * self.sr), dtype=np.float32)

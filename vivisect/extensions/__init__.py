"""
Extensions for vivisect may be implemented as python
modules which contain the function "vivExtension".

All ";" separated directories listed in the VIV_EXT_PATH
environment variable will be searched for ".py" python
modules which implement "vivExtension"

The module's vivExtension function takes a vivisect workspace
(vw) and an vivisect gui reference (if present).
"""

import os
import importlib
import traceback


def loadExtensions(vw, vwgui):
    extdir = os.getenv('VIV_EXT_PATH')
    if extdir is None:
        return

    for dirname in extdir.split(';'):

        if not os.path.isdir(dirname):
            vw.vprint('Invalid VIV_EXT_PATH dir: %s' % dirname)
            continue

        for fname in os.listdir(dirname):
            if not fname.endswith('.py'):
                continue

            # Build code objects from the module files
            try:
                mod = importlib.import_module(fname)
                mod.vivExtension(vw, vwgui)
            except Exception as e:
                vw.vprint(traceback.format_exc())
                vw.vprint('Extension Error: %s' % fname)

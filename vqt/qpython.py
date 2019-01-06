"""Home of some helpers for python interactive stuff.
"""

import io
import sys
import code
import queue
import types
import traceback
from _testcapi import _pending_threadfunc
from threading import Thread

from PyQt5 import QtGui

from vqt.common import *
from vqt.main import idlethread


class VQTerminal(QtWidgets.QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super(VQTerminal, self).__init__(*args, **kwargs)
        self._shcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+p"), self)
        self._shcut.activated.connect(self._on_ce)

    def _on_ce(self):
        self._eval_input()

    class FileCatcher:
        """Cache the stdout text so we can analyze it before returning it
        """

        def __init__(self):
            self.out = []
            self.reset()

        def reset(self):
            self.out.clear()

        def write(self, line):
            self.out.append(line)

        def flush(self):
            output = '\n'.join(self.out)
            self.reset()
            return output

    def _eval_input(self):
        # self._py_in = io.StringIO(self.document().toPlainText())
        # self._py_out = io.StringIO()
        # self._py_err = io.StringIO()
        #
        # self._py_old_in = sys.stdin
        # self._py_old_out = sys.stdout
        # self._py_old_err = sys.stderr
        #

        import os
        sys.stdout.write(self.document().toPlainText())
        # sys.stdout.flush()
        # sys.stderr.flush()

        c = code.InteractiveConsole(locals())
        c.interact()

        self.appendPlainText(self._py_out.read())
        self.appendPlainText(self._py_err.read())
        #
        # sys.stdin = self._py_old_in
        # sys.stdout = self._py_old_out
        # sys.stderr = self._py_old_err


class VQPythonView(QtWidgets.QWidget, Thread):
    def __init__(self, vdb: 'Vdb', vdb_locals=None, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)

        self.name = "PythonViewThread"
        self._vdb = vdb
        self._q = queue.Queue()
        self._quit = False

        if vdb_locals is None:
            vdb_locals = {}
        self._locals = vdb_locals

        self._script_code = VQTerminal(self)

        # self._help_button = QtWidgets.QPushButton('?', self)
        # self._run_button = QtWidgets.QPushButton('Run', self)
        #
        # self._run_button.clicked.connect(self._okClicked)
        # self._help_button.clicked.connect(self._helpClicked)
        # self._help_text = None

        # _b_hbox = HBox()
        # _b_hbox.addWidget(self._run_button)
        # _b_hbox.addWidget(self._help_button)

        vbox = VBox(self)
        vbox.addWidget(self._script_code)
        # vbox.addLayout(_b_hbox)

        self.setWindowTitle('Python Scratch')
        self.start()

    def stop(self):
        self._quit = True

    def run(self):
        while self._quit is False:
            try:
                p_code = self._q.get(timeout=0.100)

                try:
                    vm_code = compile(p_code, "python_scratch_code.py", "exec")
                    exec(vm_code, self._locals)
                    self._vdb.vprint("done")
                except Exception as e:
                    print(traceback.format_exc())

            except queue.Empty:
                pass

    def _okClicked(self):
        self._q.put(str(self._script_code.document().toPlainText()))

    def _helpClicked(self):
        withhelp = []
        for name, val in list(self._locals.items()):
            if type(val) in (types.ModuleType,):
                continue

            doc = getattr(val, '__doc__', '\nNo Documentation\n')
            if doc is None:
                doc = '\nNo Documentation\n'

            withhelp.append((name, doc))
        withhelp.sort()

        txt = 'Objects/Functions in the namespace:\n'
        for name, doc in withhelp:
            txt += ('====== %s\n' % name)
            txt += ('%s\n' % doc)

            self._add_to_output(txt)

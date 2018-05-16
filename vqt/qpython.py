"""Home of some helpers for python interactive stuff.
"""

import io
import sys
import queue
import types
import traceback
from threading import Thread

from PyQt5 import QtGui

from vqt.common import *
from vqt.main import idlethread


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

        self._script_code = QtWidgets.QTextEdit(self)

        self._help_button = QtWidgets.QPushButton('?', self)
        self._run_button = QtWidgets.QPushButton('Run', self)

        self._run_button.clicked.connect(self._okClicked)
        self._help_button.clicked.connect(self._helpClicked)
        self._help_text = None

        _b_hbox = HBox()
        _b_hbox.addWidget(self._run_button)
        _b_hbox.addWidget(self._help_button)

        vbox = VBox()
        vbox.addWidget(self._script_code)
        vbox.addLayout(_b_hbox)
        self.setLayout(vbox)

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

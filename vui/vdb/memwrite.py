import vqt.qt.memwrite as e_qt_mw
import vui.vdb.base
from vqt.main import *


class VdbMemWriteWindow(vui.vdb.base.VdbWidgetWindow):
    def __init__(self, db, dbt, expr='', esize='', parent=None):
        vui.vdb.base.VdbWidgetWindow.__init__(self, db, dbt, parent=parent)

        self.memWriteWidget = e_qt_mw.MemWriteWindow(expr=expr, esize=esize, emu=dbt, parent=parent)
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.memWriteWidget)
        self.setLayout(vbox)

        self.memWriteWidget.writeToMemory.connect(self.writeMemory)
        self.setWindowTitle('Write Memory')

        vqtconnect(self.vdbWriteMem, 'vdb:writemem')

    def vdbWriteMem(self, event, einfo):
        self.vqLoad()

    def vqLoad(self):
        self.memWriteWidget.renderMemory()

    def enviNavGoto(self, expr, esize='', rend=''):
        self.memWriteWidget.setValues(expr, esize)
        self.vqLoad()

    def vqGetSaveState(self):
        expr, esize = self.memWriteWidget.getValues()
        return {'expr': expr, 'esize': esize}

    def vqSetSaveState(self, state):
        self.memWriteWidget.setValues(state.get('expr', ''), state.get('esize', ''))

    def writeMemory(self, expr, hexbytez):
        self.db.do_writemem('-X %s %s' % (expr, hexbytez))

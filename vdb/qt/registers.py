from PyQt4 import QtCore, QtGui

import vdb.qt.base
import vui.qtrace
from vqt.main import *


class VdbRegistersWindow(vdb.qt.base.VdbWidgetWindow):
    def __init__(self, db, dbt, parent=None):
        vdb.qt.base.VdbWidgetWindow.__init__(self, db, dbt, parent=parent)

        self.regsWidget = vui.qtrace.RegistersView(trace=dbt, parent=parent)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.regsWidget)
        self.setLayout(vbox)

        self.setWindowTitle('Registers')

        vqtconnect(self.vqLoad, 'vdb:setregs')
        vqtconnect(self.vqLoad, 'vdb:setthread')

    def vqLoad(self):
        '''
        the widgets in RegistersView already register for notifications.
        '''
        self.regsWidget.reglist.vqLoad()

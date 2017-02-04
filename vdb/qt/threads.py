from PyQt4 import QtCore, QtGui

import vdb.qt.base
import vui.qt


class VdbThreadsWindow(vdb.qt.base.VdbWidgetWindow):
    def __init__(self, db, dbt, parent=None):
        vdb.qt.base.VdbWidgetWindow.__init__(self, db, dbt, parent=parent)

        self.threadWidget = vui.qt.VQThreadsView(trace=dbt, parent=parent)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.threadWidget)
        self.setLayout(vbox)

        self.setWindowTitle('Threads')

    def vqLoad(self):
        """
        the widgets in VQThreadsView already register for notifications.
        """
        self.threadWidget.vqLoad()

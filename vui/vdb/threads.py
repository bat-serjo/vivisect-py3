from PyQt4 import QtGui

import vui.vdb.base
import vui.qtrace


class VdbThreadsWindow(vui.vdb.base.VdbWidgetWindow):
    def __init__(self, db, dbt, parent=None):
        vui.vdb.base.VdbWidgetWindow.__init__(self, db, dbt, parent=parent)

        self.threadWidget = vui.qtrace.VQThreadsView(trace=dbt, parent=parent)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.threadWidget)
        self.setLayout(vbox)

        self.setWindowTitle('Threads')

    def vqLoad(self):
        """
        the widgets in VQThreadsView already register for notifications.
        """
        self.threadWidget.vqLoad()

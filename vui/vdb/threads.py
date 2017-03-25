from PyQt5 import QtWidgets

import vui.vdb.base
import vui.qtrace


class VdbThreadsWindow(vui.vdb.base.VdbWidgetWindow):
    def vqGetSaveState(self):
        pass

    def vqSetSaveState(self, state):
        pass

    def __init__(self, db, dbt, parent=None):
        vui.vdb.base.VdbWidgetWindow.__init__(self, db, dbt, parent=parent)

        self.threadWidget = vui.qtrace.VQThreadsView(trace=dbt, parent=parent)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.threadWidget)
        self.setLayout(vbox)

        self.setWindowTitle('Threads')

    def vqLoad(self):
        """
        the widgets in VQThreadsView already register for notifications.
        """
        self.threadWidget.vqLoad()

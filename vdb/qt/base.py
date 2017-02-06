from PyQt4 import QtGui

import vqt.saveable as vq_save
import vui.qtrace


class VdbWidgetWindow(QtGui.QWidget, vq_save.SaveableWidget, vui.qtrace.VQTraceNotifier):
    """
    a base window class for widgets to inherit from for vdb.
    this gives your window/widget access to the vdb instance (self.db), the gui
    instance (self.db.gui), and the persistent trace object (self.dbt).

    implement vqLoad for tracer events.
    implement vdbUIEvent for events caused by user interaction.
    state between runs of the debugger.
    """

    def __init__(self, db, dbt, parent=None):
        QtGui.QWidget.__init__(self, parent=parent)
        vq_save.SaveableWidget.__init__(self)
        vui.qtrace.VQTraceNotifier.__init__(self, trace=dbt)

        self.db = db
        self.dbt = dbt

    def keyPressEvent(self, event):
        """
        handle the global hotkeys.
        """
        self.db.gui.keyPressEvent(event)

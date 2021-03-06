"""
QtGui objects which assist in GUIs which use vtrace parts.
"""
import traceback

from PyQt5 import QtGui, QtCore, QtWidgets

import envi.memcanvas as e_mcanv
import envi.memcanvas.renderers as e_mem_rend
import vqt.colors as vq_colors
import vqt.qt.memory as envi_qt_memory
import vqt.qt.memorymap as envi_qt_memmap
import vqt.tree as vq_tree
import vtrace

from vqt.main import workthread, idlethread, idlethreadsync
from vtrace.const import *


class VQTraceNotifier(vtrace.Notifier):
    """
    A bit of shared mixin code for the handling of vtrace
    notifier callbacks in various VQTreeViews...
    """

    def __init__(self, trace=None):
        self.trace = trace
        vtrace.Notifier.__init__(self)
        self.trace.registerNotifier(NOTIFY_ALL, self)

    @idlethreadsync
    def notify(self, event, trace):
        if event in [NOTIFY_CONTINUE, NOTIFY_DETACH, NOTIFY_EXIT]:
            self.setEnabled(False)

        else:
            # If the trace is just going to run again, skip the update.
            if not trace.shouldRunAgain():
                self.setEnabled(True)
                self.vqLoad()


class RegisterListModel(envi_qt_memory.EnviNavModel):
    columns = ('Name', 'Hex', 'Dec', 'Best')
    editable = [False, True, True, False]
    register_edited = QtCore.pyqtSignal(QtCore.QModelIndex, QtCore.QVariant)

    def __init__(self, parent=None):
        envi_qt_memory.EnviNavModel.__init__(self, 0, parent=parent)

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return item.data(index.column())

        if role == QtCore.Qt.UserRole:
            return item

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        node = index.internalPointer()
        if not node:
            return False

        if role == QtCore.Qt.EditRole:
            self.register_edited.emit(index, value)

        return True


class RegistersListView(VQTraceNotifier,vq_tree.VQTreeView):
    """
    A pure "list view" object for registers
    """

    def __init__(self, trace=None, parent=None):
        VQTraceNotifier.__init__(self, trace)
        vq_tree.VQTreeView.__init__(self, parent=parent)

        self.descrend = e_mem_rend.AutoBytesRenderer()

        self.setAlternatingRowColors(True)
        # snapped in by someone else.  use a signal instead.
        self.regnames = None
        # used to determine what registers have changed.
        self.lastregs = {}
        self.regvals = {}

        self.setStyleSheet(vq_colors.getDefaultColors())

        model = RegisterListModel(parent=self)
        self.setModel(model)

    def regEdited(self, index, value):
        node = index.internalPointer()
        if not node or not value:
            return False

        expr = str(value.toString())
        try:
            value = self.trace.parseExpression(expr)
        except Exception as e:
            return False

        reg = node.rowdata[0]
        self.trace.setRegisterByName(reg, value)
        regval = self.trace.getRegisterByName(reg)
        # TODO: yuck...implement a "fast" string memorycanvas?
        smc = e_mcanv.StringMemoryCanvas(self.trace)
        self.descrend.render(smc, regval)

        node.rowdata[1] = self.trace.pointerString(regval)
        node.rowdata[2] = regval
        node.rowdata[3] = str(smc)

        return True

    def setModel(self, model):
        model.dataChanged.connect(self.dataChanged)
        model.rowsInserted.connect(self.rowsInserted)
        model.register_edited.connect(self.regEdited)
        return QtWidgets.QTreeView.setModel(self, model)

    def vqLoad(self):
        self.lastregs = self.regvals.copy()
        if not self.trace.isAttached():
            self.setEnabled(False)
            return

        if self.trace.isRunning():
            self.setEnabled(False)
            return

        model = RegisterListModel(parent=self)
        self.setModel(model)

        for rname in self.regnames:
            rval = self.trace.getRegisterByName(rname)
            self.regvals[rname] = rval
            hexva = self.trace.pointerString(rval)

            try:
                # TODO: yuck...implement a "fast" string memorycanvas?
                smc = e_mcanv.StringMemoryCanvas(self.trace)
                self.descrend.render(smc, rval)
            except Exception as e:
                traceback.print_exc()
                smc = repr(e)
            finally:
                model.append((rname, hexva, rval, str(smc)))


class RegColorDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent):
        super(RegColorDelegate, self).__init__(parent)
        self.reglist = parent

    def paint(self, painter, option, index):
        node = index.internalPointer()
        weight = QtGui.QFont.Normal
        if self.reglist.lastregs.get(node.rowdata[0]) != node.rowdata[2]:
            weight = QtGui.QFont.Bold
        option.font.setWeight(weight)
        return QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)


class RegistersView(QtWidgets.QWidget):
    """
    A register view which includes the idea of "sub views" for particular
    sets of registers per-architecture.
    """

    def __init__(self, trace=None, parent=None):
        super(RegistersView, self).__init__(parent=parent)
        self.setWindowTitle('Registers')

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(4)

        self.viewnames = QtWidgets.QComboBox(self)
        self.regviews = {}
        self.flagviews = {}

        reg_groups = trace.archGetRegisterGroups()
        for name, group in reg_groups:
            self.regviews[name] = group
            self.viewnames.addItem(name)

        self.reglist = RegistersListView(trace=trace, parent=self)
        self.regdelegate = RegColorDelegate(self.reglist)
        self.reglist.setItemDelegate(self.regdelegate)
        # TODO: we should switch theme overall to monospace font
        # font = Qt.QFont('Courier New', 10)
        # self.reglist.setFont(font)

        vbox.addWidget(self.viewnames)

        # show general in drop down by default if exists, otherwise all
        # (preferences will re-set)
        if 'general' in self.regviews:
            self.regViewNameSelected('general')
            idx = self.viewnames.findText('general')
            self.viewnames.setCurrentIndex(idx)
        else:
            self.regViewNameSelected('all')
            idx = self.viewnames.findText('all')
            self.viewnames.setCurrentIndex(idx)

        statusreg_widget = VQFlagsGridView(trace=trace, parent=self)
        statusreg_widget.setMaximumHeight(60)
        statusreg_widget.hide()

        splitview = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitview.addWidget(self.reglist)
        splitview.addWidget(statusreg_widget)
        vbox.addWidget(splitview)

        self.viewnames.currentIndexChanged.connect(self._newIndex)

        # self.setLayout(vbox)

    def _newIndex(self, *args):
        self.regViewNameSelected(self.viewnames.currentText())

    def regViewNameSelected(self, name):
        self.reglist.regnames = self.regviews.get(str(name), None)
        self.reglist.vqLoad()


class VQFlagsGridView(VQTraceNotifier, QtWidgets.QWidget):
    """
    Show the state of the status register (if available).
    """

    def __init__(self, trace=None, parent=None):
        QtWidgets.QWidget.__init__(self, parent=parent)
        VQTraceNotifier.__init__(self, trace)

        self.grid = QtWidgets.QGridLayout()
        if not trace.hasStatusRegister():
            return

        self.flags_def = trace.getStatusRegNameDesc()
        self.flags = {}
        self.flag_labels = {}
        for idx, (name, desc) in enumerate(self.flags_def):
            flag_button = QtWidgets.QPushButton(name)
            flag_button.clicked.connect(self.buttonClicked)
            flag_button.setToolTip(desc)

            flag_label = QtWidgets.QLabel('0', self)
            flag_label.setAlignment(QtCore.Qt.AlignCenter)
            self.flag_labels[name] = flag_label

            self.grid.addWidget(flag_button, 0, idx)
            self.grid.addWidget(flag_label, 1, idx)

        self.setLayout(self.grid)
        self.vqLoad()

    def buttonClicked(self):
        obj = self.sender()
        name = str(obj.text().toAscii())

        value = self.trace.getRegisterByName(name)
        if value not in (0, 1):
            raise Exception('unexpected value for status register flag')

        value = not bool(value)
        self.trace.setRegisterByName(name, value)

        self.vqLoad()

    def vqLoad(self):
        if not self.trace.isAttached():
            self.setEnabled(False)
            return

        if self.trace.isRunning():
            self.setEnabled(False)
            return

        if not self.trace.hasStatusRegister():
            self.hide()
            self.setEnabled(False)

        self.show()
        self.flags = self.trace.getStatusFlags()
        for name, desc in self.flags_def:
            self.flag_labels[name].setText(str(self.flags[name]))

        self.update()


class VQProcessListModel(vq_tree.VQTreeModel):
    columns = ('Pid', 'Name')


class VQProcessListView(vq_tree.VQTreeView):
    def __init__(self, trace=None, parent=None):
        vq_tree.VQTreeView.__init__(self, parent=parent)
        if trace is None:
            trace = vtrace.getTrace()
        self.trace = trace

        model = VQProcessListModel(parent=self)
        self.setModel(model)
        self.setAlternatingRowColors(True)

        for pid, name in self.trace.ps():
            model.append((pid, name))


class VQProcessSelectDialog(QtWidgets.QDialog):
    def __init__(self, trace=None, parent=None):
        super(VQProcessSelectDialog, self).__init__(parent=parent)

        self.pid = None

        self.setWindowTitle('Select a process...')

        vlyt = QtWidgets.QVBoxLayout()
        hlyt = QtWidgets.QHBoxLayout()

        self.plisttree = VQProcessListView(trace=trace, parent=self)

        hbox = QtWidgets.QWidget(parent=self)

        ok = QtWidgets.QPushButton("Ok", parent=hbox)
        cancel = QtWidgets.QPushButton("Cancel", parent=hbox)

        self.plisttree.doubleClicked.connect(self.dialog_activated)

        ok.clicked.connect(self.dialog_ok)
        cancel.clicked.connect(self.dialog_cancel)

        hlyt.addStretch(1)
        hlyt.addWidget(cancel)
        hlyt.addWidget(ok)
        hbox.setLayout(hlyt)

        vlyt.addWidget(self.plisttree)
        vlyt.addWidget(hbox)
        self.setLayout(vlyt)

        self.resize(800, 600)

    def dialog_activated(self, idx):
        node = idx.internalPointer()
        if node:
            self.pid = node.rowdata[0]
            self.accept()

    def dialog_ok(self):
        for idx in self.plisttree.selectedIndexes():
            node = idx.internalPointer()
            if node:
                self.pid = node.rowdata[0]
                break
        self.accept()

    def dialog_cancel(self):
        self.reject()


@idlethreadsync
def getProcessPid(trace=None, parent=None):
    d = VQProcessSelectDialog(trace=trace, parent=parent)
    r = d.exec_()
    return d.pid


class FileDescModel(vq_tree.VQTreeModel):
    columns = ('Fd', 'Type', 'Name')


class VQFileDescView(VQTraceNotifier, vq_tree.VQTreeView):
    def __init__(self, trace, parent=None):
        VQTraceNotifier.__init__(self, trace)
        vq_tree.VQTreeView.__init__(self, parent=parent)

        self.setWindowTitle('File Descriptors')
        self.setModel(FileDescModel(parent=self))
        self.vqLoad()

    def vqLoad(self):

        if not self.trace.isAttached():
            self.setEnabled(False)
            return

        if self.trace.isRunning():
            self.setEnabled(False)
            return

        model = FileDescModel(parent=self)
        for fd, fdtype, bestname in self.trace.getFds():
            model.append((fd, fdtype, bestname))
        self.setModel(model)


class VQTraceToolBar(QtWidgets.QToolBar, vtrace.Notifier):
    def __init__(self, trace, parent=None):
        QtWidgets.QToolBar.__init__(self, parent=parent)
        vtrace.Notifier.__init__(self)
        self.trace = trace

        self.setObjectName('VtraceToolbar')

        self.attach_action = self.addAction('attach')
        self.attach_action.setToolTip('Attach to a process')
        self.attach_action.triggered.connect(self.actAttach)

        self.detach_action = self.addAction('detach')
        self.detach_action.setToolTip('Detach from current process')
        self.detach_action.triggered.connect(self.actDetach)

        self.continue_action = self.addAction('continue')
        self.continue_action.setToolTip('Continue current process')
        self.continue_action.triggered.connect(self.actContinue)

        self.break_action = self.addAction('break')
        self.break_action.setStatusTip('Break current process')
        self.break_action.triggered.connect(self.actBreak)

        self.stepi_action = self.addAction('stepi')
        self.stepi_action.setToolTip('Single step the current process')
        self.stepi_action.triggered.connect(self.actStepi)

        self.stepover_action = self.addAction('stepover')
        self.stepover_action.setToolTip('step over current instruction')
        self.stepover_action.triggered.connect(self.actStepover)

        trace.registerNotifier(NOTIFY_ALL, self)
        self._updateActions(trace.isAttached(), trace.isRunning())

    def actAttach(self, *args, **kwargs):
        pid = getProcessPid(trace=self.trace)
        if pid is not None:
            workthread(self.trace.attach)(pid)

    @workthread
    def actDetach(self, thing):
        if self.trace.isAttached():
            self.trace.detach()

    @workthread
    def actContinue(self, thing):
        self.trace.run()

    @workthread
    def actBreak(self, thing):
        if self.trace.getMeta('PendingBreak'):
            return
        self.trace.setMeta('PendingBreak', True)
        self.trace.sendBreak()

    @workthread
    def actStepi(self, thing):
        self.trace.stepi()

    def actStepover(self, thing):
        # TODO: move step over into vtrace instead of vdb?
        raise Exception('no stepover for vtrace. :(')

    @idlethread
    def _updateActions(self, attached, running):
        if not attached:
            self.attach_action.setEnabled(True)
            self.detach_action.setEnabled(False)
            self.continue_action.setEnabled(False)
            self.break_action.setEnabled(False)
            self.stepi_action.setEnabled(False)
            self.stepover_action.setEnabled(False)
        else:
            if running:
                self.attach_action.setEnabled(False)
                self.detach_action.setEnabled(False)
                self.continue_action.setEnabled(False)
                self.break_action.setEnabled(True)
                self.stepi_action.setEnabled(False)
                self.stepover_action.setEnabled(False)
            else:
                self.attach_action.setEnabled(False)
                self.detach_action.setEnabled(True)
                self.continue_action.setEnabled(True)
                self.break_action.setEnabled(True)
                self.stepi_action.setEnabled(True)
                self.stepover_action.setEnabled(True)

    def notify(self, event, trace):
        if event == NOTIFY_DETACH:
            self._updateActions(False, False)

        elif event == NOTIFY_CONTINUE:
            self._updateActions(True, True)

        else:
            self._updateActions(trace.isAttached(), trace.shouldRunAgain())


class VQMemoryMapView(VQTraceNotifier, envi_qt_memmap.VQMemoryMapView):
    """
    A memory map view which is sensitive to the status of a
    trace object.
    """

    def __init__(self, trace, parent=None):
        VQTraceNotifier.__init__(self, trace)
        envi_qt_memmap.VQMemoryMapView.__init__(self, trace, parent=parent)

    def vqLoad(self):
        if not self.trace.isAttached():
            self.setEnabled(False)
            return

        if self.trace.isRunning():
            self.setEnabled(False)
            return

        super(VQMemoryMapView, self).vqLoad()
        self.vqSizeColumns()


class VQThreadListModel(vq_tree.VQTreeModel):
    columns = ('Thread Id', 'Thread Info', 'State')


class VQThreadsView(VQTraceNotifier, vq_tree.VQTreeView):
    def __init__(self, trace=None, parent=None, selectthread=None):
        # selectthread is an optional endpoint to connect to
        VQTraceNotifier.__init__(self, trace)
        vq_tree.VQTreeView.__init__(self, parent=parent)

        self.setWindowTitle('Threads')
        self.setModel(VQThreadListModel(parent=self))
        self.setAlternatingRowColors(True)
        self.vqLoad()
        self.selectthread = selectthread

    # def selectionChanged(self, selected, deselected):
    #     try:
    #         idx = self.selectedIndexes()[0]
    #         node = idx.internalPointer()
    #         if node:
    #             self.trace.selectThread(node.rowdata[0])
    #
    #         # return vq_tree.VQTreeView.selectionChanged(self, selected, deselected)
    #     except Exception as e:
    #         traceback.print_exc()
    #
    #     return vq_tree.VQTreeView.selectionChanged(self, selected, deselected)

    def vqLoad(self):

        if not self.trace.isAttached():
            self.setEnabled(False)
            return

        if self.trace.isRunning():
            self.setEnabled(False)
            return

        model = VQThreadListModel(parent=self)

        stid = self.trace.getMeta('ThreadId')
        for i, (tid, tinfo) in enumerate(self.trace.getThreads().items()):
            state = ''
            if self.trace.isThreadSuspended(tid):
                state = 'suspended'
            model.append((tid, tinfo, state))

        self.setModel(model)

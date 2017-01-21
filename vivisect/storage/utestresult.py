
import traceback

from envi import memcanvas
from vivisect import const
from vivisect import VivWorkspace

utest_header = '#VIVISECT UNIT TEST RESULT FILE.\n'


def saveWorkspaceChanges(vw, filename: str):
    elist = vw.exportWorkspaceChanges()
    if len(elist):
        vivEventsToFile(filename, elist, mode='a', vw=vw)


def vivEventsAppendFile(filename: str, events: list):
    if len(events):
        vivEventsToFile(filename, events, mode='a')


def saveWorkspace(vw: VivWorkspace, filename: str):
    _get_function_data(vw)
    events = vw.exportWorkspace()
    vivEventsToFile(filename, events, mode='w', vw=vw)


def loadWorkspace(vw: VivWorkspace, filename: str):
    raise Exception("This storage module does not support importing of workspace.")


def _get_function_data(vw: VivWorkspace):
    all_funcs_va = vw.getFunctions()
    all_funcs_va = sorted(all_funcs_va)

    str_canvas = memcanvas.StringMemoryCanvas(vw)

    for fva in all_funcs_va:
        f_meta = vw.getFunctionMetaDict(fva)
        meta_keys = sorted(f_meta.keys())
        f_name = vw.getName(fva)

        str_canvas.addText('Function: %s\n' % f_name)
        for m_key in meta_keys:
            str_canvas.addText("\t%s: %s\n" % (str(m_key), str(f_meta[m_key])))

        for cbva, cbsize, cbfva in vw.getFunctionBlocks(fva):

            finalva = cbva + cbsize
            while cbva < finalva:
                opcode = vw.parseOpcode(cbva, const.LOC_OP)
                opcode.render(str_canvas)
                str_canvas.addText("\n")
                cbva += opcode.size

        str_canvas.addText('\n')

    return str_canvas.strval


def vivEventsToFile(filename: str, events: list, mode='w', vw: VivWorkspace=None):
    try:

        event_dict = dict()
        for event in events:
            l = event_dict.get(event[0])
            if l is None:
                event_dict[event[0]] = list()

            event_dict[event[0]].append(event[1])

        with open(filename, mode=mode) as f:
            # Mime type for the basic workspace
            f.write(utest_header)

            if vw is not None:
                f.write(_get_function_data(vw))

            # [const.VWE_ADDMODULE, const.VWE_ADDLOCATION, const.VWE_ADDCODEBLOCK,
            #  const.VWE_ADDFUNCTION, const.VWE_SETFUNCMETA, const.VWE_SETFUNCARGS]:
            for action, l in event_dict.items():

                # We don't want this for now!
                if action == const.VWE_ADDMMAP:
                    continue

                try:
                    # l = event_dict[action]
                    f.write("Action: " + str(action))
                    l = sorted(l, key=lambda x: x[0])

                    for e in l:
                        f.write(str(e))
                        f.write('\n')

                except Exception as e:
                    traceback.print_exc()

    except Exception as e:
        traceback.print_exc()


import json
import traceback

from vivisect import const
from vivisect import VivWorkspace

utest_header = '#VIVISECT UNIT TEST RESULT FILE.'


def saveWorkspaceChanges(vw, filename: str):
    elist = vw.exportWorkspaceChanges()
    if len(elist):
        vivEventsToFile(filename, elist, mode='a')


def vivEventsAppendFile(filename: str, events: list):
    if len(events):
        vivEventsToFile(filename, events, mode='a')


def saveWorkspace(vw: VivWorkspace, filename: str):
    events = vw.exportWorkspace()
    vivEventsToFile(filename, events, mode='w')


def loadWorkspace(vw: VivWorkspace, filename: str):
    raise Exception("This storage module does not support importing of workspace.")


def vivEventsToFile(filename: str, events: list, mode='w'):
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

            # [const.VWE_ADDMODULE, const.VWE_ADDLOCATION, const.VWE_ADDCODEBLOCK,
            #  const.VWE_ADDFUNCTION, const.VWE_SETFUNCMETA, const.VWE_SETFUNCARGS]:
            for action, l in event_dict.items():
                if action == 20:
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

            # for event in events:
            #
            #     try:
            #         json.dump(event, f)
            #     except Exception as e:
            #         print(event)
            #         traceback.print_exc()
    except Exception as e:
        traceback.print_exc()

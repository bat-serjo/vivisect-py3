import json
import traceback

import vivisect


utest_header = '# VIVISECT UNIT TEST FILE DUMP.\n'


def saveWorkspaceChanges(vw, filename):
    elist = vw.exportWorkspaceChanges()
    if len(elist):
        with open(filename, 'a') as f:
            json.dump(elist, f)


def saveWorkspace(vw, filename):
    events = vw.exportWorkspace()
    vivEventsToFile(filename, events)


def vivEventsAppendFile(filename, events):
    with open(filename, 'a') as f:
        # Mime type for the basic workspace
        json.dump(events, f)


def vivEventsToFile(filename, events):
    try:
        with open(filename, 'w') as f:
            # Mime type for the basic workspace
            f.write(utest_header)
            for event in events:
                try:
                    json.dump(event, f)
                except Exception as e:
                    print(event)
                    traceback.print_exc()
    except Exception as e:
        traceback.print_exc()


def vivEventsFromFile(filename):
    with open(filename, "r") as f:
        hdr = f.read(len(utest_header))

        # check for various viv serial formats
        if hdr != utest_header:
            raise Exception("This is not a vivisect unit test dump file.")

        events = []
        # Incremental changes are saved to the file by appending more pickled
        # lists of exported events
        while True:
            try:
                events.extend(json.load(f))
            except EOFError as e:
                break
            except Exception as e:
                traceback.print_exc()
                raise vivisect.InvalidWorkspace(filename, "invalid unit test result file")

    return events


def loadWorkspace(vw, filename):
    events = vivEventsFromFile(filename)
    vw.importWorkspace(events)
    return

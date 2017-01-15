import envi
import vivisect


def analyze(vw):
    for nva, name in vw.getNames():
        if nva & 1 == 0: continue

        mmap = vw.getMemoryMap(nva)
        if mmap is None: continue
        mva, msz, mperms, mname = mmap

        loctup = vw.getLocation(nva)
        if loctup is None:
            print("DEBUG: name where loctup == None: %x: %s" % (nva, name))

        lva, lsz, ltype, ltinfo = loctup
        if ltype != vivisect.LOC_OP: continue

        vw.makeName(nva, None)
        vw.makeName(lva, name + "_thumb")


#if globals().get('argv') != None:
if globals().get('vw') is not None:
    analyze(vw)

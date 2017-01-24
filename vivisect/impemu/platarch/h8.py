import varchs.h8 as e_h8
from varchs.h8.emu import H8Emulator
import vivisect.impemu.emulator as v_i_emulator


class H8WorkspaceEmulator(v_i_emulator.WorkspaceEmulator, H8Emulator):
    taintregs = [
        e_h8.REG_ER0, e_h8.REG_ER1, e_h8.REG_ER2,
    ]

    def __init__(self, vw, logwrite=False, logread=False):
        e_h8.H8Emulator.__init__(self)
        v_i_emulator.WorkspaceEmulator.__init__(self, vw, logwrite=logwrite, logread=logread)

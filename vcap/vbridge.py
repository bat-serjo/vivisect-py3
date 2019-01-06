"""
Capstone to vivisect disassembler bridge.

Tries to mimic vivisect disassembler framework
as close as possible. That means provide all necessary
API for the: memory canvas, debugger, emulator and symbolics
to properly operate.

"""

import envi
import capstone


# vivisect natively supported architectures
ARCH_DEFAULT     = 0 << 16   # arch 0 is whatever the mem object has as default
ARCH_I386        = 1 << 16
ARCH_AMD64       = 2 << 16
ARCH_ARMV7       = 3 << 16
ARCH_THUMB16     = 4 << 16
ARCH_THUMB       = 5 << 16
ARCH_MSP430      = 6 << 16
ARCH_H8          = 7 << 16
ARCH_MASK        = 0xffff0000   # Masked into IF_FOO and BR_FOO values

d = {
    ARCH_DEFAULT: (capstone.CS_ARCH_X86, capstone.CS_MODE_32),  # todo: fix me!
    ARCH_I386: (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
    ARCH_AMD64: (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
    ARCH_ARMV7: (capstone.CS_ARCH_ARM, capstone.CS_MODE_32),
    ARCH_THUMB16: (capstone.CS_ARCH_ARM, capstone.CS_MODE_16),
    ARCH_THUMB: (capstone.CS_ARCH_ARM, capstone.CS_MODE_32),

    # these are unique for vivisect capstone don't have them
    # ARCH_MSP430 : None,
    # ARCH_H8 : None,
}


def v2c_arch(v_arch):
    return d[v_arch]


class CapstoneOpcode(envi.Opcode):

    def __init__(self, cs_op, *args, **kwargs):
        self.cs_op = cs_op
        super(CapstoneOpcode, self).__init__(*args, **kwargs)


dis = None


def __get_cached_dis(arch):
    global dis
    if dis is None:
        dis = capstone.Cs(*v2c_arch(arch))
    return dis


class x86Opcode(envi.Operand):

    def __init__(self, cap_op: capstone.x86.X86Op, *args, **kwargs):
        self._cap_op = cap_op
        super(x86Opcode, self).__init__(*args, **kwargs)

    def isDeref(self):
        """If the given operand will dereference memory, this method must return True.
        """
        return self._cap_op.type  == capstone.x86.X86_OP_MEM

    def isImmed(self):
        """If the given operand represents an immediate value, this must return True.
        """
        return self._cap_op.type  == capstone.x86.X86_OP_IMM

    def isReg(self):
        """If the given operand represents a register value, this must return True.
        """
        return self._cap_op.type  == capstone.x86.X86_OP_REG

    def isDiscrete(self):
        """If the given operand can be completely resolved without an emulator, return True.
        """
        return False

    def getOperValue(self, op, emu=None):
        """
        Get the current value for the operand.  If needed, use
        the given emulator/workspace/trace to resolve things like
        memory and registers.

        NOTE: This API may be passed a None emu and should return what it can
              (or None if it can't be resolved)
        """

        return self._cap_op.value.imm

    def repr(self, op):
        """
        Used by the Opcode class to get a humon readable string for this operand.
        """
        r = str(self._cap_op)

        if self._cap_op.type == capstone.x86.X86_OP_REG:
            r = op.cs_op.reg_name(self._cap_op.reg)

        if self._cap_op.type == capstone.x86.X86_OP_IMM:
            r = hex(self._cap_op.imm)

        if self._cap_op.type == capstone.x86.X86_OP_MEM:
            if self._cap_op.mem.segment != 0:
                r = "segment: " + op.cs_op.reg_name(self._cap_op.mem.segment)
            if self._cap_op.mem.base != 0:
                r = "base: " + op.cs_op.reg_name(self._cap_op.mem.base)
            if self._cap_op.mem.index != 0:
                r = "index: " + op.cs_op.reg_name(self._cap_op.mem.index)
            if self._cap_op.mem.scale != 1:
                r = "scale: %X" % self._cap_op.mem.scale
            if self._cap_op.mem.disp != 0:
                r = "disp: %X" % self._cap_op.mem.disp

        return r


def parseOpcode(self, va, arch=ARCH_DEFAULT) -> envi.Opcode:
    b = self.readMemory(va, 16)

    ds = __get_cached_dis(arch)
    ds.detail = True

    cap_instructions = ds.disasm(b, va)

    """
    constructor for the basic Envi Opcode object.  Arguments as follows:

    va       - The virtual address the instruction lives at (used for PC relative immediates etc...)
    opcode   - An architecture specific numerical value for the opcode
    mnem     - A humon readable mnemonic for the opcode
    prefixes - a bitmask of architecture specific instruction prefixes
    size     - The size of the opcode in bytes
    operands - A list of Operand objects for this opcode
    iflags   - A list of Envi (architecture independent) instruction flags (see IF_FOO)

    NOTE: If you want to create an architecture spcific opcode, I'd *highly* recommend you
          just copy/paste in the following simple initial code rather than calling the parent
          constructor.  The extra
    """

    for c_ins in cap_instructions:
        # c_ins = capstone.CsInsn()

        l = [x86Opcode(op) for op in c_ins.operands]
        import copy
        o = CapstoneOpcode(c_ins,
                           c_ins.address,
                           c_ins.bytes,
                           c_ins.mnemonic,
                           0,  # TODO: ADD PREFIXES,
                           c_ins.size,
                           l,  # [   # TODO: OPERANDS
                           # ],
                           0,  # TODO: IFLAGS
                           )

        # yes we have to return only one instruction even though we might have parsed more
        return o



"""
A module to contain code flow analysis for envi opcode objects...
"""

import copy
import traceback

import envi
import envi.memory as e_mem


class CodeFlowContext(object):
    """
    A CodeFlowContext is used for code-flow (not linear) based disassembly
    for an envi MemoryObject (which is responsible for knowing the
    implementation of parseOpcode().  The CodeFlowContext will optionally
    notify several callback handlers for different events which occur during
    disassembly:

    self._cb_opcode(va, op, branches) - called for every newly parsed opcode
        NOTE: _cb_opcode must return the desired branches for continued flow

    self._cb_function(fva, metadict) - called once for every function

    self._cb_branchtable(tabva, ptrva, destva) - called for switch tables
        NOTE: Return False to stop iteration of pointers

    Set exptable=True to expand branch tables in this phase
    Set persist=True to never disasm the same thing twice
    Set recurse=True to automatically code flow to nested functions
    """

    def __init__(self, mem, persist=False, exptable=True, recurse=True):

        self._funcs = {}
        self._fcalls = {}
        self._mem = mem
        self._cf_noret = {}  # noret funcs
        self._cf_noflow = {}  # va's to stop on

        # A few options to the codeflow object
        self._cf_persist = None
        if persist:
            self._cf_persist = {}

        self._cf_recurse = recurse
        self._cf_exptable = exptable
        self._cf_blocks = []
        self._dynamic_branch_handlers = []

    def _cb_opcode(self, va, op, branches):
        """
        Extend CodeFlowContext and implement this method to recieve
        a callback for every newly discovered opcode.
        """
        return branches

    def _cb_function(self, fva, fmeta):
        """
        Extend CodeFlowContext and implement this method to recieve
        a callback for every newly discovered function.  Additionally,
        metadata about the function may be stored in the fmeta dict.
        """
        pass

    def _cb_noflow(self, va, tva):
        """
        Implement this method to receive a callback when a given code
        branch is skipped due to being in the noflow dictionary.
        ( likely due to prodedural branch to noreturn address )
        """
        pass

    def _cb_branchtable(self, tableva, ptrva, destva):
        """
        Extend CodeFlowContext and implement this method to receive
        a callback for every conditional branch in a discovered
        "branch table" ( think jump/switch cases ).
        tableva     - The base address of the table
        ptrva       - The address of the pointer for this index
        destva      - The destination address (deref of ptrva)

        Return False to stop table iteration.
        """
        pass

    def _cb_dynamic_branch(self, va, op, bflags, branches):
        """
        if codeflow finds a branch to a non-discrete value (eg. to a register)
        we handle it here.  by default, we simply track the dynamic branch in a global
        VaSet which is added to every workspace.

        When code-flow analysis runs into an indirect branch it doesn't know
        what to do with, the architecture can take a crack at it.
        """
        for cb in self._dynamic_branch_handlers:
            cb(self, op, self._mem, bflags, branches)

    def addNoReturnAddr(self, va):
        """
        Add a virtual address to the list of VAs that are non-returning
        procedural branch targets.
        """
        self._cf_noret[va] = True

    def addNoFlow(self, va, destva):
        """
        Add a va->destva no-flow entry which will prevent codeflow from
        continuing to destva as a result of va ( destva may still be
        decoded as a result of being reached some other way... )
        """
        self._cf_noflow[(va, destva)] = True

    def getCallsFrom(self, fva):
        return self._fcalls.get(fva)

    def addFunctionDef(self, fva, calls_from):
        """
        Add a priori knowledge of a function to the code flow
        stuff...
        """
        self._fcalls[fva] = calls_from

    def addCodeFlow(self, va, arch=envi.ARCH_DEFAULT):
        """
        Do code flow disassembly from the specified address.  Returnes a list
        of the procedural branch targets discovered during code flow...

        Set persist=True to store 'opdone' and never disassemble the same thing twice
        """
        opdone = {}
        if self._cf_persist is not None:
            opdone = self._cf_persist

        calls_from = {}
        optodo = [((0, va), arch), ]
        startva = va
        self._cf_blocks.append(va)
        cf_eps = set()
        while len(optodo):

            todo, arch = optodo.pop()

            if self._cf_noflow.get(todo):
                self._cb_noflow(*todo)
                continue

            pva, va = todo
            if opdone.get(va):
                continue

            opdone[va] = True

            try:
                op = self._mem.parseOpcode(va, arch=arch)
            except envi.InvalidInstruction as e:
                traceback.print_exc()
                print('parseOpcode error at 0x%.8x: %s' % (va, e))
                continue
            except Exception as e:
                traceback.print_exc()
                print('parseOpcode error at 0x%.8x: %s' % (va, e))
                continue

            branches = op.getBranches()
            # The opcode callback may filter branches...
            branches = self._cb_opcode(va, op, branches)

            while len(branches):

                bva, bflags = branches.pop()

                # look for dynamic branches (ie. branches which don't have a known target).  assume at least one branch
                if bva is None:
                    self._cb_dynamic_branch(va, op, bflags, branches)

                # add block as part of our call stack
                self._cf_blocks.append(bva)

                try:
                    # Handle a table branch by adding more branches...
                    if bflags & envi.BR_TABLE:
                        if self._cf_exptable:
                            ptrbase = bva
                            bdest = self._mem.readMemoryFormat(ptrbase, '<P')[0]
                            tabdone = {}
                            while self._mem.isValidPointer(bdest):

                                if self._cb_branchtable(bva, ptrbase, bdest) is False:
                                    break

                                if not tabdone.get(bdest):
                                    tabdone[bdest] = True
                                    branches.append((bdest, envi.BR_COND))

                                ptrbase += self._mem.psize
                                bdest = self._mem.readMemoryFormat(ptrbase, '<P')[0]
                        continue

                    if bflags & envi.BR_DEREF:

                        if not self._mem.probeMemory(bva, self._mem.psize, e_mem.MM_READ):
                            continue

                        # Before we update bva, lets check if its in noret...
                        if self._cf_noret.get(bva):
                            self.addNoFlow(va, va + len(op))

                        bva = self._mem.readMemoryFormat(bva, '<P')[0]

                    if not self._mem.probeMemory(bva, 1, e_mem.MM_EXEC):
                        continue

                    if bflags & envi.BR_PROC:

                        # Record that the current code flow has a call from it
                        # to the branch target...
                        nextva = va + len(op)

                        if bva != nextva:  # NOTE: avoid call 0 constructs

                            # Now we decend so we do deepest func callbacks first!
                            if self._cf_recurse:
                                if bva in self._cf_blocks:
                                    # the function that we want to make prodcedural
                                    # called us so we can't call to make it procedural
                                    # until its done
                                    cf_eps.add(bva)
                                else:
                                    self.addEntryPoint(bva)

                            if self._cf_noret.get(bva):
                                # then our next va is noflow!
                                self._cf_noflow[(va, nextva)] = True

                            calls_from[bva] = True

                            # We only go up to procedural branches, not across
                            continue
                finally:
                    self._cf_blocks.pop()

                if not opdone.get(bva):
                    optodo.append(((va, bva), bflags))

        # remove our local blocks from global block stack
        self._cf_blocks.pop()
        while cf_eps:
            fva = cf_eps.pop()
            if not self._mem.isFunction(fva):
                self.addEntryPoint(fva, arch=arch)

        return list(calls_from.keys())

    def addEntryPoint(self, va, arch=envi.ARCH_DEFAULT):
        """
        Analyze the given procedure entry point and flow downward
        to find all subsequent code blocks and procedure edges.

        Example:
            cf.addEntryPoint( 0x77c70308 )
            ... callbacks flow along ...
        """
        # Check if this is already a known function.
        if self._funcs.get(va) is not None:
            return

        # Add this function to known functions
        self._funcs[va] = True
        calls_from = self.addCodeFlow(va, arch=arch)
        self._fcalls[va] = calls_from

        # Finally, notify the callback of a new function
        self._cb_function(va, {'CallsFrom': calls_from})

    def addDynamicBranchHandler(self, cb):
        """
        Add a callback handler for dynamic branches the code-flow resolver
        doesn't know what to do with
        """
        if cb in self._dynamic_branch_handlers:
            raise Exception("Already have this handler (%s) for dynamic branches" % repr(cb))

        self._dynamic_branch_handlers.append(cb)

"""
The vivisect CLI.
"""

import pprint
import socket
from getopt import getopt

import vtrace
import vivisect
import vivisect.vamp as viv_vamp
import vivisect.vector as viv_vector
import vivisect.reports as viv_reports

# FIXME modular arch specific commands!

import vivisect.tools.fscope as v_t_fscope
import vivisect.tools.graphutil as v_t_graph

import visgraph.pathcore as vg_path

import vtrace.envitools as vt_envitools

import vdb

import envi.cli as e_cli
import envi.expression as e_expr
import envi.memcanvas.renderers as e_render

from vqt.main import *
from vivisect.const import *
import vivisect.renderers as viv_rend


class VivCli(e_cli.EnviCli, vivisect.VivWorkspace):

    def __init__(self):
        e_cli.EnviCli.__init__(self, self, symobj=self)
        vivisect.VivWorkspace.__init__(self)
        self.canvas.addRenderer("bytes", e_render.ByteRend())
        self.canvas.addRenderer("u_int_16", e_render.ShortRend())
        self.canvas.addRenderer("u_int_32", e_render.LongRend())
        self.canvas.addRenderer("u_int_64", e_render.QuadRend())
        self.canvas.addRenderer("viv", viv_rend.WorkspaceRenderer(self))
        self.prompt = "viv> "
        self.addScriptPathEnvVar('VIV_SCRIPT_PATH')

    def getExpressionLocals(self):
        l = e_cli.EnviCli.getExpressionLocals(self)
        l['vw'] = self
        l['vprint'] = self.vprint
        l['vivisect'] = vivisect
        return l

    def do_report(self, line):
        """
        Fire a report module by python path name.

        Usage: report <python.path.to.report.module>
        """
        if not line:
            self.vprint("Report Modules")
            for descr, modname in viv_reports.listReportModules():
                self.vprint("%32s %s" % (modname, descr))
            return

        mod = self.loadModule(line)
        cols, results = mod.report(self)
        for row in results:
            for i in range(len(cols)+1):
                val = row[i]
                if i == 0:
                    name = self.arch.pointerString(val)
                    self.canvas.addVaText(name, val)

                else:
                    self.canvas.addText(": %s" % val)

        for va, pri, info in mod.report(self):
            name = self.getName(va)
            if name is None:
                name = self.arch.pointerString(va)
            self.canvas.addVaText(name, va)
            self.canvas.addText(": %s\n" % info)

    def do_pathcount(self, line):
        """
        Mostly for testing the graph stuff... this will likely be removed.

        (does not count paths with loops currently...)

        Usage: pathcount <func_expr>
        """
        fva = self.parseExpression(line)
        if not self.isFunction(fva):
            self.vprint('Not a function!')
            return

        g = v_t_graph.buildFunctionGraph(self, fva)
        # Lets find the "bottom" nodes...
        endblocks = []
        for nid, ninfo in g.getNodes():
            if len(g.getRefsFrom(nid)) == 0:
                endblocks.append((nid, ninfo))

        for nid, ninfo in endblocks:
            paths = list(g.pathSearch(0, toid=nid))
            self.vprint('paths to 0x%.8x: %d' % (ninfo.get('cbva'), len(paths)))

    def do_symboliks(self, line):
        """
        Use the new symboliks subsystem. (NOTE: i386 only for a bit...)

        Usage: symboliks [ options ]

        -A  Run the emu and show the state of the machine for all found paths
            to the given address

        """

        watchaddr = None

        argv = e_cli.splitargs(line)
        try:
            opts, argv = getopt(argv, 'A:')
        except Exception as e:
            return self.do_help('symboliks')

        for opt, optarg in opts:
            if opt == '-A':
                watchaddr = self.parseExpression(optarg)

        va = self.parseExpression(argv[0])
        fva = self.getFunction(va)

        import vivisect.symboliks as viv_symboliks
        import vivisect.symboliks.common as sym_common
        import vivisect.symboliks.effects as viv_sym_effects
        import vivisect.symboliks.analysis as vsym_analysis
        import vivisect.symboliks.archs.i386 as viv_sym_i386

        symctx = vsym_analysis.getSymbolikAnalysisContext(self)

        #xlate = viv_sym_i386.i386SymbolikTranslator(self)
        #graph = viv_symboliks.getSymbolikGraph(self, fva, xlate)

        for emu, effects in symctx.getSymbolikPaths(fva):

            self.vprint('PATH %s' % ('='*60))

            #esp = emu.solveExpression('esp', update=False)

            for eff in effects:

                eff.reduce(emu)
                if eff.efftype in (EFFTYPE_CONSTRAIN,EFFTYPE_CALLFUNC):
                    self.vprint(str(eff))

            #for reg in ['eax','ebx','ecx','edx','esi','edi','ebp','esp','eip']:
                #regobj = emu.getSymVariable(reg)
                #if regobj == None:
                    #continue
                #regobj = regobj.reduce()
                #regval = regobj.solve(emu=emu)
                #if regval == emu.solveExpression(reg, update=False):
                    #continue
                #self.vprint('%s: %s 0x%.8x' % (reg, regobj.reduce(), regobj.solve(emu)))

            for addrsym,valsym in list(emu._sym_mem.values()):
                addrsym = addrsym.reduce(emu=emu)
                valsym = valsym.reduce(emu=emu)
                if emu.isLocalMemory(addrsym):
                    continue
                self.vprint('[ %s ] = %s' % (addrsym, valsym))

            #print 'SPDELTA: %d' % (emu.solveExpression('esp')-esp)
            #print 'RETURN',emu.parseExpression('eax').reduce()
            self.vprint('RETURN',emu.getFunctionReturn().reduce())

    def do_names(self, line):
        """
        Show any names which contain the given argument.

        Usage: names <name_regex>

        FIXME unify do_sym from vdb into symbol context!
        """
        if not line:
            return self.do_help('names')

        import re
        regex = re.compile(line, re.I)
        for va, name in self.getNames():
            if regex.search(name):
                self.vprint('0x%.8x: %s' % (va, name))

    def do_save(self, line):
        """
        Save the current workspace.

        Usage: save
        """
        self.vprint("Saving workspace...")
        self.saveWorkspace()
        self.vprint("...save complete!")

    def do_xrefs(self, line):
        """
        Show xrefs for a particular location.

        Usage: xrefs [options] <va_expr>
        -T Show xrefs *to* the given address
        -F Show xrefs *from* the given address (default)
        """
        pass

    def do_imports(self, line):
        """
        Show the imports in the workspace (or potentially just one file)

        Usage: imports [fname]
        """
        self.canvas.addText("Imports:\n")
        for va, size, ltype, tinfo in self.getImports():
            # FIXME warn them...
            if not tinfo.startswith(line):
                continue
            vastr = self.arch.pointerString(va)
            self.canvas.addVaText(vastr, va)
            self.canvas.addText(" ")
            self.canvas.addNameText(tinfo, tinfo)
            self.canvas.addText("\n")

    def do_fscope(self, line):
        """
        The fscope command can be used to enumerate things from the
        scope of one function and down it's calling graph.

        Usage: fscope [options] <func_addr_expr>

        -I - Show import calls from this function scope
        -S - Show strings from this function scope

        Example: fscope -I kernel32.CreateFileW
                 (Show imports called by CreateFileW and down...)

        """
        showimp = False
        showstr = False

        argv = e_cli.splitargs(line)
        try:
            opts, args = getopt(argv, 'IS')
        except Exception as e:
            return self.do_help('fscope')

        if not len(args) or not len(opts):
            return self.do_help('fscope')

        for opt, optarg in opts:
            if opt == '-I':
                showimp = True
            elif opt == '-S':
                showstr = True

        for expr in args:

            va = self.parseExpression(expr)

            if showimp:
                for callva, impname in v_t_fscope.getImportCalls(self, va):
                    pstr = self.arch.pointerString(callva)
                    self.canvas.addVaText(pstr, callva)
                    # FIXME best name symbol etc?
                    self.canvas.addText(' %s\n' % impname)

            if showstr:
                for refva, strva, strbytes in v_t_fscope.getStringRefs(self, va):
                    pstr = self.arch.pointerString(refva)
                    self.canvas.addVaText(pstr, refva)
                    self.canvas.addText(' ')
                    self.canvas.addVaText(strbytes, strva)
                    self.canvas.addText('\n')

    def do_exports(self, line):
        """
        List the exports in the workspace (or in a specific file).

        Usage: exports [fname]
        """
        edict = {}
        for va, etype, name, filename in self.getExports():
            l = edict.get(filename)
            if l is None:
                l = []
                edict[filename] = l
            l.append((name, va))

        if line:
            x = edict.get(line)
            if x is None:
                self.vprint("Unknown fname: %s" % line)
                return
            edict = {line: x}

        fnames = list(edict.keys())
        fnames.sort()
        for fname in fnames:
            self.canvas.addNameText(fname, fname)
            self.canvas.addText(":\n")
            exports = edict.get(fname)
            exports.sort()
            for ename, eva in exports:
                pstr = self.arch.pointerString(eva)
                self.canvas.addText("    ")
                self.canvas.addVaText(pstr, eva)
                self.canvas.addText("  ")
                self.canvas.addNameText(ename, ename)
                self.canvas.addText("\n")

    def do_filemeta(self, line):

        """
        Show/List file metadata.

        Usage: filemeta [ fname [ keyname ] ]

        Example: filemeta kernel32
        Example: filemeta kernel32 md5
        """

        argv = e_cli.splitargs(line)
        if len(argv) == 0:

            self.vprint('Loaded Files:')
            for fname in self.getFiles():
                self.vprint('    %s' % fname)

        elif len(argv) == 1:
            d = self.getFileMetaDict(argv[0])
            self.vprint(pprint.pformat(d))

        elif len(argv) == 2:
            val = self.getFileMeta(argv[0], argv[1])
            self.vprint('%s (%s):' % (argv[1], argv[0]))
            self.vprint(pprint.pformat(val))

        else:
            self.do_help('filemeta')

    def do_funcmeta(self, line):
        """
        Show/Set function metadata.
        Usage: funcmeta <func_expr> [key <value_expr>]

        """
        # FIXME make a search thing here!
        argv = e_cli.splitargs(line)
        if len(argv) == 0:
            return self.do_help("funcmeta")

        if len(argv) == 1:
            va = self.parseExpression(argv[0])
            meta = self.getFunctionMetaDict(va)
            self.vprint(pprint.pformat(meta))

        elif len(argv) == 3:
            va = self.parseExpression(argv[0])
            name = argv[1]
            locs = self.getExpressionLocals()
            val = e_expr.evaluate(argv[2], locs)
            self.setFunctionMeta(va, name, val)

    def do_loc(self, line):
        """
        Display the repr of a single location by va.

        Usage: loc <va_expr>
        """
        if not line:
            return self.do_help("loc")

        addr = self.parseExpression(line)
        l = self.getLocation(addr)
        if l is None:
            s = self.arch.pointerString(addr)
            self.vprint("Unknown location: %s" % s)
        r = self.reprLocation(l)
        self.vprint(r)

    def do_make(self, line):
        """
        Create new instances of locations in the vivisect workspace.

        Usage: make [options] <va_expr>
        -c Make code
        -f Make function
        -s Make a string
        -u Make a unicode string
        -n <size> Make a number
        -p <size> Make a pad
        -S <structname> Make a structure
        """
        argv = e_cli.splitargs(line)
        try:
            opts,args = getopt(argv, "csup:S:")
        except Exception as e:
            return self.do_help("make")

        if len(args) != 1 or len(opts) != 1:
            return self.do_help("make")

        addr = self.parseExpression(args[0])
        opt, optarg = opts[0]

        if opt == "-f":
            self.makeFunction(addr)

        elif opt == "-c":
            self.makeCode(addr)

        elif opt == "-s":
            self.makeString(addr)

        elif opt == "-u":
            self.makeUnicode(addr)

        elif opt == "-n":
            size = self.parseExpression(optarg)
            self.makeNumber(addr, size)

        elif opt == "-p":
            size = self.parseExpression(optarg)
            self.makePad(addr, size)

        elif opt == "-S":
            self.makeStructure(addr, optarg)

        else:
            return self.do_help("make")

    def do_emulate(self, line):
        """
        Create an emulator for the given function, and drop into a vdb
        interface to step through the code.
        
        (vdb CLI will appear in controlling terminal...)

        Usage: emulate <va_expr>
        """
        if not line:
            return self.do_help("emulate")

        emu = self.getEmulator()
        addr = self.parseExpression(line)
        emu.setProgramCounter(addr)

        trace = vt_envitools.TraceEmulator(emu)

        db = vdb.Vdb(trace=trace)

        @idlethread
        def _start_vdb_gui(db):
            # db.cmdloop()
            db.do_gui(None)

        _start_vdb_gui(db)

    def do_argtrack(self, line):
        """
        Track input arguments to the given function by name or address.

        Usage: argtrack <func_addr_expr> <arg_idx>
        """
        if not line:
            return self.do_help("argtrack")

        argv = e_cli.splitargs(line)
        if len(argv) != 2:
            return self.do_help("argtrack")

        try:
            fva = self.parseExpression(argv[0])
        except Exception as e:
            self.vprint("Invalid Address Expression: %s" % argv[0])
            return

        try:
            idx = self.parseExpression(argv[1])
        except Exception as e:
            self.vprint("Invalid Index Expression: %s" % argv[1])
            return

        if self.getFunction(fva) != fva:
            self.vprint("Invalid Function Address: (0x%.8x) %s" % (fva, line))

        for pleaf in viv_vector.trackArgOrigin(self, fva, idx):

            self.vprint('='*80)

            path = vg_path.getPathToNode(pleaf)
            path.reverse()

            for pnode in path:
                fva = vg_path.getNodeProp(pnode, 'fva')
                argv = vg_path.getNodeProp(pnode, 'argv')
                callva = vg_path.getNodeProp(pnode, 'cva')
                argidx = vg_path.getNodeProp(pnode, 'argidx')
                if callva is not None:
                    aval, amagic = argv[argidx]
                    arepr = '0x%.8x' % aval
                    if amagic is not None:
                        arepr = repr(amagic)
                    frepr = 'UNKNOWN'
                    if fva is not None:
                        frepr = '0x%.8x' % fva
                    self.vprint('func: %s calls at: 0x%.8x with his own: %s' % (frepr, callva, arepr))
            self.vprint("="*80)

    def do_chat(self, line):
        """
        Echo a message to any other users of a shared workspace.

        Usage: chat oh hai! Checkout 0x7c778030
        """
        if len(line) == 0:
            return self.do_help('chat')

        self.chat(line)

    def do_codepath(self, line):
        """
        Enumerate and show any known code paths from the specified
        from address expression to the to address expression.
        Usage: codepath <from_expr> <to_expr>
        """
        if not line:
            return self.do_help("codepath")

        argv = e_cli.splitargs(line)
        if len(argv) != 2:
            return self.do_help("codepath")

        try:
            frva = self.parseExpression(argv[0])
        except Exception as e:
            self.vprint("Invalid From Va: %s" % argv[0])
            return

        try:
            tova = self.parseExpression(argv[1])
        except Exception as e:
            self.vprint("Invalid To Va: %s" % argv[1])
            return

        self.vprint("Tracking Paths From 0x%.8x to 0x%.8x" % (frva, tova))

        paths = viv_vector.getCodePaths(self, frva, tova)
        self.vprint("Function VA\tBlock VA\tSize\tFunction Name")
        count = 0
        for blist in paths:
            count += 1
            self.vprint("="*30)
            for bva, bsize, fva in blist:
                fname = self.getName(fva)
                self.vprint("0x%.8x\t0x%.8x\t%4d\t%s" % (fva, bva, bsize,fname))
        if count == 0:
            self.vprint("None!")
            return

    def do_vampsig(self, line):
        """
        Generate a vamp signature string for the given function's first block.
        """
        if not line:
            return self.do_help("vampsig")

        va = self.parseExpression(line)

        fva = self.getFunction(va)
        if fva is None:
            self.vprint("Invalid Function Address: 0x%.8x (%s)" % (va, line))

        sig, mask = viv_vamp.genSigAndMask(self, fva)
        self.vprint("SIGNATURE: %s" % sig.hex())
        self.vprint("MASK: %s" % mask.hex())

    def do_vdb(self, line):
        """
        Execute vdb GUI from within vivisect (allowing special hooks between them...)
        (Optionally, specify a host to use for remote vdb debugging)

        Usage: vdb [<remote_host>]
        """
        if line:
            try:
                socket.gethostbyname(line)
            except Exception as e:
                self.vprint('Invalid Remote Host: %s' % line)

            vtrace.remote = line

        import vivisect.vdbext as viv_vdbext
        viv_vdbext.runVdb(self._viv_gui)

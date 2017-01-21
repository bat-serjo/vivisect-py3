"""
Load and provide information about various calling conventions and API definitions on different architectures.

The modules that should provide this information resize under:
    vivisect.impapi.%s.%s (API, ARCHITECTURE)

Each module there should provide at least 2 exports: apitypes and api.
Example:

apitypes = {
    # NTDLL
    'DWORD':        'unsigned int',
    'HANDLE':       'DWORD',
    'HEAP':         'HANDLE',
}

api = {
    # NTDLL
    'ntdll.main_entry':( 'int', None, 'stdcall', 'ntdll.main_entry', (('int', None), ('int', None), ('int', None)) ),
    'ntdll.seh4_prolog':('int', None, 'stdcall', 'ntdll.seh4_prolog', (('void *','pScopeTable'),('int','dwAllocSize'))),
}

"""

import importlib


_search_path = 'vivisect.impapi'


class ImportApi:
    def __init__(self):
        self._api_lookup = {}
        self._apitype_lookup = {}

    def getImpApiType(self, tname):
        return self._apitype_lookup.get(tname)

    def updateApiDef(self, apidict):
        self._api_lookup.update(apidict)

    def getImpApi(self, funcname):
        """
        An API definition consists of the following:
            ( rettype, retname, callconv, funcname, ( (argtype, argname), ...) )
        """
        return self._api_lookup.get(funcname.lower())

    def getImpApiCallConv(self, funcname):
        ret = self._api_lookup.get(funcname.lower())
        if ret is None:
            return None
        return ret[2]

    def getImpApiArgs(self, funcname):
        ret = self._api_lookup.get(funcname.lower())
        if ret is None:
            return None
        return ret[4]

    def getImpApiRetType(self, funcname):
        ret = self._api_lookup.get(funcname.lower())
        if ret is None:
            return None
        return ret[0]

    def getImpApiRetName(self, funcname):
        ret = self._api_lookup.get(funcname.lower())
        if ret is None:
            return None
        return ret[1]

    def getImpApiArgTypes(self, funcname):
        ret = self._api_lookup.get(funcname.lower())
        if ret is None:
            return None
        return [argt for (argt, argn) in ret[4]]

    def getImpApiArgNames(self, funcname):
        ret = self._api_lookup.get(funcname.lower())
        if ret is None:
            return None
        return [argn for (argt, argn) in ret[4]]

    def addImpApi(self, api, arch):
        api = api.lower()
        arch = arch.lower()
        modname = 'vivisect.impapi.%s.%s' % (api, arch)
        # # mod = imp.load_module( modname, *imp.find_module( modname ) )
        # __import__(modname)
        # mod = sys.modules[modname]

        mod = importlib.import_module(modname)
        self._api_lookup.update(mod.api)
        self._apitype_lookup.update(mod.apitypes)


def getImportApi(api, arch):
    impapi = ImportApi()
    impapi.addImpApi(api, arch)
    return impapi

import sys
from topaz.modules.ffi.type import W_TypeObject
from topaz.modules.ffi import type as ffitype
from topaz.modules.ffi._ruby_wrap_llval import (_ruby_wrap_number,
                                                _ruby_wrap_POINTER,
                                                _ruby_wrap_STRING,
                                                _ruby_wrap_llpointer_content,
                                                _ruby_unwrap_llpointer_content)
from topaz.module import ClassDef

from rpython.rtyper.lltypesystem import rffi, llmemory, lltype
from rpython.rlib.jit_libffi import (CIF_DESCRIPTION, CIF_DESCRIPTION_P,
                                     FFI_TYPE_P, FFI_TYPE_PP, SIZE_OF_FFI_ARG)
from rpython.rlib.jit_libffi import jit_ffi_prep_cif
from rpython.rlib import jit
from rpython.rlib.objectmodel import we_are_translated
from rpython.rlib import clibffi

BIG_ENDIAN = sys.byteorder == 'big'

def raise_TypeError_if_not_TypeObject(space, w_candidate):
    if not isinstance(w_candidate, W_TypeObject):
        raise space.error(space.w_TypeError,
                          "Invalid parameter type (%s)" %
                          space.str_w(space.send(w_candidate, 'inspect')))

class W_FunctionTypeObject(W_TypeObject):
    classdef = ClassDef('FunctionType', W_TypeObject.classdef)
    _immutable_fields_ = ['arg_types_w', 'w_ret_type']

    def __init__(self, space):
        W_TypeObject.__init__(self, space, ffitype.FUNCTION)

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space, args_w):
        return W_FunctionTypeObject(space)

    @classdef.method('initialize', arg_types_w='array')
    def method_initialize(self, space, w_ret_type, arg_types_w, w_options=None):
        if w_options is None:
            w_options = space.newhash()
        self.w_options = w_options
        self.space = space

        raise_TypeError_if_not_TypeObject(space, w_ret_type)
        for w_arg_type in arg_types_w:
            raise_TypeError_if_not_TypeObject(space, w_arg_type)

        self.w_ret_type = w_ret_type
        self.arg_types_w = arg_types_w

    @jit.dont_look_inside
    def build_cif_descr(self, space):
        ffi_arg_types = [ffitype.ffi_types[t.typeindex]
                         for t in self.arg_types_w]
        ffi_ret_type = ffitype.ffi_types[self.w_ret_type.typeindex]

        nargs = len(ffi_arg_types)
        # XXX combine both mallocs with alignment
        size = llmemory.raw_malloc_usage(llmemory.sizeof(CIF_DESCRIPTION, nargs))
        if we_are_translated():
            cif_descr = lltype.malloc(rffi.CCHARP.TO, size, flavor='raw')
            cif_descr = rffi.cast(CIF_DESCRIPTION_P, cif_descr)
        else:
            # gross overestimation of the length below, but too bad
            cif_descr = lltype.malloc(CIF_DESCRIPTION_P.TO, size, flavor='raw')
        assert cif_descr
        #
        size = rffi.sizeof(FFI_TYPE_P) * nargs
        atypes = lltype.malloc(rffi.CCHARP.TO, size, flavor='raw')
        atypes = rffi.cast(FFI_TYPE_PP, atypes)
        assert atypes
        #
        cif_descr.abi = clibffi.FFI_DEFAULT_ABI
        cif_descr.nargs = nargs
        cif_descr.rtype = ffi_ret_type
        cif_descr.atypes = atypes
        #
        # first, enough room for an array of 'nargs' pointers
        exchange_offset = rffi.sizeof(rffi.CCHARP) * nargs
        exchange_offset = self.align_arg(exchange_offset)
        cif_descr.exchange_result = exchange_offset
        cif_descr.exchange_result_libffi = exchange_offset
        #
        if BIG_ENDIAN:
            assert 0, 'missing support'
            # see _cffi_backend in pypy
        # then enough room for the result, rounded up to sizeof(ffi_arg)
        exchange_offset += max(rffi.getintfield(ffi_ret_type, 'c_size'),
                               SIZE_OF_FFI_ARG)

        # loop over args
        for i, ffi_arg in enumerate(ffi_arg_types):
            # XXX do we need the "must free" logic?
            exchange_offset = self.align_arg(exchange_offset)
            cif_descr.exchange_args[i] = exchange_offset
            atypes[i] = ffi_arg
            exchange_offset += rffi.getintfield(ffi_arg, 'c_size')

        # store the exchange data size
        cif_descr.exchange_size = exchange_offset
        #
        res = jit_ffi_prep_cif(cif_descr)
        #
        if res != clibffi.FFI_OK:
            raise space.error(space.w_RuntimeError,
                    "libffi failed to build this function type")
        #
        return cif_descr

    def align_arg(self, n):
        return (n + 7) & ~7

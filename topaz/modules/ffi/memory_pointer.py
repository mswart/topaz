from topaz.modules.ffi.pointer import W_PointerObject
from topaz.module import ClassDef

from rpython.rtyper.lltypesystem import rffi
from rpython.rtyper.lltypesystem import lltype


class W_MemoryPointerObject(W_PointerObject):
    classdef = ClassDef('FFI::MemoryPointer', W_PointerObject.classdef)

    def __init__(self, space, klass=None):
        W_PointerObject.__init__(self, space, klass)
        self.w_type = None

    def __del__(self):
        lltype.free(self.ptr, flavor='raw')

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space, args_w):
        return W_MemoryPointerObject(space, self)

    @classdef.method('initialize', size='int')
    def method_initialize(self, space, w_type_hint, size=1, block=None):
        if space.is_kind_of(w_type_hint, space.w_symbol):
            w_FFI = space.find_const(space.w_kernel, 'FFI')
            w_Type = space.find_const(w_FFI, 'Type')
            self.w_type = space.find_const(w_Type, space.symbol_w(w_type_hint).upper())
            sizeof_type = space.int_w(space.send(self.w_type, 'size'))
            self.sizeof_memory = size * sizeof_type
        elif space.is_kind_of(w_type_hint, space.w_fixnum):
            self.sizeof_memory = space.int_w(w_type_hint)
        else:
            raise space.error(space.w_TypeError, 'need symbol as type hint or memory size')
        memory = lltype.malloc(rffi.CArray(rffi.CHAR),
                               self.sizeof_memory,
                               flavor='raw', zero=True)
        self.ptr = rffi.cast(rffi.VOIDP, memory)
        if block is not None:
            return space.invoke_block(block, [self])

    @classdef.method('total')
    def method_total(self, space):
        return space.newint(self.sizeof_memory)

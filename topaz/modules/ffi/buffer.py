from topaz.modules.ffi.abstract_memory import W_AbstractMemoryObject
from topaz.modules.ffi.struct import is_struct
from topaz.module import ClassDef

from rpython.rtyper.lltypesystem import rffi
from rpython.rtyper.lltypesystem import lltype


class W_BufferObject(W_AbstractMemoryObject):
    classdef = ClassDef('FFI::Buffer', W_AbstractMemoryObject.classdef)

    def __deepcopy__(self, memo):
        obj = super(W_BufferObject, self).__deepcopy__(memo)
        obj.ptr = self.ptr
        obj.sizeof_type = self.sizeof_type
        obj.sizeof_memory = self.sizeof_memory
        obj.release_ptr = self.release_ptr
        return obj

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_BufferObject(space, self)

    @classdef.setup_class
    def setup_class(cls, space, w_cls):
        w_method_new = w_cls.getclass(space).find_method(space, 'new')
        for alias in ['alloc_in', 'alloc_out', 'alloc_inout']:
            w_cls.attach_method(space, alias, w_method_new)

    @classdef.method('initialize', count='int', clear='bool')
    def method_initialize(self, space, w_type_hint, count=1, clear=False, block=None):
        if space.is_kind_of(w_type_hint, space.w_symbol):
            w_FFI = space.find_const(space.w_kernel, 'FFI')
            w_Type = space.find_const(w_FFI, 'Type')
            self.w_type = space.find_const(w_Type, space.symbol_w(w_type_hint).upper())
            self.sizeof_type = space.int_w(space.send(self.w_type, 'size'))
        elif space.is_kind_of(w_type_hint, space.w_fixnum):
            self.sizeof_type = space.int_w(w_type_hint)
        elif is_struct(space, w_type_hint):
            self.sizeof_type = space.int_w(space.send(space.send(w_type_hint, 'layout'), 'size'))
        else:
            raise space.error(space.w_TypeError, 'need symbol as type hint or memory size')
        self.sizeof_memory = self.sizeof_type * count
        memory = lltype.malloc(rffi.CArray(rffi.CHAR),
                               self.sizeof_memory,
                               flavor='raw', zero=True)  # zero=clear, but lltype seams to not support that
        self.release_ptr = True
        self.ptr = rffi.cast(rffi.VOIDP, memory)
        if block is not None:
            return space.invoke_block(block, [self])

    @classdef.method('free')
    def method_free(self, space):
        if self.release_ptr:
            lltype.free(self.ptr, flavor='raw')

    def __del__(self):
        if self.release_ptr:
            lltype.free(self.ptr, flavor='raw')

    @classdef.method('null?')
    def method_null(self, space):
        return space.newbool(self.ptr == lltype.nullptr(rffi.VOIDP.TO))

    @classdef.method('length')
    @classdef.method('total')
    @classdef.method('size')
    def method_size(self, space):
        return space.newint_or_bigint(self.sizeof_memory)

    @classdef.method('type_size')
    def method_typesize(self, space):
        return space.newint_or_bigint(self.sizeof_type)

    @classdef.method('==')
    def method_eq(self, space, w_other):
        if isinstance(w_other, W_BufferObject):
            return space.newbool(self.ptr == w_other.ptr)
        else:
            return space.newbool(False)

    def createsubbuffer(self, space, offset, size):
        w_buffer = W_BufferObject(space, klass=self)
        ptr = rffi.ptradd(rffi.cast(rffi.CCHARP, self.ptr), offset * self.sizeof_type)
        w_buffer.ptr = rffi.cast(rffi.VOIDP, ptr)
        w_buffer.sizeof_type = self.sizeof_type
        w_buffer.sizeof_memory = self.sizeof_memory + (size - offset) * self.sizeof_type
        w_buffer.release_ptr = False
        return w_buffer

    @classdef.method('slice', offset='int', size='int')
    def method_slice(self, space, offset, size):
        return self.createsubbuffer(space, offset, size)

    @classdef.method('+', other='int')
    def method_plus(self, space, other):
        return self.createsubbuffer(space, other, int(self.sizeof_memory / self.sizeof_type) - other)

    @classdef.method('[]', other='int')
    def method_subscript(self, space, other):
        return self.createsubbuffer(space, other, self.sizeof_type)



    @classdef.method('inspect')
    def method_inspect(self, space):
        return space.newstr_fromstr("#<FFI:Buffer:%s address=%s size=%d>" %
                                    (self, self.ptr, self.sizeof_memory))

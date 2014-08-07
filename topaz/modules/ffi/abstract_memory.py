from rpython.rtyper.lltypesystem import rffi, lltype

from topaz.objects.objectobject import W_Object
from topaz.module import ClassDef
from topaz.coerce import Coerce

from topaz.modules.ffi import type as ffitype

NULLPTR = lltype.nullptr(rffi.VOIDP.TO)


def ensure_no_nullpointer(space, ptr):
    if ptr == NULLPTR:
        w_FFI = space.find_const(space.w_kernel, 'FFI')
        w_NullPointerError = space.find_const(w_FFI, 'NullPointerError')
        raise space.error(w_NullPointerError, 'Try to read null pointer')


def new_put_method(typeindex):
    rw_strategy = ffitype.rw_strategies[typeindex]
    sizeof_type = ffitype.lltype_sizes[typeindex]

    def put_method(self, space, offset, w_value):
        ensure_no_nullpointer(space, self.ptr)
        offset_ptr = rffi.ptradd(rffi.cast(rffi.CCHARP, self.ptr), offset)
        raise_if_out_of_bounds(space, offset, self.sizeof_memory, sizeof_type)
        rw_strategy.write(space, offset_ptr, w_value)
        return self
    return put_method


def new_get_method(typeindex):
    rw_strategy = ffitype.rw_strategies[typeindex]
    sizeof_type = ffitype.lltype_sizes[typeindex]

    def get_method(self, space, offset):
        ensure_no_nullpointer(space, self.ptr)
        offset_ptr = rffi.ptradd(rffi.cast(rffi.CCHARP, self.ptr), offset)
        raise_if_out_of_bounds(space, offset, self.sizeof_memory, sizeof_type)
        return rw_strategy.read(space, offset_ptr)
    return get_method


def new_write_method(type_str):
    put_method_name = 'put_' + type_str

    def write_method(self, space, w_value):
        space.send(self, put_method_name, [space.newint(0), w_value])
        return self
    return write_method


def new_read_method(type_str):
    get_method_name = 'get_' + type_str

    def read_method(self, space):
        return space.send(self, get_method_name, [space.newint(0)])
    return read_method


def raise_if_out_of_bounds(space, offset, size, sizeof_type):
    if offset < 0 or offset >= size:
        raise memory_index_error(space, offset, sizeof_type)


def memory_index_error(space, offset, size):
    return space.error(space.w_IndexError,
                       "Memory access offset=%s size=%s is out of bounds"
                       % (offset, size))


class W_AbstractMemoryObject(W_Object):
    classdef = ClassDef('FFI::AbstractMemory', W_Object.classdef)
    ptr = lltype.nullptr(rffi.VOIDP.TO)
    _immutable_fields_ = ['ptr']

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_AbstractMemoryObject(space)

    @classdef.setup_class
    def setup_class(cls, space, w_cls):
        long_in_bits = 8 * rffi.sizeof(rffi.LONG)
        for orig, alias in [('int8', 'char'),
                            ('uint8', 'uchar'),
                            ('int16', 'short'),
                            ('uint16', 'ushort'),
                            ('int32', 'int'),
                            ('uint32', 'uint'),
                            ('int64', 'long_long'),
                            ('uint64', 'ulong_long'),
                            ('float32', 'float'),
                            ('float64', 'double'),
                            ('int' + str(long_in_bits), 'long'),
                            ('uint' + str(long_in_bits), 'ulong')]:
            for prefix in ['put_', 'get_', 'write_', 'read_']:
                space.send(w_cls, 'alias_method',
                           [space.newsymbol(prefix + alias),
                            space.newsymbol(prefix + orig)])

    def ptroffset(self, offset):
        voidp = rffi.cast(rffi.VOIDP, self.ptr)
        return rffi.cast(rffi.CCHARP, rffi.ptradd(voidp, offset))

    @classdef.method('get_bytes', offset='int', length='int')
    def method_get_bytes(self, space, offset, length):
        if offset + length > self.sizeof_memory:
            raise space.error(space.w_IndexError,
                              "Address out of bounds of pointer")
        if self.ptr == NULLPTR:
            raise space.error(space.w_IndexError,
                              "Try to access NullPointer")
        result = rffi.charpsize2str(self.ptroffset(offset), length)
        return space.newstr_fromstr(result)

    @classdef.method('put_bytes', pointer_offset='int', str_offset='int')
    def method_put_bytes(self, space, pointer_offset, w_data, str_offset=0, w_length=None):
        if self.ptr == NULLPTR:
            raise space.error(space.w_IndexError,
                              "Try to access NullPointer")
        if str_offset < 0:
            raise space.error(space.w_RangeError, 'index+length is greater than size of string')
        # convert to c str
        w_data = space.convert_type(w_data, space.w_string, 'to_s')
        from rpython.rtyper.lltypesystem.rstr import copy_string_to_raw
        from rpython.rtyper.annlowlevel import llstr as llstrtype
        str_w = space.str_w(w_data)
        if w_length is None:
            length = len(str_w) - str_offset
        else:
            length = Coerce.int(space, w_length)
        if str_offset + length > len(str_w):
            raise space.error(space.w_RangeError, 'index+length is greater than size of string')
        if length < 0:
            raise space.error(space.w_IndexError, 'Length to small')
        if pointer_offset + length > self.sizeof_memory:
            raise space.error(space.w_IndexError,
                              "Address out of bounds of pointer")
        copy_string_to_raw(llstrtype(str_w), self.ptroffset(pointer_offset), str_offset, length)
        return self

    @classdef.method('get_string', offset='int')
    def method_get_string(self, space, offset=0):
        if self.ptr == NULLPTR:
            raise space.error(space.w_IndexError,
                              "Try to access NullPointer")
        result = rffi.charp2str(self.ptroffset(offset))
        return space.newstr_fromstr(result)


W_AMO = W_AbstractMemoryObject
for t in [ffitype.INT8, ffitype.INT16, ffitype.INT32, ffitype.INT64,
          ffitype.UINT8, ffitype.UINT16, ffitype.UINT32, ffitype.UINT64,
          ffitype.FLOAT32, ffitype.FLOAT64,
          ffitype.POINTER]:
    tn = ffitype.type_names[t].lower()
    setattr(W_AMO, 'method_put_' + tn,
            W_AMO.classdef.method('put_' + tn, offset='int')(
                new_put_method(t)))
    setattr(W_AMO, 'method_get_' + tn,
            W_AMO.classdef.method('get_' + tn, offset='int')(
                new_get_method(t)))
    setattr(W_AMO, 'method_write_' + tn,
            W_AMO.classdef.method('write_' + tn)(
                new_write_method(tn)))
    setattr(W_AMO, 'method_read_' + tn,
            W_AMO.classdef.method('read_' + tn)(
                new_read_method(tn)))

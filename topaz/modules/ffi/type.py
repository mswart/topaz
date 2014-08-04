from topaz.objects.objectobject import W_Object
from topaz.module import ClassDef

from rpython.rlib.jit_libffi import FFI_TYPE_P
from rpython.rlib import clibffi
from rpython.rtyper.lltypesystem import rffi, lltype
from rpython.rlib.rarithmetic import intmask
from topaz.coerce import Coerce

# XXX maybe move to rlib/jit_libffi
from pypy.module._cffi_backend import misc

ffi_types = []
type_names = []
lltypes = []
lltype_sizes = []
aliases = []


def native(name, lltype, ffi=None, alias=[]):
    type_names.append(name)
    if ffi is None:
        ffi_types.append(clibffi.cast_type_to_ffitype(lltype))
    else:
        ffi_types.append(ffi)
    lltypes.append(lltype)
    aliases.append(alias)
    if name == 'VOID':
        lltype_sizes.append(-1)
    else:
        lltype_sizes.append(rffi.sizeof(lltypes[-1]))
    return len(type_names) - 1


def define_unimplemented_type(name):
    type_names.append(name)
    ffi_types.append(lltype.nullptr(FFI_TYPE_P.TO))
    lltype_sizes.append(0)
    aliases.append([])
    return len(type_names) - 1


VOID = native('VOID', ffi=clibffi.ffi_type_void, lltype=lltype.Void)
INT8 = native('INT8', ffi=clibffi.ffi_type_sint8,
              lltype=rffi.CHAR, alias=['CHAR', 'SCHAR'])
UINT8 = native('UINT8', ffi=clibffi.ffi_type_uint8,
               lltype=rffi.UCHAR, alias=['UCHAR'])
INT16 = native('INT16', ffi=clibffi.ffi_type_sint16,
               lltype=rffi.SHORT, alias=['SHORT', 'SSHORT'])
UINT16 = native('UINT16', ffi=clibffi.ffi_type_uint16,
                lltype=rffi.USHORT, alias=['USHORT'])
INT32 = native('INT32', ffi=clibffi.ffi_type_sint32,
               lltype=rffi.INT, alias=['INT', 'SINT'])
UINT32 = native('UINT32', ffi=clibffi.ffi_type_uint32,
                lltype=rffi.UINT, alias=['UINT'])
INT64 = native('INT64', ffi=clibffi.ffi_type_sint64,
               lltype=rffi.LONGLONG, alias=['LONG_LONG', 'SLONG_LONG'])
UINT64 = native('UINT64', ffi=clibffi.ffi_type_uint64,
                lltype=rffi.ULONGLONG, alias=['ULONG_LONG'])
LONG = native('LONG', lltype=rffi.LONG, alias=['SLONG'])
ULONG = native('ULONG', lltype=rffi.ULONG)
FLOAT32 = native('FLOAT32', ffi=clibffi.ffi_type_float, lltype=rffi.FLOAT,
                 alias=['FLOAT'])
FLOAT64 = native('FLOAT64', ffi=clibffi.ffi_type_double, lltype=rffi.DOUBLE,
                 alias=['DOUBLE'])
LONGDOUBLE = native('LONGDOUBLE', ffi=clibffi.ffi_type_longdouble,
                    lltype=rffi.LONGDOUBLE)
POINTER = native('POINTER', ffi=clibffi.ffi_type_pointer, lltype=rffi.VOIDP)
CALLBACK = native('CALLBACK', ffi=clibffi.ffi_type_pointer, lltype=rffi.VOIDP)
FUNCTION = native('FUNCTION', ffi=clibffi.ffi_type_pointer, lltype=rffi.VOIDP)
BUFFER_IN = native('BUFFER_IN', ffi=clibffi.ffi_type_pointer, lltype=rffi.VOIDP)#define_unimplemented_type('BUFFER_IN')
BUFFER_OUT = native('BUFFER_OUT', ffi=clibffi.ffi_type_pointer, lltype=rffi.VOIDP)#define_unimplemented_type('BUFFER_OUT')
BUFFER_INOUT = native('BUFFER_INOUT', ffi=clibffi.ffi_type_pointer, lltype=rffi.VOIDP)#define_unimplemented_type('BUFFER_INOUT')
CHAR_ARRAY = define_unimplemented_type('CHAR_ARRAY')
BOOL = native('BOOL', lltype=lltype.Bool)
STRING = native('STRING', ffi=clibffi.ffi_type_pointer, lltype=rffi.CCHARP)
VARARGS = native('VARARGS', ffi=clibffi.ffi_type_void, lltype=rffi.CHAR)
NATIVE_VARARGS = define_unimplemented_type('NATIVE_VARARGS')
NATIVE_STRUCT = define_unimplemented_type('NATIVE_STRUCT')
NATIVE_ARRAY = define_unimplemented_type('NATIVE_ARRAY')
NATIVE_MAPPED = native('NATIVE_MAPPED', ffi=clibffi.ffi_type_void,
                       lltype=rffi.CCHARP)


def lltype_for_name(name):
    """NOT_RPYTHON"""
    # XXX maybe use a dictionary
    return lltypes[type_names.index(name)]


def size_for_name(name):
    """NOT_RPYTHON"""
    # XXX maybe use a dictionary
    return lltype_sizes[type_names.index(name)]


class W_TypeObject(W_Object):
    classdef = ClassDef('FFI::Type', W_Object.classdef)

    typeindex = 0
    _immutable_fields_ = ['typeindex', 'rw_strategy']

    def __init__(self, space, typeindex=0, rw_strategy=None, klass=None):
        assert isinstance(typeindex, int)
        W_Object.__init__(self, space, klass)
        self.typeindex = typeindex
        self.rw_strategy = rw_strategy

    @classdef.setup_class
    def setup_class(cls, space, w_cls):
        for t in rw_strategies:
            w_new_type = W_BuiltinType(space, t, rw_strategies[t])
            space.set_const(w_cls, type_names[t], w_new_type)
            for alias in aliases[t]:
                space.set_const(w_cls, alias, w_new_type)
        space.set_const(w_cls, 'Mapped', space.getclassfor(W_MappedObject))

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space, args_w):
        return W_TypeObject(space, VOID)

    def __deepcopy__(self, memo):
        obj = super(W_TypeObject, self).__deepcopy__(memo)
        obj.typeindex = self.typeindex
        obj.rw_strategy = self.rw_strategy
        return obj

    def __repr__(self):
        return '<W_TypeObject %s(%s)>' % (type_names[self.typeindex], lltype_sizes[self.typeindex])

    def eq(self, w_other):
        if not isinstance(w_other, W_TypeObject):
            return False
        return self.typeindex == w_other.typeindex

    __eq__ = eq

    @classdef.method('==')
    def method_eq(self, space, w_other):
        return space.newbool(self.eq(w_other))

    @classdef.method('size')
    @classdef.method('alignment')
    def method_size(self, space):
        r_uint_size = lltype_sizes[self.typeindex]
        size = intmask(r_uint_size)
        return space.newint(size)

    def read(self, space, data):
        return self.rw_strategy.read(space, data)

    def write(self, space, data, w_arg):
        return self.rw_strategy.write(space, data, w_arg)


class W_BuiltinType(W_TypeObject):
    classdef = ClassDef('Builtin', W_TypeObject.classdef)

    def __init__(self, space, typeindex, rw_strategy):
        W_TypeObject.__init__(self, space, typeindex, rw_strategy)

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space, args_w):
        raise NotImplementedError


def type_object(space, w_obj):
    w_ffi_mod = space.find_const(space.w_kernel, 'FFI')
    w_type = space.send(w_ffi_mod, 'find_type', [w_obj])
    if not isinstance(w_type, W_TypeObject):
        raise space.error(space.w_TypeError,
                          "This seems to be a bug. find_type should always"
                          "return an FFI::Type object, but apparently it did"
                          "not in this case.")
    return w_type


class ReadWriteStrategy(object):
    def __init__(self, typeindex):
        self.typesize = lltype_sizes[typeindex]

    def read(self, space, data):
        raise NotImplementedError("abstract ReadWriteStrategy")

    def write(self, space, data, w_arg):
        raise NotImplementedError("abstract ReadWriteStrategy")


class StringRWStrategy(ReadWriteStrategy):
    def __init__(self):
        ReadWriteStrategy.__init__(self, STRING)

    def read(self, space, data):
        result = misc.read_raw_unsigned_data(data, self.typesize)
        result = rffi.cast(rffi.CCHARP, result)
        result = rffi.charp2str(result)
        return space.newstr_fromstr(result)

    def write(self, space, data, w_arg):
        w_arg = space.convert_type(w_arg, space.w_string, 'to_s')
        arg = space.str_w(w_arg)
        arg = rffi.str2charp(arg)
        arg = rffi.cast(lltype.Unsigned, arg)
        misc.write_raw_unsigned_data(data, arg, self.typesize)


class PointerRWStrategy(ReadWriteStrategy):
    def __init__(self):
        ReadWriteStrategy.__init__(self, POINTER)

    def read(self, space, data):
        result = misc.read_raw_unsigned_data(data, self.typesize)
        result = rffi.cast(lltype.Signed, result)
        w_FFI = space.find_const(space.w_kernel, 'FFI')
        w_Pointer = space.find_const(w_FFI, 'Pointer')
        return space.send(w_Pointer, 'new',
                          [space.newint(result)])

    def write(self, space, data, w_arg):
        w_arg = self._convert_to_NULL_if_nil(space, w_arg)
        arg = Coerce.ffi_pointer(space, w_arg)
        arg = rffi.cast(lltype.Unsigned, arg)
        misc.write_raw_unsigned_data(data, arg, self.typesize)

    @staticmethod
    def _convert_to_NULL_if_nil(space, w_arg):
        if w_arg is space.w_nil:
            w_FFI = space.find_const(space.w_kernel, 'FFI')
            w_Pointer = space.find_const(w_FFI, 'Pointer')
            return space.find_const(w_Pointer, 'NULL')
        else:
            return w_arg


class BoolRWStrategy(ReadWriteStrategy):
    def __init__(self):
        ReadWriteStrategy.__init__(self, BOOL)

    def read(self, space, data):
        result = bool(misc.read_raw_signed_data(data, self.typesize))
        return space.newbool(result)

    def write(self, space, data, w_arg):
        arg = space.is_true(w_arg)
        misc.write_raw_unsigned_data(data, arg, self.typesize)


class FloatRWStrategy(ReadWriteStrategy):
    def read(self, space, data):
        result = misc.read_raw_float_data(data, self.typesize)
        return space.newfloat(float(result))

    def write(self, space, data, w_arg):
        arg = space.float_w(w_arg)
        misc.write_raw_float_data(data, arg, self.typesize)


class SignedRWStrategy(ReadWriteStrategy):
    def read(self, space, data):
        result = misc.read_raw_signed_data(data, self.typesize)
        return space.newint(intmask(result))

    def write(self, space, data, w_arg):
        w_arg = space.convert_type(w_arg, space.w_integer, 'to_i')
        arg = space.int_w(w_arg)
        misc.write_raw_signed_data(data, arg, self.typesize)


class UnsignedRWStrategy(ReadWriteStrategy):
    def read(self, space, data):
        result = misc.read_raw_unsigned_data(data, self.typesize)
        return space.newint(intmask(result))

    def write(self, space, data, w_arg):
        arg = space.int_w(w_arg)
        misc.write_raw_unsigned_data(data, arg, self.typesize)


class VoidRWStrategy(ReadWriteStrategy):
    def __init__(self):
        ReadWriteStrategy.__init__(self, VOID)

    def read(self, space, data):
        return space.w_nil

    def write(self, space, data, w_arg):
        pass

rw_strategies = {}
rw_strategies[VOID] = VoidRWStrategy()
for ts, tu in [[INT8, UINT8],
              [INT16, UINT16],
              [INT32, UINT32],
              [INT64, UINT64],
              [LONG, ULONG]]:
    rw_strategies[ts] = SignedRWStrategy(ts)
    rw_strategies[tu] = UnsignedRWStrategy(tu)
# LongdoubleRWStrategy is not implemented yet, give LONGDOUBLE a
# FloatRWStrategy for now so the ruby part of ffi doesn't crash when it gets
# loaded
for t in [FLOAT32, FLOAT64, LONGDOUBLE]:
    rw_strategies[t] = FloatRWStrategy(t)
rw_strategies[POINTER] = PointerRWStrategy()
rw_strategies[BOOL] = BoolRWStrategy()
rw_strategies[STRING] = StringRWStrategy()
# These three are not implemented yet, they just get a pointer strategy for now
# to make the ruby part happy
for t in [BUFFER_IN, BUFFER_OUT, BUFFER_INOUT]:
    rw_strategies[t] = PointerRWStrategy()
rw_strategies[VARARGS] = VoidRWStrategy()


class W_MappedObject(W_TypeObject):
    classdef = ClassDef('MappedObject', W_TypeObject.classdef)

    def __init__(self, space, klass=None):
        W_TypeObject.__init__(self, space, NATIVE_MAPPED)
        self.rw_strategy = None

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space, args_w):
        return W_MappedObject(space)

    @classdef.method('initialize')
    def method_initialize(self, space, w_data_converter):
        for required in ['native_type', 'to_native', 'from_native']:
            if not space.respond_to(w_data_converter, required):
                raise space.error(space.w_NoMethodError,
                                  "%s method not implemented" % required)
        self.w_data_converter = w_data_converter
        w_type = space.send(w_data_converter, 'native_type')
        if isinstance(w_type, W_TypeObject):
            self.typeindex = w_type.typeindex
            self.rw_strategy = w_type.rw_strategy
        else:
            raise space.error(space.w_TypeError,
                              "native_type did not return instance of "
                              "FFI::Type")

    @classdef.method('to_native')
    def method_to_native(self, space, args_w):
        return space.send(self.w_data_converter, 'to_native', args_w)

    @classdef.method('from_native')
    def method_from_native(self, space, args_w):
        return space.send(self.w_data_converter, 'from_native', args_w)

    def read(self, space, data):
        w_native = W_TypeObject.read(self, space, data)
        return self.method_from_native(space, [w_native, space.w_nil])

    def write(self, space, data, w_obj):
        w_lookup = self.method_to_native(space, [w_obj, space.w_nil])
        W_TypeObject.write(self, space, data, w_lookup)

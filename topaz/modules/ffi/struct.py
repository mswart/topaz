from rpython.rlib import clibffi
from rpython.rtyper.lltypesystem import lltype, rffi

from topaz.objects.classobject import W_ClassObject
from topaz.objects.objectobject import W_Object
from topaz.module import ClassDef
from topaz.modules.enumerable import Enumerable
from topaz.modules.ffi.type import W_TypeObject, ffi_types, NATIVE_MAPPED
from topaz.modules.ffi.pointer import W_PointerObject
from topaz.modules.ffi.abstract_memory import W_AbstractMemoryObject
from topaz.modules.ffi.struct_layout import W_StructLayoutObject, W_ArrayFieldObject
from topaz.modules.ffi.array_type import W_ArrayTypeObject


class W_StructByValue(W_TypeObject):
    classdef = ClassDef('FFI::StructByValue', W_TypeObject.classdef)

    @classdef.method('[]=')
    def setter(self, space):
        pass

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_StructByValue(space, NATIVE_MAPPED, klass=self)

    @classdef.method('initialize')
    def method_initialize(self, space, w_struct):
        self.w_struct = w_struct

    @classdef.method('struct_class')
    def method_struct_class(self, space):
        return self.w_struct

    def read(self, space, data):
        w_pointer = W_PointerObject(space)
        w_pointer.ptr = rffi.cast(rffi.VOIDP, data)
        w_pointer.sizeof_memory = w_pointer.sizeof_type = space.int_w(space.send(space.send(self.w_struct, 'layout'), 'size'))
        return space.send(self.w_struct, 'new', [w_pointer])


class W_InlineArrayObject(W_Object):
    classdef = ClassDef('FFI::Struct::InlineArray', W_Object.classdef)
    classdef.include_module(Enumerable)

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_InlineArrayObject(space)

    @classdef.method('initialize')
    def method_initialize(self, space, w_abstract_memory, w_field):
        if not space.is_kind_of(w_abstract_memory, space.getclassfor(W_AbstractMemoryObject)):
            raise space.error(space.w_TypeError, 'FFI::AbstractMemory needed')
        self.w_memory = w_abstract_memory
        W_FieldObject = space.find_const(space.getclassfor(W_StructLayoutObject), 'Field')
        if not space.is_kind_of(w_field, W_FieldObject):
            raise space.error(space.w_TypeError, 'FFI::Struct::Field needed')
        assert type(w_field) is W_ArrayFieldObject
        self.w_field = w_field
        w_type = w_field.w_type
        assert type(w_type) is W_ArrayTypeObject
        self.w_elementtype = w_type.element_type

    @classdef.method('size')
    def method_size(self, space):
        return space.send(self.w_field.w_type, 'length')

    def ptroffset(self, space, index):
        assert isinstance(self.w_memory, W_AbstractMemoryObject)
        voidp = rffi.cast(rffi.VOIDP, self.w_memory.ptr)
        return rffi.cast(rffi.CCHARP, rffi.ptradd(voidp, self.w_field.offset + index * space.int_w(space.send(self.w_elementtype, 'size'))))

    @classdef.method('[]', index='int')
    def method_subscript(self, space, index):
        return self.w_elementtype.read(space, self.ptroffset(space, index))

    @classdef.method('[]=', index='int')
    def method_subscript_assign(self, space, index, w_value):
        return self.w_elementtype.write(space, self.ptroffset(space, index), w_value)

    @classdef.method('each')
    def method_each(self, space, block):
        for i in range(space.int_w(space.send(self, 'size'))):
            space.invoke_block(block, [self.method_subscript(space, i)])

    @classdef.method('to_ary')
    def method_to_ary(self, space, block):
        return space.newarray([self.method_subscript(space, i)
                               for i in range(space.int_w(space.send(self, 'size')))])

    @classdef.method('to_ptr')
    def method_to_ptr(self, space):
        return space.send(self.w_memory, '+', [space.newint(self.w_field.offset)])


class W_Struct(W_Object):
    classdef = ClassDef('FFI::Struct', W_Object.classdef)

    def __init__(self, space, klass=None):
        W_Object.__init__(self, space, klass)
        self.layout = None
        self.pointer = None
        self.self_allocated = True
        self.name_to_index = {}

    @classdef.setup_class
    def setup_class(self, space, cls):
        space.set_const(cls, 'InlineArray', space.getclassfor(W_InlineArrayObject))

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_Struct(space, self)

    @classdef.method('initialize')
    def method_initialize(self, space, w_pointer=None):
        if w_pointer is not None and w_pointer is not space.w_nil:
            if not isinstance(w_pointer, W_AbstractMemoryObject):
                raise space.error(space.w_TypeError, 'AbstractMemory needed!')
            self.ensure_layout(space)
            self.pointer = w_pointer
            self.self_allocated = False

    @classdef.method('null?')
    def method_null(self, space):
        if self.pointer is None:
            return space.w_false
        else:
            return space.send(self.pointer, 'null?')

    def ensure_layout(self, space):
        if self.layout is None:  # layout not yet loaded
            layout = space.send(space.send(self, 'class'), 'layout')
            if not isinstance(layout, W_StructLayoutObject):
                raise space.error(space.w_TypeError, 'Struct needs StructLayout not %s' % space.getclass(layout).name)
            self.layout = layout
            for w_field in layout.fields:
                self.name_to_index[space.send(w_field, 'name')] = w_field
        return self.layout

    def ensure_allocated(self, space):
        if self.pointer is None:
            layout = self.ensure_layout(space)
            fieldtypes = []
            for w_field in layout.fields:
                w_type = space.send(w_field, 'type')
                if type(w_type) is W_ArrayTypeObject:
                    count = space.int_w(space.send(w_type, 'length'))
                else:
                    count = 1
                fieldtypes += [ffi_types[w_type.typeindex]] * count
            ffi_struct = clibffi.make_struct_ffitype_e(layout.struct_size,
                                                       layout.alignment,
                                                       fieldtypes)
            w_pointer = W_PointerObject(space)
            w_pointer.sizeof_type = self.layout.struct_size
            w_pointer.ptr = rffi.cast(rffi.VOIDP, ffi_struct)
            w_pointer.sizeof_memory = w_pointer.sizeof_type
            self.pointer = w_pointer
        return self.pointer

    def ptroffset(self, offset):
        voidp = rffi.cast(rffi.VOIDP, self.pointer.ptr)
        return rffi.cast(rffi.CCHARP, rffi.ptradd(voidp, offset))

    @classdef.method('[]', w_key='symbol')
    def method_subscript(self, space, w_key):
        w_pointer = self.ensure_allocated(space)
        w_field = self.name_to_index[w_key]
        return space.send(w_field, 'get', [w_pointer])

    @classdef.method('[]=', w_key='symbol')
    def method_subscript_assign(self, space, w_key, w_value):
        w_pointer = self.ensure_allocated(space)
        w_field = self.name_to_index[w_key]
        return space.send(w_field, 'put', [w_pointer, w_value])

    def __repr__(self):
        return '<modules.ffi.W_Struct ()>'

    def eq(self, w_other):
        if not isinstance(w_other, W_Struct):
            return False
        if self.layout is None or w_other.layout is None:
            return False
        return self.layout == w_other.layout

    __eq__ = eq

    @classdef.method('==')
    def method_eq(self, space, w_other):
        return space.newbool(self.eq(w_other))

    @classdef.method('size')
    @classdef.method('alignment')
    def method_size(self, space):
        self.ensure_layout
        return space.newint(self.layout.struct_size)

    @classdef.method('pointer')
    def method_pointer(self, space):
        return self.ensure_allocated(space)

    @classdef.method('free')
    def method_free(self, space):
        self.__del__()
        self.pointer = None

    # TODO: possible to get it @rgc.must_be_light_finalizer again?
    def __del__(self):
        if self.self_allocated and self.pointer is not None:
            lltype.free(self.pointer.ptr, flavor='raw')


def is_struct(space, w_object):
    if not space.is_kind_of(w_object, space.w_class):
        return False
    assert isinstance(w_object, W_ClassObject)
    w_structclass = space.getclassfor(W_Struct)
    while w_object.superclass is not None:
        if w_object is w_structclass:
            return True
        w_object = w_object.superclass
    return w_object is w_structclass

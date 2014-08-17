from rpython.rtyper.lltypesystem import rffi

from topaz.objects.objectobject import W_Object
from topaz.module import ClassDef

from topaz.modules.ffi.abstract_memory import W_AbstractMemoryObject
from topaz.modules.ffi.type import W_TypeObject


class W_StructLayoutFieldObject(W_Object):
    classdef = ClassDef('FFI::StructLayout::Field', W_Object.classdef)

    def __init__(self, space, klass=None):
        W_Object.__init__(self, space, klass)
        self.name = ''
        self.offset = 0
        self.w_type = None

    @classdef.method('initialize', name='str', offset='int')
    def method_initialize(self, space, name, offset, w_type):
        self.name = name
        self.offset = offset
        if not space.is_kind_of(w_type, space.getclassfor(W_TypeObject)):
            raise space.error(space.w_TypeError, 'Expected a FFI::Type object')
        self.w_type = w_type

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_StructLayoutFieldObject(space, self)

    @classdef.method('name')
    def method_name(self, space):
        return space.newsymbol(self.name)

    @classdef.method('offset')
    def method_offset(self, space):
        return space.newint(self.offset)

    @classdef.method('type')
    def method_type(self, space):
        return self.w_type

    @classdef.method('size')
    @classdef.method('alignment')
    def method_size(self, space):
        return space.send(self.w_type, 'size')

    def ptroffset(self, w_pointer):
        assert isinstance(w_pointer, W_AbstractMemoryObject)
        voidp = rffi.cast(rffi.VOIDP, w_pointer.ptr)
        return rffi.cast(rffi.CCHARP, rffi.ptradd(voidp, self.offset))

    @classdef.method('get')
    def method_get(self, space, w_abstractmemory):
        return self.w_type.read(space, self.ptroffset(w_abstractmemory))

    @classdef.method('put')
    def method_put(self, space, w_abstractmemory, w_value):
        return self.w_type.write(space, self.ptroffset(w_abstractmemory), w_value)


class W_ArrayFieldObject(W_StructLayoutFieldObject):
    classdef = ClassDef('FFI::StructLayout::Array', W_StructLayoutFieldObject.classdef)

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_ArrayFieldObject(space, self)

    @classdef.method('get')
    def method_get(self, space, w_abstractmemory):
        w_FFI = space.find_const(space.w_kernel, 'FFI')
        w_Struct = space.find_const(w_FFI, 'Struct')
        w_InlineArray = space.find_const(w_Struct, 'InlineArray')
        return space.send(w_InlineArray, 'new', [w_abstractmemory, self])

    @classdef.method('put')
    def method_put(self, space, w_abstractmemory, w_value):
        raise space.error(space.w_NotImplementedError, 'cannot set array field')


class W_StructLayoutObject(W_Object):
    classdef = ClassDef('FFI::StructLayout', W_Object.classdef)

    @classdef.setup_class
    def setup_class(self, space, cls):
        w_struct_layout_field = space.getclassfor(W_StructLayoutFieldObject)
        space.set_const(cls, 'Field', w_struct_layout_field)
        # space.set_const(cls, 'Number',
        #                 space.newclass('Number', w_struct_layout_field))
        # space.set_const(cls, 'String',
        #                 space.newclass('String', w_struct_layout_field))
        # space.set_const(cls, 'Pointer',
        #                 space.newclass('Pointer', w_struct_layout_field))
        # space.set_const(cls, 'Function',
        #                 space.newclass('Function', w_struct_layout_field))
        space.set_const(cls, 'Array', space.getclassfor(W_ArrayFieldObject))

    @classdef.method('initialize', fields='array', size='int', alignment='int')
    def method_initialize(self, space, fields, size, alignment):
        # TODO: type checks!
        self.fields = fields
        self.struct_size = size
        self.alignment = alignment

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_StructLayoutObject(space, self)

    @classdef.method('size')
    def method_size(self, space):
        return space.newint(self.struct_size)

    @classdef.method('alignment')
    def method_alignment(self, space):
        return space.newint(self.alignment)

    @classdef.method('members')
    def method_fields(self, space):
        symbols = []
        for field in self.fields:
            assert isinstance(field, W_StructLayoutFieldObject)
            symbols.append(space.newsymbol(field.name))
        return space.newarray(symbols)

    @classdef.method('[]', name='str')
    def method_subscript(self, space, name):
        for field in self.fields:
            assert isinstance(field, W_StructLayoutFieldObject)
            if field.name == name:
                return field
        return space.w_nil

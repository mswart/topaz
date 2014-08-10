from rpython.rlib import clibffi
from rpython.rtyper.lltypesystem import lltype, rffi

from topaz.objects.objectobject import W_Object
from topaz.module import ClassDef
from topaz.modules.ffi.type import W_TypeObject, ffi_types
from topaz.modules.ffi.pointer import W_PointerObject


class W_StructLayout(W_Object):
    classdef = ClassDef('FFI::StructLayout', W_Object.classdef)

    @classdef.method('initialize', fields='array', size='int', alignment='int')
    def method_initialize(self, space, fields, size, alignment):
        # TODO: type checks!
        self.fields = fields
        self.struct_size = size
        self.alignment = alignment

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_StructLayout(space, self)

    @classdef.method('size')
    def method_size(self, space):
        return space.newint(self.struct_size)

    @classdef.method('alignment')
    def method_alignment(self, space):
        return space.newint(self.alignment)


class W_StructByValue(W_TypeObject):
    classdef = ClassDef('FFI::StructByValue', W_TypeObject.classdef)

    @classdef.method('[]=')
    def setter(self, space):
        pass

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_StructByValue(space, -1, klass=self)


class W_Struct(W_Object):
    classdef = ClassDef('FFI::Struct', W_Object.classdef)

    def __init__(self, space, klass=None):
        W_Object.__init__(self, space, klass)
        self.layout = None
        self.pointer = None
        self.self_allocated = True
        self.name_to_index = {}

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_Struct(space, self)

    @classdef.method('initialize')
    def method_initialize(self, space, w_pointer=None):
        if w_pointer is not None and w_pointer is not space.w_nil:
            if not isinstance(w_pointer, W_PointerObject):
                raise space.error(space.w_TypeError, 'PointerObject needed!')
            self.ensure_layout(space)
            self.pointer = w_pointer
            self.self_allocated = False

    def ensure_layout(self, space):
        if self.layout is None:  # layout not yet loaded
            layout = space.send(space.send(self, 'class'), 'layout')
            if not isinstance(layout, W_StructLayout):
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
                assert isinstance(w_type, W_TypeObject)
                fieldtypes.append(ffi_types[w_type.typeindex])
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

    @classdef.method('[]=', w_key='symbol')
    def method_subscript_assign(self, space, w_key, w_value):
        self.ensure_allocated(space)
        w_field = self.name_to_index[w_key]
        w_type = space.send(w_field, 'type')
        offset = space.int_w(space.send(w_field, 'offset'))
        return w_type.write(space, self.ptroffset(offset), w_value)

    @classdef.method('[]', w_key='symbol')
    def method_subscript(self, space, w_key):
        self.ensure_allocated(space)
        w_field = self.name_to_index[w_key]
        w_type = space.send(w_field, 'type')
        offset = space.send(w_field, 'offset').int_w(space)
        return w_type.read(space, self.ptroffset(offset))

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

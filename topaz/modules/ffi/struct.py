from rpython.rlib.rarithmetic import intmask
from rpython.rlib import clibffi, rgc
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
        self.size = size
        self.alignment = alignment

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_StructLayout(space, self)

    @classdef.method('size')
    def method_size(self, space):
        return space.newint(self.size)


class W_StructByValue(W_TypeObject):
    classdef = ClassDef('FFI::StructByValue', W_TypeObject.classdef)

    @classdef.method('[]=')
    def setter(self, space):
        pass

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_StructByValue(space, -1, self)


class W_Struct(W_Object):
    classdef = ClassDef('FFI::Struct', W_Object.classdef)

    def __init__(self, space, klass=None):
        W_Object.__init__(self, space, klass)
        self.layout = None
        self.ffi_struct = None
        self.name_to_index = {}

    @classdef.singleton_method("allocate")
    def singleton_method_allocate(self, space):
        return W_Struct(space, self)

    def ensure_layout(self, space):
        if self.layout is None: # layout not yet loaded
            layout = space.send(space.send(self, 'class'), 'layout')
            assert isinstance(layout, W_StructLayout)
            self.layout = layout
            for w_field in layout.fields:
                self.name_to_index[space.send(w_field, 'name')] = w_field
        return self.layout

    def ensure_allocated(self, space):
        if not self.ffi_struct:
            layout = self.ensure_layout(space)
            # Repeated fields are delicate.  Consider for example
            #     struct { int a[5]; }
            # or  struct { struct {int x;} a[5]; }
            # Seeing no corresponding doc in clibffi, let's just repeat
            # the field 5 times...
            fieldtypes = []
            for w_field in layout.fields:
                w_type = space.send(w_field, 'type')
                assert isinstance(w_type, W_TypeObject)
                fieldtypes.append(ffi_types[w_type.typeindex])
            self.ffi_struct = clibffi.make_struct_ffitype_e(layout.size,
                                                           layout.alignment,
                                                           fieldtypes)

    def ptroffset(self, offset):
        voidp = rffi.cast(rffi.VOIDP, self.ffi_struct.ffistruct)
        return rffi.ptradd(voidp, offset)

    @classdef.method('[]=', w_key='symbol')
    def method_subscript_assign(self, space, w_key, w_value):
        self.ensure_allocated(space)
        w_field = self.name_to_index[w_key]
        w_type = space.send(w_field, 'type')
        offset = space.send(w_field, 'offset').intvalue
        return w_type.write(space, self.ptroffset(offset), w_value)

    @classdef.method('[]', w_key='symbol')
    def method_subscript(self, space, w_key):
        self.ensure_allocated(space)
        w_field = self.name_to_index[w_key]
        w_type = space.send(w_field, 'type')
        offset = space.send(w_field, 'offset').intvalue
        return w_type.read(space, self.ptroffset(offset))

    def __repr__(self):
        return '<W_StructObject ()>'
            # % (type_names[self.typeindex], lltype_sizes[self.typeindex])

    def eq(self, w_other):
        if not isinstance(w_other, W_Struct):
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

    @classdef.method('pointer')
    def method_pointer(self, space):
        self.ensure_allocated(space)
        w_pointer = W_PointerObject(space)
        w_pointer._initialize(space, self.ffi_struct.ffistruct,
                              space.send(self.layout, 'size'))
        return w_pointer

    # get the corresponding ffi_type
    ffi_struct = lltype.nullptr(clibffi.FFI_STRUCT_P.TO)

    @rgc.must_be_light_finalizer
    def __del__(self):
        if self.ffi_struct:
            lltype.free(self.ffi_struct, flavor='raw')

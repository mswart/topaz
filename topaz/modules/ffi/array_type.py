from topaz.module import ClassDef
from topaz.modules.ffi.type import W_TypeObject


class W_ArrayTypeObject(W_TypeObject):
    classdef = ClassDef('FFI::ArrayType', W_TypeObject.classdef)

    @classdef.singleton_method('allocate')
    def singleton_method_allocate(self, space):
        return W_ArrayTypeObject(space)

    @classdef.method('initialize', length='int')
    def method_initialize(self, space, w_type, length):
        if not isinstance(w_type, W_TypeObject):
            raise space.error(space.w_TypeError,
                              "native_type did not return instance of "
                              "FFI::Type")
        # ToDo check whether is is working and the best way
        self.element_type = w_type
        self.typeindex = w_type.typeindex
        self.rw_strategy = w_type.rw_strategy
        self.array_size = length

    @classdef.method('element_type')
    def method_element_type(self, space):
        return space.element_type

    @classdef.method('length')
    def method_length(self, space):
        return space.newint(self.array_size)

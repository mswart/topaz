from topaz.modules.ffi.abstract_memory import W_AbstractMemoryObject
from topaz.module import ClassDef

from rpython.rtyper.lltypesystem import rffi
from rpython.rtyper.lltypesystem import lltype


class W_BufferObject(W_AbstractMemoryObject):
    classdef = ClassDef('FFI::Buffer', W_AbstractMemoryObject.classdef)

    def __init__(self, space, klass=None):
        W_AbstractMemoryObject.__init__(self, space, klass)
        self.sizeof_type = 0
        self.sizeof_memory = 0

    def __deepcopy__(self, memo):
        obj = super(W_BufferObject, self).__deepcopy__(memo)
        obj.ptr = self.ptr
        obj.sizeof_type = self.sizeof_type
        obj.sizeof_memory = self.sizeof_memory
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
        else:
            raise space.error(space.w_TypeError, 'need symbol as type hint or memory size')
        self.sizeof_memory = self.sizeof_type * count
        memory = lltype.malloc(rffi.CArray(rffi.CHAR),
                               self.sizeof_memory,
                               flavor='raw', zero=True)
                               # zero=clear, but lltype seams to not support that
        self.ptr = rffi.cast(rffi.VOIDP, memory)
        if block is not None:
            return space.invoke_block(block, [self])

    @classdef.method('free')
    def method_free(self, space):
        lltype.free(self.ptr, flavor='raw')

    @classdef.method('length')
    @classdef.method('total')
    @classdef.method('size')
    def method_size(self, space):
        return space.newint_or_bigint(self.sizeof_memory)

    @classdef.method('==')
    def method_eq(self, space, w_other):
        if isinstance(w_other, W_BufferObject):
            return space.newbool(self.ptr == w_other.ptr)
        else:
            return space.newbool(False)

    @classdef.method('slice', size='int')
    def method_slice(self, space, w_offset, size):
        w_pointer = space.send(self, '+', [w_offset])
        assert isinstance(w_pointer, W_BufferObject)
        w_pointer.sizeof_memory = size
        return w_pointer

        # static VALUE
        # slice(VALUE self, long offset, long len)
        # {
        #     Buffer* ptr;
        #     Buffer* result;
        #     VALUE obj = Qnil;

        #     Data_Get_Struct(self, Buffer, ptr);
        #     checkBounds(&ptr->memory, offset, len);

        #     obj = Data_Make_Struct(BufferClass, Buffer, buffer_mark, -1, result);
        #     result->memory.address = ptr->memory.address + offset;
        #     result->memory.size = len;
        #     result->memory.flags = ptr->memory.flags;
        #     result->memory.typeSize = ptr->memory.typeSize;
        #     result->data.rbParent = self;

        #     return obj;
        # }

    @classdef.method('+', other='int')
    def method_plus(self, space, other):
        ptr = rffi.ptradd(rffi.cast(rffi.CCHARP, self.ptr), other)
        ptr_val = rffi.cast(lltype.Unsigned, ptr)
        w_ptr_val = space.newint_or_bigint_fromunsigned(ptr_val)
        w_res = space.send(space.getclassfor(W_BufferObject), 'new', [w_ptr_val])
        return w_res

        # /*
        #  * call-seq: + offset
        #  * @param [Numeric] offset
        #  * @return [Buffer] a new instance of Buffer pointing from offset until end of previous buffer.
        #  * Add a Buffer with an offset
        #  */
        # static VALUE
        # buffer_plus(VALUE self, VALUE rbOffset)
        # {
        #     Buffer* ptr;
        #     long offset = NUM2LONG(rbOffset);

        #     Data_Get_Struct(self, Buffer, ptr);

        #     return slice(self, offset, ptr->memory.size - offset);
        # }

    @classdef.method('inspect')
    def method_inspect(self, space):
        return space.newstr_fromstr("#<FFI:Buffer:%s address=%s size=%d>" %
                                    (self, self.ptr, self.sizeof_memory))

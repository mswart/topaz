module FFI
  class AbstractMemory
    %w{int8 uint8 int16 uint16 int32 uint32 int64 uint64 float32 float64 pointer}.each do |type|
      self.class_eval <<-code, __FILE__, __LINE__
      def get_array_of_#{type}(offset, length)
        sizeof = FFI.type_size :#{type}
        length.times.map do |index|
          get_#{type}(offset + index * sizeof)
        end
      end
      def read_array_of_#{type}(length)
        get_array_of_#{type}(0, length)
      end
      def put_array_of_#{type}(offset, array)
        sizeof = FFI.type_size :#{type}
        array.inject(offset) do |offset, value|
          put_#{type}(offset, value)
          offset + sizeof
        end
      end
      def write_array_of_#{type}(array)
        put_array_of_#{type}(0, array)
      end
      code
    end
  end
end

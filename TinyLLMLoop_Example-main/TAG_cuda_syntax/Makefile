# Compiling llm_kernel with nvcc
NVCC = nvcc

# Flags
NVCC_FLAGS = -arch=sm_89 -O3 --compiler-options '-fPIC'

# Get Python and PyTorch paths
PYTHON_INCLUDE = $(shell python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())")
PYTHON_LIB = $(shell python3 -c "import distutils.sysconfig as sysconfig; print(sysconfig.get_config_var('LIBDIR'))")

# Try to get PyTorch paths using pip show
TORCH_PATH = $(shell python3 -c "import torch; print(torch.__path__[0])" 2>/dev/null)
TORCH_INCLUDE = $(TORCH_PATH)/include
TORCH_LIB = $(TORCH_PATH)/lib

# Source files
SRC = $(src_cu)
TARGET = hgemm_llm_kernel.so

# Default target
all: $(TARGET)

# Build target
$(TARGET): $(SRC)
	$(NVCC) $(NVCC_FLAGS) \
	-I$(PYTHON_INCLUDE) \
	-I$(TORCH_INCLUDE) \
	-I$(TORCH_INCLUDE)/torch/csrc/api/include \
	-L$(PYTHON_LIB) \
	-L$(TORCH_LIB) \
	-shared $^ -o $@ \
	-lcublas -lcudart -ltorch -lc10

# Clean up
clean:
	rm -f $(TARGET)

# Phony targets
.PHONY: all clean
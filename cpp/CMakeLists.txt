cmake_minimum_required(VERSION 3.18)
project(av_metrics_cpp CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(av_metrics_cpp metrics_engine.cpp)

# Platform-independent optimization flags
if(MSVC)
  # Windows / MSVC
  target_compile_options(av_metrics_cpp PRIVATE
      /O2 /W4 /WX-
  )
else()
  # GCC / Clang (Linux, macOS)
  target_compile_options(av_metrics_cpp PRIVATE
      -O3 -Wall -Wextra -Wpedantic
  )
  # Only add -march=native on x86/x86_64 — not safe on ARM (Apple Silicon, Jetson)
  if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64|i686")
    target_compile_options(av_metrics_cpp PRIVATE -march=native)
  endif()
endif()

install(TARGETS av_metrics_cpp DESTINATION .)

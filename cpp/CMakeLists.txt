cmake_minimum_required(VERSION 3.18)
project(av_metrics_cpp CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Optimization flags
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(av_metrics_cpp metrics_engine.cpp)

target_compile_options(av_metrics_cpp PRIVATE
    -Wall -Wextra -Wpedantic
)

install(TARGETS av_metrics_cpp DESTINATION .)

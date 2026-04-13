"""Bazel BUILD for C++ metrics extension."""

load("@pybind11_bazel//:build_defs.bzl", "pybind_extension")

# Platform-conditional copts — Bazel select() for cross-platform builds
pybind_extension(
    name = "av_metrics_cpp",
    srcs = ["metrics_engine.cpp"],
    copts = select({
        "@bazel_tools//src/conditions:windows": [
            "/O2",
            "/W4",
            "/std:c++17",
        ],
        "//conditions:default": [
            # GCC / Clang (Linux, macOS)
            "-O3",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-DNDEBUG",
        ],
    }),
    visibility = ["//visibility:public"],
)

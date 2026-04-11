"""Bazel BUILD for C++ metrics extension."""

load("@pybind11_bazel//:build_defs.bzl", "pybind_extension")

pybind_extension(
    name = "av_metrics_cpp",
    srcs = ["metrics_engine.cpp"],
    copts = [
        "-O3",
        "-march=native",
        "-std=c++17",
        "-Wall",
        "-Wextra",
    ],
    visibility = ["//visibility:public"],
)

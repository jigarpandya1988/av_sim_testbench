load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "metrics_lib",
    srcs = glob(["*.py"]),
    visibility = ["//visibility:public"],
    deps = [
        "//runner:runner_lib",
    ],
)

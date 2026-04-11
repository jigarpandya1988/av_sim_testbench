load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "runner_lib",
    srcs = glob(["*.py"]),
    visibility = ["//visibility:public"],
    deps = [
        "//scenarios:scenarios_lib",
    ],
)

load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "replay_lib",
    srcs = glob(["*.py"]),
    visibility = ["//visibility:public"],
    deps = [
        "//metrics:metrics_lib",
    ],
)

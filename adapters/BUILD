load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "adapters_lib",
    srcs = glob(["*.py"]),
    visibility = ["//visibility:public"],
    deps = [
        "//scenarios:scenarios_lib",
        "//runner:runner_lib",
    ],
)

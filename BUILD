# Root Bazel BUILD file

load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

py_binary(
    name = "av_sim_testbench",
    srcs = ["main.py"],
    deps = [
        "//scenarios:scenarios_lib",
        "//runner:runner_lib",
        "//metrics:metrics_lib",
        "//replay:replay_lib",
        "//ml:ml_lib",
    ],
    python_version = "PY3",
)

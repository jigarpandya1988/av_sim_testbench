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
        "//catalog:catalog_lib",
        "//observability:observability_lib",
        "//reports:reports_lib",
    ],
    python_version = "PY3",
    visibility = ["//visibility:public"],
)

py_test(
    name = "all_tests",
    srcs = glob(["tests/**/*.py"]),
    deps = [
        ":av_sim_testbench",
        "//scenarios:scenarios_lib",
        "//runner:runner_lib",
        "//metrics:metrics_lib",
        "//ml:ml_lib",
        "//catalog:catalog_lib",
    ],
    python_version = "PY3",
)

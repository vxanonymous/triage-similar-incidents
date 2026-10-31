"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import generate, link, read, similar

TOOLS = {
    Tool.GENERATE_INCIDENTS: generate,
    Tool.READ_INCIDENT: read,
    Tool.FIND_SIMILAR: similar,
}


def _tool_output(module):
    """A tool task's check: its output judged as its one tool's verify_output judges it."""
    return lambda arguments, output, reference, workspace: module.verify_output(arguments, output, workspace)


# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {
    Task.GENERATE_INCIDENTS: _tool_output(generate),
    Task.FIND_SIMILAR_INCIDENTS: _tool_output(similar),
    Task.LINK_NEW_INCIDENT: link.verify_task,
}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)

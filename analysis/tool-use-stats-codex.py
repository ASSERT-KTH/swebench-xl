import os
import json


TRAJECTORY_DIR = "/Users/pontusberglund/Documents/full-run-trajectories/codex-gpt-5.4-analysis-final/"
INSTANCE_STATS = "/Users/pontusberglund/Documents/GitHub/swebench-xl/analysis/instance_stats_output.json"
RUN_RESULTS_JSON = "/Users/pontusberglund/Documents/full-run-trajectories/codex-gpt-5.4-analysis-final/result.json"


def get_steps(trajectory):
    return trajectory["steps"]

def load_trajectory(file_path):
    with open(file_path, "r") as f:
        trajectory = json.load(f)
    return trajectory

def get_steps_with_tool_calls(steps):
    steps_with_tool_calls = []
    for step in steps:
        if "tool_calls" in step and step["tool_calls"]:
            steps_with_tool_calls.append(step)
    return steps_with_tool_calls

def get_steps_with_wall_clock_time(steps):
    import re
    steps_with_wall_clock_time = []
    for step in steps:
        observation = step.get("observation")
        if not observation:
            continue
        for result in observation.get("results", []):
            content = result.get("content", "")
            match = re.search(r"Wall time:\s*([\d.]+)\s*seconds", content)
            if match:
                steps_with_wall_clock_time.append({
                    **step,
                    "wall_clock_time": float(match.group(1)),
                })
                break
    return steps_with_wall_clock_time

def get_command_and_time(steps):
    import re
    command_and_time = []
    for step in steps:
        extra = step.get("extra", {})
        raw_args = extra.get("raw_arguments", "")
        try:
            args = json.loads(raw_args)
            cmd = args.get("cmd")
        except (json.JSONDecodeError, TypeError):
            continue
        if not cmd:
            continue
        observation = step.get("observation")
        if not observation:
            continue
        for result in observation.get("results", []):
            content = result.get("content", "")
            match = re.search(r"Wall time:\s*([\d.]+)\s*seconds", content)
            if match:
                command_and_time.append((cmd, float(match.group(1))))
                break

    #Sort command and time by time in descending order
    command_and_time.sort(key=lambda x: x[1], reverse=True)
    return command_and_time

def get_all_trajectory_files(trajectory_dir):
    trajectory_file_and_instance_id = []
    for root, _, files in os.walk(trajectory_dir):
        for file in files:
            if file.endswith("trajectory.json"):
                instance_id = os.path.basename(os.path.dirname(root)).rsplit("__", 1)[0]
                trajectory_file_and_instance_id.append((os.path.join(root, file), instance_id))
    return trajectory_file_and_instance_id

def main():
    # Get all steps with tool calls across all trajectories
    all_steps_with_tool_calls = []
    trajectory_files_and_instance_ids = get_all_trajectory_files(TRAJECTORY_DIR)
    for trajectory_file, instance_id in trajectory_files_and_instance_ids:
        trajectory = load_trajectory(trajectory_file)
        steps = get_steps(trajectory)
        steps_with_tool_calls = get_steps_with_tool_calls(steps)
        all_steps_with_tool_calls.extend(steps_with_tool_calls)
    # Print the total number of steps with tool calls
    print(f"Total number of steps with tool calls: {len(all_steps_with_tool_calls)}")

    steps_with_wall_clock_time = []
    for trajectory_file, instance_id in trajectory_files_and_instance_ids:
        trajectory = load_trajectory(trajectory_file)
        steps = get_steps(trajectory)
        steps_with_wall_clock_time.extend(get_steps_with_wall_clock_time(steps))
    print(f"Total number of steps with wall clock time: {len(steps_with_wall_clock_time)}")

    command_and_time = []
    for trajectory_file, instance_id in trajectory_files_and_instance_ids:
        trajectory = load_trajectory(trajectory_file)
        steps = get_steps(trajectory)
        command_and_time.extend(get_command_and_time(steps))
    print(f"Total number of commands with wall clock time: {len(command_and_time)}")

    command_and_time.sort(key=lambda x: x[1], reverse=True)
    print("Top 10 slowest commands:")
    for cmd, time in command_and_time[:10]:
        print(f"Command: {cmd}, Wall clock time: {time} seconds")

if __name__ == "__main__":
    main()
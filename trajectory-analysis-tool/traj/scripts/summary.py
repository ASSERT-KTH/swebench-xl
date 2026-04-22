"""Summary analysis script — basic stats about normalised trajectories."""
from __future__ import annotations
from collections import Counter
from traj.models import TrajectoryResult


def run(trajectories: list[TrajectoryResult]) -> dict:
    """Produce summary statistics across all trajectories."""
    per_trajectory = []

    total_ops = Counter()
    total_sub_agent_ops = 0
    all_read_paths = []
    all_write_paths = []

    for traj in trajectories:
        counts = Counter()
        sub_agent_count = 0
        read_paths = []
        write_paths = []

        for op in traj.operations:
            counts[op.action] += 1
            total_ops[op.action] += 1
            if op.sub_agent:
                sub_agent_count += 1
                total_sub_agent_ops += 1
            if op.action == "Read" and op.path:
                read_paths.append(op.path)
                all_read_paths.append(op.path)
            if op.action == "Write" and op.path:
                write_paths.append(op.path)
                all_write_paths.append(op.path)

        per_trajectory.append({
            "source_file": traj.source_file,
            "agent": traj.agent,
            "total_operations": len(traj.operations),
            "action_counts": dict(counts),
            "sub_agent_operations": sub_agent_count,
            "unique_files_read": len(set(read_paths)),
            "unique_files_written": len(set(write_paths)),
        })

    return {
        "total_trajectories": len(trajectories),
        "total_operations": sum(total_ops.values()),
        "action_counts": dict(total_ops),
        "sub_agent_operations": total_sub_agent_ops,
        "unique_files_read": len(set(all_read_paths)),
        "unique_files_written": len(set(all_write_paths)),
        "per_trajectory": per_trajectory,
    }

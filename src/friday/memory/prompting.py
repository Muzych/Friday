from friday.memory.models import DeepMemorySnapshot, SessionMemorySnapshot


def render_session_block(snapshot: SessionMemorySnapshot) -> str:
    lines = ["Session Memory"]
    if snapshot.goal:
        lines.append(f"Goal: {snapshot.goal}")
    if snapshot.active_tasks:
        lines.append("Active Tasks:")
        lines.extend(f"- {task}" for task in snapshot.active_tasks)
    if snapshot.constraints:
        lines.append("Constraints:")
        lines.extend(f"- {constraint}" for constraint in snapshot.constraints)
    return "\n".join(lines)


def render_deep_block(snapshot: DeepMemorySnapshot) -> str:
    lines = ["Deep Memory"]
    if snapshot.preferences:
        lines.append("Preferences:")
        lines.extend(f"- {preference}" for preference in snapshot.preferences)
    if snapshot.profile_facts:
        lines.append("Profile Facts:")
        lines.extend(f"- {fact}" for fact in snapshot.profile_facts)
    if snapshot.long_running_projects:
        lines.append("Long-Running Projects:")
        lines.extend(f"- {project}" for project in snapshot.long_running_projects)
    if snapshot.stable_workflows:
        lines.append("Stable Workflows:")
        lines.extend(f"- {workflow}" for workflow in snapshot.stable_workflows)
    return "\n".join(lines)


def render_memory_blocks(
    session: SessionMemorySnapshot | None,
    deep: DeepMemorySnapshot | None,
) -> str:
    sections: list[str] = []
    if session is not None:
        sections.append(render_session_block(session))
    if deep is not None:
        sections.append(render_deep_block(deep))
    return "\n\n".join(section for section in sections if section.strip())

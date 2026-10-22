from scripts.orchestrator.checkpoint_manager import STAGES


def affected_stages(stage: str) -> tuple[str, ...]:
    """The current linear DAG; upstream artifacts remain available and valid."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    return STAGES[STAGES.index(stage):]

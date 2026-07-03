"""
ValidationIOLogger: Centralized logging for all validator LLM interactions.

Captures every input/output from GPT-5.2 validator calls for debugging and analysis.
Logs are saved to validation_reports/ directory.
"""
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager


@dataclass
class ValidatorInteraction:
    """Single validator LLM call with full input/output capture."""
    timestamp: str
    validator_name: str       # e.g., "ChemicalAccuracyValidator"
    method_name: str          # e.g., "validate", "_llm_validate"
    step: int                 # Reaction step being validated

    # Full input capture
    system_message: str       # Complete system prompt
    user_message: str         # Complete user prompt (includes reaction data)

    # Full output capture
    raw_response: str = ""         # Raw GPT-5.2 response string
    parsed_response: Optional[Dict[str, Any]] = None  # Parsed JSON if applicable

    # Metadata
    model: str = "gpt-5.2"         # Model used
    reasoning_effort: str = "high" # Reasoning level
    duration_ms: float = 0.0       # Time taken for LLM call
    success: bool = False          # Whether call succeeded
    error_message: Optional[str] = None  # Error if failed

    # Validation result summary
    score: Optional[float] = None  # Score from this validator
    issues_found: Optional[int] = None  # Number of issues found


class ValidationIOLogger:
    """
    Logger for all validator LLM interactions.

    Writes to JSON Lines format in validation_reports/ directory.
    Each validation run gets its own log file.
    """

    def __init__(
        self,
        synthesis_file: str,
        output_dir: str = "validation_reports"
    ):
        """
        Initialize the validation I/O logger.

        Args:
            synthesis_file: Path to synthesis file being validated (used in filename)
            output_dir: Directory for log files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Extract synthesis filename for log naming
        synthesis_name = Path(synthesis_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.log_file = self.output_dir / f"{synthesis_name}_io_{timestamp}.jsonl"
        self.summary_file = self.output_dir / f"{synthesis_name}_summary_{timestamp}.json"

        self._interactions: list = []
        self._start_time = datetime.now()

        # Write header
        with open(self.log_file, 'w') as f:
            f.write(f"# ValidationIOLogger: {synthesis_name} - {timestamp}\n")
            f.write(f"# Model: GPT-5.2 with reasoning=high\n")
            f.flush()

    def log_interaction(self, interaction: ValidatorInteraction) -> None:
        """
        Append interaction to JSONL file.

        Args:
            interaction: The validator interaction to log
        """
        self._interactions.append(interaction)

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(asdict(interaction), default=str) + '\n')
            f.flush()

    def get_log_path(self) -> str:
        """Return the path to the log file."""
        return str(self.log_file)

    def get_summary(self) -> Dict[str, Any]:
        """Generate a summary of all logged interactions."""
        if not self._interactions:
            return {"total_calls": 0}

        total_duration = sum(i.duration_ms for i in self._interactions)
        successful = sum(1 for i in self._interactions if i.success)

        by_validator = {}
        for i in self._interactions:
            if i.validator_name not in by_validator:
                by_validator[i.validator_name] = {
                    "calls": 0,
                    "successful": 0,
                    "total_duration_ms": 0,
                    "avg_score": []
                }
            by_validator[i.validator_name]["calls"] += 1
            by_validator[i.validator_name]["total_duration_ms"] += i.duration_ms
            if i.success:
                by_validator[i.validator_name]["successful"] += 1
            if i.score is not None:
                by_validator[i.validator_name]["avg_score"].append(i.score)

        # Calculate averages
        for v in by_validator.values():
            scores = v["avg_score"]
            v["avg_score"] = sum(scores) / len(scores) if scores else None

        return {
            "total_calls": len(self._interactions),
            "successful_calls": successful,
            "failed_calls": len(self._interactions) - successful,
            "total_duration_ms": total_duration,
            "avg_duration_ms": total_duration / len(self._interactions),
            "by_validator": by_validator,
            "log_file": str(self.log_file)
        }

    def save_summary(self) -> str:
        """Save summary to JSON file and return path."""
        summary = self.get_summary()
        summary["validation_started"] = self._start_time.isoformat()
        summary["validation_ended"] = datetime.now().isoformat()

        with open(self.summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        return str(self.summary_file)


@asynccontextmanager
async def log_validator_call(
    logger: Optional[ValidationIOLogger],
    validator_name: str,
    method_name: str,
    step: int,
    system_message: str,
    user_message: str,
    model: str = "gpt-5.2",
    reasoning_effort: str = "high"
):
    """
    Async context manager to log validator LLM calls with timing.

    Usage:
        async with log_validator_call(logger, "ChemicalAccuracyValidator", "validate", 1, sys, user) as interaction:
            response = await client.create_with_reasoning(...)
            interaction.raw_response = response
            interaction.parsed_response = parsed_data
            interaction.score = result.score

    Args:
        logger: ValidationIOLogger instance (or None to skip logging)
        validator_name: Name of the validator
        method_name: Name of the method being called
        step: Reaction step being validated
        system_message: Complete system prompt
        user_message: Complete user prompt
        model: Model name
        reasoning_effort: Reasoning effort level

    Yields:
        ValidatorInteraction object that caller can populate with response data
    """
    start_time = time.time()

    interaction = ValidatorInteraction(
        timestamp=datetime.now().isoformat(),
        validator_name=validator_name,
        method_name=method_name,
        step=step,
        system_message=system_message,
        user_message=user_message,
        raw_response="",
        parsed_response=None,
        model=model,
        reasoning_effort=reasoning_effort,
        duration_ms=0.0,
        success=False,
        error_message=None,
        score=None,
        issues_found=None
    )

    try:
        yield interaction
        interaction.success = True
    except Exception as e:
        interaction.error_message = str(e)
        raise
    finally:
        interaction.duration_ms = (time.time() - start_time) * 1000
        if logger:
            logger.log_interaction(interaction)

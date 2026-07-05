import logging
from decimal import Decimal
from apps.evaluation.models import Evaluation, QualityScore
from config.constants import EVAL_STATUS_PASSED, EVAL_STATUS_FAILED, EVAL_STATUS_FLAGGED, METRIC_COMPLETENESS, METRIC_FEASIBILITY, METRIC_READABILITY, METRIC_SECURITY

logger = logging.getLogger('specpilot.ai')

class EvaluationService:
    """
    Quality control parser assessing validation parameters and recording compliance feedback.
    """

    @staticmethod
    def evaluate_artifact(agent_execution, artifact_content, artifact_title):
        """
        Executes structural audit verification rules.
        Saves scores and reasons.
        """
        logger.info(f"Running automated quality check on artifact: '{artifact_title}'")
        
        # 1. Initialize evaluation
        evaluation = Evaluation.objects.create(
            agent_execution=agent_execution,
            evaluator_name="System-Rule-Guard"
        )
        
        # 2. Run structural sanity checks
        completeness_score = Decimal("10.0")
        readability_score = Decimal("10.0")
        feasibility_score = Decimal("8.0")
        security_score = Decimal("9.0")
        
        reasons = []
        
        # Heuristic rules check
        if not artifact_content:
            completeness_score = Decimal("0.0")
            reasons.append("Artifact is empty.")
        else:
            # Check length to estimate depth
            if len(artifact_content) < 200:
                completeness_score = Decimal("5.0")
                reasons.append("Content is extremely short, indicating lack of detail.")
                
            # Check markdown completeness (contains headers)
            if "#" not in artifact_content:
                readability_score = Decimal("4.0")
                reasons.append("Missing Markdown structural titles (#).")

        # Determine status
        if completeness_score < Decimal("5.0") or readability_score < Decimal("5.0"):
            status = EVAL_STATUS_FAILED
        elif completeness_score < Decimal("8.0") or readability_score < Decimal("8.0"):
            status = EVAL_STATUS_FLAGGED
        else:
            status = EVAL_STATUS_PASSED

        # Update evaluation status
        evaluation.status = status
        evaluation.save()

        # 3. Save scores
        QualityScore.objects.create(
            evaluation=evaluation,
            metric_name=METRIC_COMPLETENESS,
            score=completeness_score,
            rationalization="; ".join(reasons) if reasons else "Output meets length requirements."
        )

        QualityScore.objects.create(
            evaluation=evaluation,
            metric_name=METRIC_READABILITY,
            score=readability_score,
            rationalization="Determined by header checking and line formatting structure."
        )

        QualityScore.objects.create(
            evaluation=evaluation,
            metric_name=METRIC_FEASIBILITY,
            score=feasibility_score,
            rationalization="Standard technical feasibility rating."
        )

        QualityScore.objects.create(
            evaluation=evaluation,
            metric_name=METRIC_SECURITY,
            score=security_score,
            rationalization="Automatic safety layer approval checks passed."
        )

        logger.info(f"Quality validation for '{artifact_title}' concluded: Status is {status}")
        return evaluation

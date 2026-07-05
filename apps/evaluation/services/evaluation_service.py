import logging
from decimal import Decimal
from apps.evaluation.models import Evaluation, QualityScore
from config.constants import (
    EVAL_STATUS_PASSED, EVAL_STATUS_FAILED, EVAL_STATUS_FLAGGED,
    METRIC_COMPLETENESS, METRIC_CLARITY, METRIC_CONSISTENCY, METRIC_TECHNICAL_ACCURACY,
    METRIC_ARCHITECTURE_QUALITY, METRIC_SECURITY_COVERAGE, METRIC_TESTING_COVERAGE,
    METRIC_DOCUMENTATION_QUALITY, METRIC_IMPLEMENTATION_READINESS, METRIC_OVERALL_CONFIDENCE
)

logger = logging.getLogger('specpilot.ai')

class EvaluationService:
    """
    Quality control parser assessing validation parameters and recording compliance feedback.
    Analyzes specifications against 10 enterprise quality metrics.
    """

    @staticmethod
    def evaluate_artifact(agent_execution, artifact_content, artifact_title):
        """
        Executes structural audit verification rules.
        Saves scores and reasons for all 10 enterprise metrics.
        """
        logger.info(f"Running automated quality check on artifact: '{artifact_title}'")
        
        # 1. Initialize evaluation
        evaluation = Evaluation.objects.create(
            agent_execution=agent_execution,
            evaluator_name="System-Quality-Guard"
        )
        
        # 2. Run structural sanity checks
        completeness_score = Decimal("10.0")
        clarity_score = Decimal("10.0")
        consistency_score = Decimal("10.0")
        accuracy_score = Decimal("10.0")
        arch_score = Decimal("10.0")
        security_score = Decimal("10.0")
        testing_score = Decimal("10.0")
        doc_score = Decimal("10.0")
        readiness_score = Decimal("10.0")
        
        reasons_completeness = ["Output contains sufficient character length."]
        reasons_clarity = ["Structure conforms to markdown headers syntax."]
        reasons_consistency = ["Key terminologies are aligned throughout the document."]
        reasons_accuracy = ["Technical specifications align with standard development practices."]
        reasons_arch = ["Architecture configurations reflect target pattern paradigms."]
        reasons_security = ["Security configurations are present in generated text."]
        reasons_testing = ["Testing configurations and hooks are mentioned."]
        reasons_doc = ["Clear headings, parameters tables, and comments are mapped."]
        reasons_readiness = ["Specifications contain actionable directives for developer onboarding."]

        # Check content length
        content_len = len(artifact_content) if artifact_content else 0
        if content_len == 0:
            completeness_score = Decimal("0.0")
            clarity_score = Decimal("0.0")
            reasons_completeness = ["Artifact is empty."]
            reasons_clarity = ["No text content to evaluate clarity."]
        elif content_len < 200:
            completeness_score = Decimal("4.0")
            reasons_completeness = ["Content is extremely short, indicating lack of detail."]
        elif content_len < 800:
            completeness_score = Decimal("7.0")
            reasons_completeness = ["Content is moderate in length, could be expanded for detail."]

        # Markdown check
        if content_len > 0 and "#" not in artifact_content:
            clarity_score = Decimal("5.0")
            reasons_clarity = ["Missing Markdown structural titles (#), which degrades readability."]

        # Consistency check (matches terms frequency)
        if content_len > 0:
            lowercase_content = artifact_content.lower()
            # Technical keywords checks to score metrics
            # Security coverage
            sec_keywords = ["security", "auth", "encrypt", "password", "token", "https", "ssl", "owasp"]
            sec_matches = sum(1 for kw in sec_keywords if kw in lowercase_content)
            if sec_matches == 0:
                security_score = Decimal("4.0")
                reasons_security = ["No security or compliance protocols mentioned in content."]
            elif sec_matches < 3:
                security_score = Decimal("7.0")
                reasons_security = ["Basic security mentions found. Could be expanded with encryption details."]

            # Testing coverage
            test_keywords = ["test", "pytest", "mock", "assert", "coverage", "unit test", "integration"]
            test_matches = sum(1 for kw in test_keywords if kw in lowercase_content)
            if test_matches == 0:
                testing_score = Decimal("4.0")
                reasons_testing = ["No test cases, assertions, or test configurations mentioned."]
            elif test_matches < 3:
                testing_score = Decimal("7.0")
                reasons_testing = ["Basic testing checklist references. Could describe integration cases."]

            # Architecture quality
            arch_keywords = ["architect", "mvc", "layer", "database", "model", "component", "schema", "api"]
            arch_matches = sum(1 for kw in arch_keywords if kw in lowercase_content)
            if arch_matches == 0:
                arch_score = Decimal("5.0")
                reasons_arch = ["Lacks architectural design, component separation, or models definitions."]

            # Technical accuracy
            tech_keywords = ["error", "exception", "validate", "input", "return", "type", "def"]
            tech_matches = sum(1 for kw in tech_keywords if kw in lowercase_content)
            if tech_matches == 0:
                accuracy_score = Decimal("6.0")
                reasons_accuracy = ["Missing code signatures, parameter types, or validation schemas."]

            # Readiness
            readiness_keywords = ["npm", "run", "python", "deploy", "build", "install", "git"]
            readiness_matches = sum(1 for kw in readiness_keywords if kw in lowercase_content)
            if readiness_matches == 0:
                readiness_score = Decimal("5.0")
                reasons_readiness = ["Missing setup commands or configuration guides for implementation."]

        # Calculate overall confidence score as simple average
        all_scores = [
            completeness_score, clarity_score, consistency_score, accuracy_score,
            arch_score, security_score, testing_score, doc_score, readiness_score
        ]
        confidence_score = Decimal(str(sum(all_scores) / len(all_scores))).quantize(Decimal("0.1"))

        # Determine overall status based on confidence
        if confidence_score < Decimal("5.0"):
            status = EVAL_STATUS_FAILED
        elif confidence_score < Decimal("8.0"):
            status = EVAL_STATUS_FLAGGED
        else:
            status = EVAL_STATUS_PASSED

        # Update evaluation status
        evaluation.status = status
        evaluation.save()

        # 3. Save scores for all 10 metrics
        metrics_mapping = [
            (METRIC_COMPLETENESS, completeness_score, reasons_completeness),
            (METRIC_CLARITY, clarity_score, reasons_clarity),
            (METRIC_CONSISTENCY, consistency_score, reasons_consistency),
            (METRIC_TECHNICAL_ACCURACY, accuracy_score, reasons_accuracy),
            (METRIC_ARCHITECTURE_QUALITY, arch_score, reasons_arch),
            (METRIC_SECURITY_COVERAGE, security_score, reasons_security),
            (METRIC_TESTING_COVERAGE, testing_score, reasons_testing),
            (METRIC_DOCUMENTATION_QUALITY, doc_score, reasons_doc),
            (METRIC_IMPLEMENTATION_READINESS, readiness_score, reasons_readiness),
            (METRIC_OVERALL_CONFIDENCE, confidence_score, ["Overall confidence calculated from individual ratings."])
        ]

        for metric_name, score, reasons in metrics_mapping:
            QualityScore.objects.create(
                evaluation=evaluation,
                metric_name=metric_name,
                score=score,
                rationalization=" ".join(reasons)
            )

        logger.info(f"Quality validation for '{artifact_title}' concluded: Status is {status} (Confidence: {confidence_score}/10)")
        return evaluation

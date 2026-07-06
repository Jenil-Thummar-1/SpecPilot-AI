import time
import logging
from django.db import connection

logger = logging.getLogger('specpilot.profiler')

class PerformanceProfiler:
    """
    轻量级性能分析器 Context Manager.
    Captures duration, database queries count, and details for every phase.
    """
    _records = {}

    def __init__(self, step_id, component_name):
        self.step_id = step_id
        self.component_name = component_name
        self.start_time = None
        self.start_queries = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        self.start_queries = len(connection.queries)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        queries_run = len(connection.queries) - self.start_queries
        
        if self.step_id not in self._records:
            self._records[self.step_id] = []
        
        self._records[self.step_id].append({
            "component": self.component_name,
            "duration_seconds": duration,
            "queries": queries_run
        })
        logger.info(f"[PROFILER] Step {self.step_id} - Component {self.component_name} took {duration:.4f}s with {queries_run} SQL queries.")

    @classmethod
    def get_records(cls, step_id):
        return cls._records.get(step_id, [])

    @classmethod
    def clear_records(cls, step_id):
        if step_id in cls._records:
            del cls._records[step_id]


class BottleneckAnalyzer:
    """
    Analyzes step profiling records to detect slow queries or API latency,
    returning concrete optimization suggestions.
    """
    @classmethod
    def analyze(cls, step_id):
        records = PerformanceProfiler.get_records(step_id)
        if not records:
            return {
                "summary": "No profiling records available.",
                "recommendations": []
            }
            
        sorted_records = sorted(records, key=lambda x: x["duration_seconds"], reverse=True)
        
        recommendations = []
        for r in sorted_records[:2]:
            comp = r["component"]
            dur = r["duration_seconds"]
            if comp == "Gemini Generation" and dur > 1.5:
                recommendations.append("Primary bottleneck is API Generation. Use Cache or lower temperature.")
            elif comp == "Context Loading" and r["queries"] > 5:
                recommendations.append("Context loading executed too many queries. Use preloaded context caching.")
            elif comp == "Database Saving" and dur > 0.5:
                recommendations.append("Database saving is slow. Batch edits using transaction blocks.")

        if not recommendations:
            recommendations.append("Performance looks optimal. No bottlenecks detected.")

        return {
            "summary": [f"{r['component']}: {r['duration_seconds']:.3f}s ({r['queries']} queries)" for r in sorted_records],
            "recommendations": recommendations
        }

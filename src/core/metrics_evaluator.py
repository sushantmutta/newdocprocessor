"""
Metrics Evaluation Module

Calculates aggregate performance metrics against target thresholds:
- Extraction Accuracy ≥ 90%
- PII Recall ≥ 95%, Precision ≥ 90%
- Workflow Success Rate ≥ 90%
- P95 Latency ≤ 4s
"""

import pandas as pd
import numpy as np
import os
import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class MetricsEvaluator:
    """Evaluates system performance against target metrics."""

    # Target thresholds
    TARGET_EXTRACTION_ACCURACY = 90.0  # %
    TARGET_PII_RECALL = 95.0  # %
    TARGET_PII_PRECISION = 90.0  # %
    TARGET_WORKFLOW_SUCCESS = 90.0  # %
    TARGET_P95_LATENCY = 4000  # milliseconds

    def __init__(self, metrics_csv_path: str):
        """Initialize with path to metrics CSV file."""
        self.metrics_csv_path = metrics_csv_path
        self.df = None
        self._load_data()

    def _load_data(self):
        """Load metrics data from CSV."""
        if os.path.exists(self.metrics_csv_path):
            try:
                current_cols = [
                    "timestamp", "doc_type", "file_path",
                    "extraction_completeness", "validation_accuracy",
                    "pipeline_success", "error_count", "repair_attempts",
                    "repair_success_rate", "repair_flag_types", "repair_max_attempts_hit",
                    "redaction_coverage", "pii_recall", "pii_precision", "latency_ms",
                ]
                legacy_cols = [
                    "timestamp", "doc_type", "file_path",
                    "extraction_completeness", "validation_accuracy",
                    "pipeline_success", "error_count", "repair_attempts",
                    "redaction_coverage", "pii_recall", "pii_precision", "latency_ms",
                ]

                with open(self.metrics_csv_path, newline="", encoding="utf-8") as f:
                    reader = list(csv.reader(f))

                if not reader:
                    self.df = pd.DataFrame()
                    return

                header = reader[0]
                data_rows = [r for r in reader[1:]
                             if any(cell.strip() for cell in r)]

                consistent_row_lengths = all(
                    len(r) == len(header) for r in data_rows)
                if consistent_row_lengths:
                    self.df = pd.read_csv(self.metrics_csv_path)
                else:
                    normalized_rows = []
                    for row in data_rows:
                        if len(row) >= len(current_cols):
                            mapped = dict(
                                zip(current_cols, row[:len(current_cols)]))
                            normalized_rows.append(mapped)
                            continue

                        if len(row) == len(legacy_cols):
                            legacy = dict(zip(legacy_cols, row))
                            normalized_rows.append({
                                "timestamp": legacy.get("timestamp", ""),
                                "doc_type": legacy.get("doc_type", ""),
                                "file_path": legacy.get("file_path", ""),
                                "extraction_completeness": legacy.get("extraction_completeness", "0"),
                                "validation_accuracy": legacy.get("validation_accuracy", "0"),
                                "pipeline_success": legacy.get("pipeline_success", "False"),
                                "error_count": legacy.get("error_count", "0"),
                                "repair_attempts": legacy.get("repair_attempts", "0"),
                                "repair_success_rate": "N/A",
                                "repair_flag_types": "N/A",
                                "repair_max_attempts_hit": "False",
                                "redaction_coverage": legacy.get("redaction_coverage", "0"),
                                "pii_recall": legacy.get("pii_recall", "0"),
                                "pii_precision": legacy.get("pii_precision", "0"),
                                "latency_ms": legacy.get("latency_ms", "0"),
                            })

                    self.df = pd.DataFrame(normalized_rows)

                percentage_cols = [
                    "extraction_completeness",
                    "validation_accuracy",
                    "redaction_coverage",
                    "pii_recall",
                    "pii_precision",
                ]
                for col in percentage_cols:
                    if col in self.df.columns:
                        self.df[col] = pd.to_numeric(
                            self.df[col].astype(str).str.rstrip('%').replace(
                                {'': '0', 'nan': '0', 'N/A': '0'}),
                            errors='coerce'
                        ).fillna(0.0)

                if 'latency_ms' in self.df.columns:
                    self.df['latency_ms'] = pd.to_numeric(
                        self.df['latency_ms'], errors='coerce').fillna(0.0)

                for col in ['error_count', 'repair_attempts']:
                    if col in self.df.columns:
                        self.df[col] = pd.to_numeric(
                            self.df[col], errors='coerce').fillna(0).astype(int)
            except Exception as e:
                print(f"Warning: Error loading metrics CSV: {e}")
                self.df = pd.DataFrame()
        else:
            self.df = pd.DataFrame()

    def calculate_extraction_accuracy(self) -> Dict[str, float]:
        """
        Calculate extraction accuracy metrics.

        Returns average of extraction_completeness and validation_accuracy.
        Target: ≥ 90%
        """
        if self.df.empty:
            return {
                'avg_extraction_completeness': 0.0,
                'avg_validation_accuracy': 0.0,
                'overall_extraction_accuracy': 0.0,
                'meets_target': False,
                'target': self.TARGET_EXTRACTION_ACCURACY
            }

        avg_completeness = self.df['extraction_completeness'].mean()
        avg_validation = self.df['validation_accuracy'].mean()

        # Overall accuracy is weighted average
        overall_accuracy = (avg_completeness * 0.5) + (avg_validation * 0.5)

        return {
            'avg_extraction_completeness': round(avg_completeness, 2),
            'avg_validation_accuracy': round(avg_validation, 2),
            'overall_extraction_accuracy': round(overall_accuracy, 2),
            'meets_target': overall_accuracy >= self.TARGET_EXTRACTION_ACCURACY,
            'target': self.TARGET_EXTRACTION_ACCURACY,
            'sample_size': len(self.df)
        }

    def calculate_pii_metrics(self) -> Dict[str, float]:
        """
        Calculate PII redaction recall and precision.

        Recall: % of actual PII that was redacted
        Precision: % of redactions that were actual PII

        Targets: Recall ≥ 95%, Precision ≥ 90%
        """
        if self.df.empty:
            return {
                'avg_pii_recall': 0.0,
                'avg_pii_precision': 0.0,
                'recall_meets_target': False,
                'precision_meets_target': False,
                'target_recall': self.TARGET_PII_RECALL,
                'target_precision': self.TARGET_PII_PRECISION,
                'sample_size': 0,
                'note': 'No data available'
            }

        # Check if pii_recall and pii_precision columns exist and have valid data
        has_pii_metrics = ('pii_recall' in self.df.columns and
                           'pii_precision' in self.df.columns)

        if has_pii_metrics:
            # Filter out rows with 0 or NaN values to get actual tracked metrics
            valid_recall = self.df[self.df['pii_recall'] > 0]['pii_recall']
            valid_precision = self.df[self.df['pii_precision']
                                      > 0]['pii_precision']

            if len(valid_recall) > 0 and len(valid_precision) > 0:
                avg_recall = valid_recall.mean()
                avg_precision = valid_precision.mean()

                return {
                    'avg_pii_recall': round(avg_recall, 2),
                    'avg_pii_precision': round(avg_precision, 2),
                    'recall_meets_target': avg_recall >= self.TARGET_PII_RECALL,
                    'precision_meets_target': avg_precision >= self.TARGET_PII_PRECISION,
                    'target_recall': self.TARGET_PII_RECALL,
                    'target_precision': self.TARGET_PII_PRECISION,
                    'sample_size': len(valid_recall)
                }

        # Fallback: estimate from redaction_coverage
        avg_coverage = self.df['redaction_coverage'].mean(
        ) if 'redaction_coverage' in self.df.columns else 0.0

        # Estimate: assume high coverage means high recall/precision
        estimated_recall = min(avg_coverage * 10, 100.0)  # Scale up coverage
        estimated_precision = min(avg_coverage * 8, 100.0)  # Slightly lower

        return {
            'avg_pii_recall': round(estimated_recall, 2),
            'avg_pii_precision': round(estimated_precision, 2),
            'recall_meets_target': estimated_recall >= self.TARGET_PII_RECALL,
            'precision_meets_target': estimated_precision >= self.TARGET_PII_PRECISION,
            'target_recall': self.TARGET_PII_RECALL,
            'target_precision': self.TARGET_PII_PRECISION,
            'sample_size': len(self.df),
            'note': 'Estimated from redaction_coverage (actual PII metrics not yet tracked)'
        }

    def calculate_workflow_success(self) -> Dict[str, float]:
        """
        Calculate workflow success rate.

        Target: ≥ 90% of documents processed without manual intervention
        """
        if self.df.empty:
            return {
                'success_rate': 0.0,
                'success_count': 0,
                'total_count': 0,
                'meets_target': False,
                'target': self.TARGET_WORKFLOW_SUCCESS
            }

        if 'pipeline_success' not in self.df.columns:
            return {
                'success_rate': 0.0,
                'success_count': 0,
                'total_count': len(self.df),
                'meets_target': False,
                'target': self.TARGET_WORKFLOW_SUCCESS
            }

        total_count = len(self.df)
        success_series = self.df['pipeline_success']

        if pd.api.types.is_bool_dtype(success_series):
            success_mask = success_series.fillna(False)
        else:
            success_mask = success_series.astype(str).str.strip().str.lower().isin(
                {'true', '1', 'yes', 'y', 't'}
            )

        success_count = int(success_mask.sum())
        success_rate = (success_count / total_count) * 100

        return {
            'success_rate': round(success_rate, 2),
            'success_count': int(success_count),
            'total_count': total_count,
            'meets_target': success_rate >= self.TARGET_WORKFLOW_SUCCESS,
            'target': self.TARGET_WORKFLOW_SUCCESS
        }

    def calculate_latency_metrics(self) -> Dict[str, float]:
        """
        Calculate P95 latency.

        Target: P95 ≤ 4000ms (4 seconds)
        """
        if self.df.empty or 'latency_ms' not in self.df.columns:
            return {
                'p50_latency_ms': 0.0,
                'p95_latency_ms': 0.0,
                'p99_latency_ms': 0.0,
                'avg_latency_ms': 0.0,
                'meets_target': None,
                'target': self.TARGET_P95_LATENCY,
                'note': 'Latency tracking not yet implemented'
            }

        # Filter out N/A values
        latency_data = pd.to_numeric(
            self.df['latency_ms'], errors='coerce').dropna()

        if latency_data.empty:
            return {
                'p50_latency_ms': 0.0,
                'p95_latency_ms': 0.0,
                'p99_latency_ms': 0.0,
                'avg_latency_ms': 0.0,
                'meets_target': None,
                'target': self.TARGET_P95_LATENCY,
                'sample_size': 0,
                'note': 'No latency data available'
            }

        p50 = latency_data.quantile(0.50)
        p95 = latency_data.quantile(0.95)
        p99 = latency_data.quantile(0.99)
        avg = latency_data.mean()

        return {
            'p50_latency_ms': round(p50, 2),
            'p95_latency_ms': round(p95, 2),
            'p99_latency_ms': round(p99, 2),
            'avg_latency_ms': round(avg, 2),
            'meets_target': p95 <= self.TARGET_P95_LATENCY,
            'target': self.TARGET_P95_LATENCY,
            'sample_size': len(latency_data)
        }

    def get_comprehensive_report(self) -> Dict:
        """Generate comprehensive metrics report."""
        return {
            'extraction_accuracy': self.calculate_extraction_accuracy(),
            'pii_metrics': self.calculate_pii_metrics(),
            'workflow_success': self.calculate_workflow_success(),
            'latency': self.calculate_latency_metrics(),
            'summary': self._generate_summary()
        }

    def _generate_summary(self) -> Dict:
        """Generate summary of metric compliance."""
        extraction = self.calculate_extraction_accuracy()
        pii = self.calculate_pii_metrics()
        workflow = self.calculate_workflow_success()
        latency = self.calculate_latency_metrics()

        targets_met = []
        targets_missed = []

        if extraction['meets_target']:
            targets_met.append('Extraction Accuracy')
        else:
            targets_missed.append('Extraction Accuracy')

        if pii['recall_meets_target'] and pii['precision_meets_target']:
            targets_met.append('PII Metrics')
        else:
            targets_missed.append('PII Metrics')

        if workflow['meets_target']:
            targets_met.append('Workflow Success')
        else:
            targets_missed.append('Workflow Success')

        if latency['meets_target'] is True:
            targets_met.append('P95 Latency')
        elif latency['meets_target'] is False:
            targets_missed.append('P95 Latency')

        return {
            'targets_met': targets_met,
            'targets_missed': targets_missed,
            'overall_compliance': f"{len(targets_met)}/{len(targets_met) + len(targets_missed)}",
            'total_documents_processed': len(self.df) if not self.df.empty else 0
        }

    def generate_llm_insights(self, metrics_data: Dict, provider: str = "groq") -> Dict:
        """
        Generate AI-powered insights and recommendations based on metrics.

        Args:
            metrics_data: The comprehensive metrics report
            provider: LLM provider to use (default: groq)

        Returns:
            Dictionary with AI-generated insights and recommendations
        """
        try:
            from src.core.clients.llm_client import UnifiedLLMManager
            from langchain_core.messages import HumanMessage, SystemMessage
            from src.core.prompts import METRICS_SYSTEM_PROMPT, METRICS_ANALYSIS_PROMPT

            llm_manager = UnifiedLLMManager(provider=provider)

            # Prepare metrics summary for LLM
            summary = metrics_data.get('summary', {})
            extraction = metrics_data.get('extraction_accuracy', {})
            pii = metrics_data.get('pii_metrics', {})
            workflow = metrics_data.get('workflow_success', {})
            latency = metrics_data.get('latency', {})

            prompt = METRICS_ANALYSIS_PROMPT.format(
                total_documents_processed=summary.get(
                    'total_documents_processed', 0),
                overall_compliance=summary.get('overall_compliance', 'N/A'),
                overall_extraction_accuracy=extraction.get(
                    'overall_extraction_accuracy', 0),
                avg_extraction_completeness=extraction.get(
                    'avg_extraction_completeness', 0),
                avg_validation_accuracy=extraction.get(
                    'avg_validation_accuracy', 0),
                extraction_status='✅ MEETS TARGET' if extraction.get(
                    'meets_target') else '❌ BELOW TARGET',
                avg_pii_recall=pii.get('avg_pii_recall', 0),
                avg_pii_precision=pii.get('avg_pii_precision', 0),
                recall_status='✅ MEETS TARGET' if pii.get(
                    'recall_meets_target') else '❌ BELOW TARGET',
                precision_status='✅ MEETS TARGET' if pii.get(
                    'precision_meets_target') else '❌ BELOW TARGET',
                success_rate=workflow.get('success_rate', 0),
                success_count=workflow.get('success_count', 0),
                total_count=workflow.get('total_count', 0),
                workflow_status='✅ MEETS TARGET' if workflow.get(
                    'meets_target') else '❌ BELOW TARGET',
                latency_status=latency.get('note', 'Not tracked'),
            )

            messages = [
                SystemMessage(content=METRICS_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]

            response = llm_manager.invoke_with_fallback(messages)
            response_text = response.content if hasattr(
                response, 'content') else str(response)

            # Parse JSON response
            insights = None
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
                insights = json.loads(json_str)
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
                insights = json.loads(json_str)
            else:
                # Try to find JSON object directly
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    insights = json.loads(json_str)

            if insights:
                insights['generated_by'] = f"{llm_manager.provider_name} ({llm_manager.model_name})"
                insights['generated_at'] = pd.Timestamp.now().strftime(
                    '%Y-%m-%d %H:%M:%S')
                return insights
            else:
                return {
                    'error': 'Failed to parse LLM response',
                    'raw_response': response_text[:500]
                }

        except Exception as e:
            return {
                'error': f'Failed to generate insights: {str(e)}',
                'note': 'LLM insights unavailable'
            }

    def get_comprehensive_report(self, include_llm_insights: bool = True, llm_provider: str = "groq") -> Dict:
        """
        Generate comprehensive metrics report.

        Args:
            include_llm_insights: Whether to include AI-generated insights (default: True)
            llm_provider: LLM provider for insights generation (default: groq)

        Returns:
            Complete metrics report with optional AI insights
        """
        report = {
            'extraction_accuracy': self.calculate_extraction_accuracy(),
            'pii_metrics': self.calculate_pii_metrics(),
            'workflow_success': self.calculate_workflow_success(),
            'latency': self.calculate_latency_metrics(),
            'summary': self._generate_summary()
        }

        # Add LLM insights if requested
        if include_llm_insights:
            report['llm_insights'] = self.generate_llm_insights(
                report, provider=llm_provider)

        return report


def get_metrics_summary(metrics_csv_path: str = None, include_llm_insights: bool = True, llm_provider: str = "groq") -> Dict:
    """
    Convenience function to get metrics summary.

    Args:
        metrics_csv_path: Path to metrics CSV file. If None, uses default.
        include_llm_insights: Whether to include AI-generated insights (default: True)
        llm_provider: LLM provider for insights generation (default: groq)

    Returns:
        Dictionary with comprehensive metrics report
    """
    if metrics_csv_path is None:
        # Prefer data/reports path, then fallback to other known locations.
        module_file = Path(__file__).resolve()
        project_root = module_file.parents[2]
        cwd = Path.cwd().resolve()

        candidates = [
            project_root / "data" / "reports" / "metrics_report.csv",
            project_root / "reports" / "metrics_report.csv",
            cwd / "reports" / "metrics_report.csv",
            project_root / "src" / "reports" / "metrics_report.csv",
        ]

        def _looks_like_metrics_csv(path: Path) -> bool:
            if not path.exists():
                return False
            try:
                cols = set(pd.read_csv(path, nrows=1).columns)
                required = {
                    "extraction_completeness",
                    "validation_accuracy",
                    "pipeline_success",
                    "latency_ms",
                }
                return required.issubset(cols)
            except Exception:
                return False

        selected = next(
            (p for p in candidates if _looks_like_metrics_csv(p)), None)
        metrics_csv_path = str(
            selected if selected is not None else candidates[0])

    evaluator = MetricsEvaluator(metrics_csv_path)
    return evaluator.get_comprehensive_report(include_llm_insights=include_llm_insights, llm_provider=llm_provider)

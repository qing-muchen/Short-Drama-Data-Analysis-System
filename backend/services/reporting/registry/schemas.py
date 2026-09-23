"""Explicit V1 report schema declarations; no discovery or data access."""

from __future__ import annotations

from services.reporting.contracts import (
    ExportDescriptor,
    ExportFormat,
    FilterDefinition,
    ReportColumn,
    ReportColumnType,
    ReportSchema,
    ReportType,
    SnapshotSemantics,
)


CSV_MIME = "text/csv; charset=utf-8"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ALL_FORMATS = (ExportFormat.CSV, ExportFormat.XLSX)


def _column(
    name: str,
    display_name: str,
    data_type: ReportColumnType,
    *,
    nullable: bool = False,
    format: str | None = None,
) -> ReportColumn:
    return ReportColumn(name, display_name, data_type, nullable, format)


def _filter(
    key: str,
    value_type: str,
    *,
    allowed_values: tuple[str, ...] = (),
) -> FilterDefinition:
    return FilterDefinition(
        key=key,
        value_type=value_type,
        allowed_values=allowed_values,
    )


def _descriptors(report_type: ReportType) -> tuple[ExportDescriptor, ...]:
    prefix = report_type.value.lower()
    return (
        ExportDescriptor(
            ExportFormat.CSV,
            CSV_MIME,
            ".csv",
            f"{prefix}_{{analysis_as_of}}_{{schema_version}}.csv",
        ),
        ExportDescriptor(
            ExportFormat.XLSX,
            XLSX_MIME,
            ".xlsx",
            f"{prefix}_{{analysis_as_of}}_{{schema_version}}.xlsx",
        ),
    )


DRAMA_CATALOG_SCHEMA = ReportSchema(
    report_type=ReportType.DRAMA_CATALOG,
    name="Drama Catalog",
    description="Current authorized drama master-data catalog.",
    schema_version="DRAMA_CATALOG Schema V1.0",
    columns=(
        _column("drama_id", "Drama ID", ReportColumnType.INTEGER),
        _column("drama_code", "Drama Code", ReportColumnType.STRING),
        _column("drama_name", "Drama Name", ReportColumnType.STRING),
        _column("status", "Status", ReportColumnType.STRING),
        _column(
            "premiere_date", "Premiere Date", ReportColumnType.DATE, nullable=True
        ),
        _column(
            "episode_count", "Episode Count", ReportColumnType.INTEGER, nullable=True
        ),
        _column(
            "episode_duration_seconds",
            "Episode Duration Seconds",
            ReportColumnType.INTEGER,
            nullable=True,
        ),
        _column("platforms", "Platforms", ReportColumnType.STRING, nullable=True),
        _column("tags", "Tags", ReportColumnType.STRING, nullable=True),
    ),
    filters=(
        _filter("drama_id", "INTEGER"),
        _filter("platform_id", "INTEGER"),
        _filter(
            "status",
            "ENUM",
            allowed_values=("DRAFT", "SERIALIZING", "COMPLETED", "INACTIVE"),
        ),
        _filter("tag_id", "INTEGER"),
    ),
    supported_formats=ALL_FORMATS,
    snapshot_semantics=SnapshotSemantics.CURRENT_STATE_AT_REQUEST,
    sheet_name="Drama Catalog",
    export_descriptors=_descriptors(ReportType.DRAMA_CATALOG),
)


SCORE_RESULTS_SCHEMA = ReportSchema(
    report_type=ReportType.SCORE_RESULTS,
    name="Score Results",
    description="Persisted versioned composite-score results.",
    schema_version="SCORE_RESULTS Schema V1.0",
    columns=(
        _column("score_id", "Score ID", ReportColumnType.INTEGER),
        _column("drama_id", "Drama ID", ReportColumnType.INTEGER),
        _column("score_date", "Score Date", ReportColumnType.DATE),
        _column("score_scope_type", "Scope Type", ReportColumnType.STRING),
        _column("score_scope_id", "Scope ID", ReportColumnType.INTEGER),
        _column("analysis_as_of", "Analysis As Of", ReportColumnType.DATETIME),
        _column("heat_score", "Heat Score", ReportColumnType.DECIMAL),
        _column("growth_score", "Growth Score", ReportColumnType.DECIMAL),
        _column(
            "engagement_score", "Engagement Score", ReportColumnType.DECIMAL
        ),
        _column(
            "lifecycle_score", "Lifecycle Score", ReportColumnType.DECIMAL
        ),
        _column("total_score", "Total Score", ReportColumnType.DECIMAL),
        _column("level", "Level", ReportColumnType.STRING),
        _column("algorithm_version", "Algorithm Version", ReportColumnType.STRING),
    ),
    filters=(
        _filter("algorithm_version", "STRING"),
        _filter("drama_id", "INTEGER"),
        _filter("end_time", "DATETIME"),
        _filter("start_time", "DATETIME"),
    ),
    supported_formats=ALL_FORMATS,
    snapshot_semantics=SnapshotSemantics.AS_OF_RECONSTRUCTED,
    sheet_name="Score Results",
    export_descriptors=_descriptors(ReportType.SCORE_RESULTS),
)


DATA_QUALITY_RESULTS_SCHEMA = ReportSchema(
    report_type=ReportType.DATA_QUALITY_RESULTS,
    name="Data Quality Results",
    description="Persisted versioned Phase 2 data-quality score results.",
    schema_version="DATA_QUALITY_RESULTS Schema V1.0",
    columns=(
        _column("quality_score_id", "Quality Score ID", ReportColumnType.INTEGER),
        _column("score_date", "Score Date", ReportColumnType.DATE),
        _column("score_scope_type", "Scope Type", ReportColumnType.STRING),
        _column("score_scope_id", "Scope ID", ReportColumnType.INTEGER),
        _column("analysis_as_of", "Analysis As Of", ReportColumnType.DATETIME),
        _column(
            "completeness_score", "Completeness Score", ReportColumnType.DECIMAL
        ),
        _column("accuracy_score", "Accuracy Score", ReportColumnType.DECIMAL),
        _column(
            "consistency_score", "Consistency Score", ReportColumnType.DECIMAL
        ),
        _column(
            "timeliness_score", "Timeliness Score", ReportColumnType.DECIMAL
        ),
        _column("total_score", "Total Score", ReportColumnType.DECIMAL),
        _column("quality_grade", "Quality Grade", ReportColumnType.STRING),
        _column(
            "evaluated_entity_count",
            "Evaluated Entity Count",
            ReportColumnType.INTEGER,
        ),
        _column(
            "open_issue_count", "Open Issue Count", ReportColumnType.INTEGER
        ),
        _column("algorithm_version", "Algorithm Version", ReportColumnType.STRING),
        _column("rule_set_version", "Rule Set Version", ReportColumnType.STRING),
        _column("rule_set_hash", "Rule Set Hash", ReportColumnType.STRING),
    ),
    filters=(
        _filter("algorithm_version", "STRING"),
        _filter("end_time", "DATETIME"),
        _filter("rule_set_version", "STRING"),
        _filter("start_time", "DATETIME"),
    ),
    supported_formats=ALL_FORMATS,
    snapshot_semantics=SnapshotSemantics.AS_OF_RECONSTRUCTED,
    sheet_name="Data Quality",
    export_descriptors=_descriptors(ReportType.DATA_QUALITY_RESULTS),
)


PREDICTION_RESULTS_SCHEMA = ReportSchema(
    report_type=ReportType.PREDICTION_RESULTS,
    name="Prediction Results",
    description="Persisted versioned drama prediction results.",
    schema_version="PREDICTION_RESULTS Schema V1.0",
    columns=(
        _column("prediction_id", "Prediction ID", ReportColumnType.INTEGER),
        _column("drama_id", "Drama ID", ReportColumnType.INTEGER),
        _column("metric_type", "Metric Type", ReportColumnType.STRING),
        _column("prediction_date", "Prediction Date", ReportColumnType.DATE),
        _column("target_date", "Target Date", ReportColumnType.DATE),
        _column("predicted_value", "Predicted Value", ReportColumnType.DECIMAL),
        _column("algorithm_version", "Algorithm Version", ReportColumnType.STRING),
        _column("analysis_as_of", "Analysis As Of", ReportColumnType.DATETIME),
    ),
    filters=(
        _filter("algorithm_version", "STRING"),
        _filter("drama_id", "INTEGER"),
        _filter("end_time", "DATETIME"),
        _filter("start_time", "DATETIME"),
    ),
    supported_formats=ALL_FORMATS,
    snapshot_semantics=SnapshotSemantics.AS_OF_RECONSTRUCTED,
    sheet_name="Prediction Results",
    export_descriptors=_descriptors(ReportType.PREDICTION_RESULTS),
)


ANOMALY_RECORDS_SCHEMA = ReportSchema(
    report_type=ReportType.ANOMALY_RECORDS,
    name="Anomaly Records",
    description="Persisted anomaly findings with request-time current status.",
    schema_version="ANOMALY_RECORDS Schema V1.0",
    columns=(
        _column("anomaly_id", "Anomaly ID", ReportColumnType.INTEGER),
        _column("drama_id", "Drama ID", ReportColumnType.INTEGER),
        _column("metric_type", "Metric Type", ReportColumnType.STRING),
        _column("anomaly_type", "Anomaly Type", ReportColumnType.STRING),
        _column("severity", "Severity", ReportColumnType.STRING),
        _column("status", "Current Status", ReportColumnType.STRING),
        _column("analysis_as_of", "Analysis As Of", ReportColumnType.DATETIME),
        _column("detected_at", "Detected At", ReportColumnType.DATETIME),
        _column("algorithm_version", "Algorithm Version", ReportColumnType.STRING),
        _column(
            "baseline_value", "Baseline Value", ReportColumnType.DECIMAL, nullable=True
        ),
        _column(
            "actual_value", "Actual Value", ReportColumnType.DECIMAL, nullable=True
        ),
        _column(
            "deviation_value", "Deviation Value", ReportColumnType.DECIMAL, nullable=True
        ),
        _column("evidence_summary", "Evidence Summary", ReportColumnType.STRING),
    ),
    filters=(
        _filter("algorithm_version", "STRING"),
        _filter("drama_id", "INTEGER"),
        _filter("end_time", "DATETIME"),
        _filter(
            "severity", "ENUM", allowed_values=("A", "B", "C")
        ),
        _filter("start_time", "DATETIME"),
        _filter(
            "status",
            "ENUM",
            allowed_values=("OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED"),
        ),
    ),
    supported_formats=ALL_FORMATS,
    snapshot_semantics=SnapshotSemantics.CURRENT_STATE_AT_REQUEST,
    sheet_name="Anomaly Records",
    export_descriptors=_descriptors(ReportType.ANOMALY_RECORDS),
)


OPERATION_ACTIONS_SCHEMA = ReportSchema(
    report_type=ReportType.OPERATION_ACTIONS,
    name="Operation Actions",
    description="Operation action facts with request-time current state.",
    schema_version="OPERATION_ACTIONS Schema V1.0",
    columns=(
        _column("action_id", "Action ID", ReportColumnType.INTEGER),
        _column("drama_id", "Drama ID", ReportColumnType.INTEGER, nullable=True),
        _column("title", "Title", ReportColumnType.STRING),
        _column("description", "Description", ReportColumnType.STRING, nullable=True),
        _column("priority", "Priority", ReportColumnType.STRING),
        _column("status", "Current Status", ReportColumnType.STRING),
        _column(
            "assignee_user_id", "Assignee User ID", ReportColumnType.INTEGER, nullable=True
        ),
        _column("created_by_user_id", "Created By User ID", ReportColumnType.INTEGER),
        _column("due_date", "Due Date", ReportColumnType.DATE, nullable=True),
        _column("created_at", "Created At", ReportColumnType.DATETIME),
        _column("updated_at", "Updated At", ReportColumnType.DATETIME),
        _column("source_count", "Source Count", ReportColumnType.INTEGER),
        _column("history_count", "History Count", ReportColumnType.INTEGER),
    ),
    filters=(
        _filter("drama_id", "INTEGER"),
        _filter("end_time", "DATETIME"),
        _filter("start_time", "DATETIME"),
        _filter(
            "status",
            "ENUM",
            allowed_values=("OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"),
        ),
    ),
    supported_formats=ALL_FORMATS,
    snapshot_semantics=SnapshotSemantics.CURRENT_STATE_AT_REQUEST,
    sheet_name="Operation Actions",
    export_descriptors=_descriptors(ReportType.OPERATION_ACTIONS),
)


DEFAULT_REPORT_SCHEMAS = (
    DRAMA_CATALOG_SCHEMA,
    SCORE_RESULTS_SCHEMA,
    DATA_QUALITY_RESULTS_SCHEMA,
    PREDICTION_RESULTS_SCHEMA,
    ANOMALY_RECORDS_SCHEMA,
    OPERATION_ACTIONS_SCHEMA,
)


__all__ = (
    "ANOMALY_RECORDS_SCHEMA",
    "DATA_QUALITY_RESULTS_SCHEMA",
    "DEFAULT_REPORT_SCHEMAS",
    "DRAMA_CATALOG_SCHEMA",
    "OPERATION_ACTIONS_SCHEMA",
    "PREDICTION_RESULTS_SCHEMA",
    "SCORE_RESULTS_SCHEMA",
)

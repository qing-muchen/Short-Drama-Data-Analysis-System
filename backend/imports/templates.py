"""V1 fixed import template definitions and upload limits."""

from dataclasses import dataclass

MAX_IMPORT_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_IMPORT_ROWS = 50_000

MASTER_DATA_ENTITY_TYPES = frozenset(
    {"DRAMA", "ACTOR", "DIRECTOR", "COMPANY", "PLATFORM", "TAG"}
)


@dataclass(frozen=True, slots=True)
class ImportTemplate:
    import_type: str
    columns: tuple[str, ...]
    required_columns: frozenset[str]


MASTER_DATA_TEMPLATE = ImportTemplate(
    import_type="MASTER_DATA",
    columns=(
        "entity_type",
        "name",
        "status",
        "drama_code",
        "description",
        "episode_count",
        "episode_duration_seconds",
        "premiere_date",
    ),
    required_columns=frozenset(
        {
            "entity_type",
            "name",
            "status",
            "drama_code",
            "description",
            "episode_count",
            "episode_duration_seconds",
            "premiere_date",
        }
    ),
)

SNAPSHOT_TEMPLATE = ImportTemplate(
    import_type="SNAPSHOT",
    columns=(
        "drama_code",
        "platform_name",
        "snapshot_time",
        "play_count",
        "like_count",
        "comment_count",
        "favorite_count",
        "share_count",
        "ranking",
    ),
    required_columns=frozenset(
        {
            "drama_code",
            "platform_name",
            "snapshot_time",
            "play_count",
            "like_count",
            "comment_count",
            "favorite_count",
            "share_count",
            "ranking",
        }
    ),
)

TEMPLATES = {
    MASTER_DATA_TEMPLATE.import_type: MASTER_DATA_TEMPLATE,
    SNAPSHOT_TEMPLATE.import_type: SNAPSHOT_TEMPLATE,
}


def get_template(import_type: str) -> ImportTemplate:
    try:
        return TEMPLATES[import_type]
    except KeyError as error:
        raise ValueError("Unsupported import type") from error

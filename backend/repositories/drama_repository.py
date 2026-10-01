"""Drama persistence queries."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from models.drama import Drama
from models.master_data import Tag
from models.relations import DramaPlatform, DramaTag
from repositories.base import BaseRepository, Page


class DramaRepository(BaseRepository[Drama]):
    """Database access for drama master records."""

    model = Drama

    def get_by_drama_code(self, drama_code: str) -> Drama | None:
        statement = select(Drama).where(Drama.drama_code == drama_code)
        return self.session.scalar(statement)

    def get_by_id(self, entity_id: int) -> Drama | None:
        statement = (
            select(Drama)
            .where(Drama.drama_id == entity_id)
            .options(*self._relation_options())
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(statement)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        name_contains: str | None = None,
        tag_ids: Sequence[int] = (),
    ) -> Page[Drama]:
        statement = select(Drama).options(*self._relation_options())
        if status is not None:
            statement = statement.where(Drama.status == status)
        if name_contains:
            statement = statement.where(
                Drama.drama_name.contains(name_contains, autoescape=True)
            )
        unique_tag_ids = tuple(dict.fromkeys(tag_ids))
        if unique_tag_ids:
            matching_dramas = (
                select(DramaTag.drama_id)
                .join(Tag, Tag.tag_id == DramaTag.tag_id)
                .where(
                    DramaTag.tag_id.in_(unique_tag_ids),
                    DramaTag.relation_status == "ACTIVE",
                    Tag.status == "ACTIVE",
                )
                .group_by(DramaTag.drama_id)
                .having(func.count(func.distinct(DramaTag.tag_id)) == len(unique_tag_ids))
            )
            statement = statement.where(Drama.drama_id.in_(matching_dramas))
        statement = statement.order_by(Drama.drama_id.asc())
        return self.paginate(statement, page=page, page_size=page_size)

    def replace_tags(self, drama_id: int, tag_ids: Sequence[int]) -> None:
        """Activate exactly the requested relations while preserving relation history."""

        requested = set(tag_ids)
        relations = list(
            self.session.scalars(
                select(DramaTag).where(DramaTag.drama_id == drama_id).with_for_update()
            ).all()
        )
        existing = {relation.tag_id: relation for relation in relations}
        for relation in relations:
            relation.relation_status = (
                "ACTIVE" if relation.tag_id in requested else "INACTIVE"
            )
        self.session.add_all(
            DramaTag(drama_id=drama_id, tag_id=tag_id, relation_status="ACTIVE")
            for tag_id in sorted(requested - existing.keys())
        )
        self.session.flush()

    @staticmethod
    def _relation_options() -> tuple[object, ...]:
        return (
            selectinload(Drama.tag_relations).joinedload(DramaTag.tag),
            selectinload(Drama.platform_relations).joinedload(DramaPlatform.platform),
        )

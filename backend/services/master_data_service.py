"""Actor, director, company, and tag CRUD orchestration."""

from typing import Any, Mapping

from sqlalchemy.orm import Session

from repositories.actor_repository import ActorRepository
from repositories.company_repository import CompanyRepository
from repositories.director_repository import DirectorRepository
from repositories.tag_repository import TagRepository
from services.base import BaseService
from services.exceptions import ConflictException, NotFoundException, ValidationException


class MasterDataService(BaseService):
    """Coordinate master-data persistence and logical deactivation."""

    def __init__(
        self,
        session: Session,
        actors: ActorRepository,
        directors: DirectorRepository,
        companies: CompanyRepository,
        tags: TagRepository,
    ) -> None:
        super().__init__(session, actors, directors, companies, tags)
        self.actors = actors
        self.directors = directors
        self.companies = companies
        self.tags = tags

    def list_actors(self, **filters: Any) -> Any:
        return self.read(self.actors.list_page, **filters)

    def get_actor(self, actor_id: int) -> Any:
        return self._get(self.actors, actor_id, "Actor", "actor_id")

    def create_actor(self, values: Mapping[str, Any]) -> Any:
        return self._create(self.actors, values)

    def update_actor(self, actor_id: int, values: Mapping[str, Any]) -> Any:
        self._reject_null(values, "actor_name", "status")
        return self._update(self.actors, actor_id, values, "Actor", "actor_id")

    def deactivate_actor(self, actor_id: int) -> Any:
        return self.update_actor(actor_id, {"status": "INACTIVE"})

    def list_directors(self, **filters: Any) -> Any:
        return self.read(self.directors.list_page, **filters)

    def get_director(self, director_id: int) -> Any:
        return self._get(self.directors, director_id, "Director", "director_id")

    def create_director(self, values: Mapping[str, Any]) -> Any:
        return self._create(self.directors, values)

    def update_director(self, director_id: int, values: Mapping[str, Any]) -> Any:
        self._reject_null(values, "director_name", "status")
        return self._update(
            self.directors,
            director_id,
            values,
            "Director",
            "director_id",
        )

    def deactivate_director(self, director_id: int) -> Any:
        return self.update_director(director_id, {"status": "INACTIVE"})

    def list_companies(self, **filters: Any) -> Any:
        return self.read(self.companies.list_page, **filters)

    def get_company(self, company_id: int) -> Any:
        return self._get(self.companies, company_id, "Company", "company_id")

    def create_company(self, values: Mapping[str, Any]) -> Any:
        return self._create(self.companies, values)

    def update_company(self, company_id: int, values: Mapping[str, Any]) -> Any:
        self._reject_null(values, "company_name", "status")
        return self._update(
            self.companies,
            company_id,
            values,
            "Company",
            "company_id",
        )

    def deactivate_company(self, company_id: int) -> Any:
        return self.update_company(company_id, {"status": "INACTIVE"})

    def list_tags(self, **filters: Any) -> Any:
        return self.read(self.tags.list_page, **filters)

    def get_tag(self, tag_id: int) -> Any:
        return self._get(self.tags, tag_id, "Tag", "tag_id")

    def create_tag(self, values: Mapping[str, Any]) -> Any:
        tag_name = str(values["tag_name"])
        if self.read(self.tags.get_by_tag_name, tag_name) is not None:
            raise ConflictException("Tag name already exists")
        return self._create(self.tags, values)

    def update_tag(self, tag_id: int, values: Mapping[str, Any]) -> Any:
        self._reject_null(values, "tag_name", "status")
        tag = self.get_tag(tag_id)
        tag_name = values.get("tag_name")
        if tag_name is not None:
            existing = self.read(self.tags.get_by_tag_name, str(tag_name))
            if existing is not None and getattr(existing, "tag_id", None) != tag_id:
                raise ConflictException("Tag name already exists")
        return self._update(self.tags, tag_id, values, "Tag", "tag_id")

    def deactivate_tag(self, tag_id: int) -> Any:
        return self.update_tag(tag_id, {"status": "INACTIVE"})

    def _get(
        self,
        repository: Any,
        entity_id: int,
        entity_name: str,
        id_name: str,
    ) -> Any:
        entity = self.read(repository.get_by_id, entity_id)
        if entity is None:
            raise NotFoundException(
                f"{entity_name} was not found",
                details={id_name: entity_id},
            )
        return entity

    def _create(self, repository: Any, values: Mapping[str, Any]) -> Any:
        with self.transaction():
            return repository.create(values)

    def _update(
        self,
        repository: Any,
        entity_id: int,
        values: Mapping[str, Any],
        entity_name: str,
        id_name: str,
    ) -> Any:
        self._get(repository, entity_id, entity_name, id_name)
        with self.transaction():
            return repository.update(entity_id, values)

    @staticmethod
    def _reject_null(values: Mapping[str, Any], *required: str) -> None:
        invalid = [field for field in required if field in values and values[field] is None]
        if invalid:
            raise ValidationException(
                "Required master-data fields cannot be null",
                details={"fields": invalid},
            )

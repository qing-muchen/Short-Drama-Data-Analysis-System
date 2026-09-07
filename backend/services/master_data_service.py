"""Master-data Service wiring without business operations."""

from sqlalchemy.orm import Session

from repositories.actor_repository import ActorRepository
from repositories.company_repository import CompanyRepository
from repositories.director_repository import DirectorRepository
from repositories.tag_repository import TagRepository
from services.base import BaseService


class MasterDataService(BaseService):
    """Future entry point for actor, director, company, and tag rules."""

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

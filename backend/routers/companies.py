"""Company master-data CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from routers.dependencies import MasterDataServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.master_data import CompanyCreate, CompanyResponse, CompanyUpdate, EntityStatus

router = APIRouter(prefix="/companies", tags=["companies"], responses=ERROR_RESPONSES)


@router.get("", response_model=ResponseModel[PageResponse[CompanyResponse]])
def list_companies(
    service: MasterDataServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[EntityStatus | None, Query(alias="status")] = None,
    name_contains: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> ResponseModel[PageResponse[CompanyResponse]]:
    result = service.list_companies(
        page=page,
        page_size=page_size,
        status=status_filter,
        name_contains=name_contains,
    )
    return page_response(result, CompanyResponse)


@router.get("/{company_id}", response_model=ResponseModel[CompanyResponse])
def get_company(
    service: MasterDataServiceDependency,
    company_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[CompanyResponse]:
    return item_response(service.get_company(company_id), CompanyResponse)


@router.post(
    "",
    response_model=ResponseModel[CompanyResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    payload: CompanyCreate,
    service: MasterDataServiceDependency,
) -> ResponseModel[CompanyResponse]:
    return item_response(
        service.create_company(payload.model_dump(exclude_unset=True)),
        CompanyResponse,
    )


@router.put("/{company_id}", response_model=ResponseModel[CompanyResponse])
def update_company(
    payload: CompanyUpdate,
    service: MasterDataServiceDependency,
    company_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[CompanyResponse]:
    return item_response(
        service.update_company(
            company_id,
            payload.model_dump(exclude_unset=True),
        ),
        CompanyResponse,
    )


@router.delete("/{company_id}", response_model=ResponseModel[CompanyResponse])
def delete_company(
    service: MasterDataServiceDependency,
    company_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[CompanyResponse]:
    return item_response(service.deactivate_company(company_id), CompanyResponse)

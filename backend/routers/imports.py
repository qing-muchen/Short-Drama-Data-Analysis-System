"""Administrator-only two-stage CSV/XLSX import endpoints."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Path, Query, UploadFile, status

from auth.dependencies import AdministratorDependency
from imports.templates import MAX_IMPORT_FILE_SIZE_BYTES
from routers.dependencies import ImportServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response, page_response
from schemas.common import PageResponse, ResponseModel
from schemas.import_job import (
    ImportConfirmRequest,
    ImportErrorResponse,
    ImportJobCreate,
    ImportJobResponse,
    ImportType,
)
from services.exceptions import ValidationException

router = APIRouter(prefix="/import/jobs", tags=["imports"], responses=ERROR_RESPONSES)


@router.post(
    "",
    response_model=ResponseModel[ImportJobResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_import_job(
    administrator: AdministratorDependency,
    service: ImportServiceDependency,
    import_type: Annotated[ImportType, Form()],
    file: Annotated[UploadFile, File()],
) -> ResponseModel[ImportJobResponse]:
    filename = file.filename or ""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    formats = {"csv": "CSV", "xlsx": "XLSX"}
    if suffix not in formats:
        raise ValidationException("Only .csv and .xlsx files are supported")

    chunks: list[bytes] = []
    size = 0
    try:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            chunks.append(chunk)
            if size > MAX_IMPORT_FILE_SIZE_BYTES:
                # Pass the bounded over-limit payload to ImportService so the
                # rejected upload still has an ImportJob and ImportError trail.
                break
    finally:
        await file.close()

    request = ImportJobCreate(
        import_type=import_type,
        original_filename=filename,
        file_format=formats[suffix],
    )
    entity = service.create_import_job(
        request,
        content=b"".join(chunks),
        administrator_id=administrator.user_id,
    )
    return item_response(entity, ImportJobResponse)


@router.get(
    "/{import_job_id}",
    response_model=ResponseModel[ImportJobResponse],
)
def get_import_job(
    administrator: AdministratorDependency,
    service: ImportServiceDependency,
    import_job_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[ImportJobResponse]:
    del administrator
    return item_response(service.get_import_job(import_job_id), ImportJobResponse)


@router.get(
    "/{import_job_id}/errors",
    response_model=ResponseModel[PageResponse[ImportErrorResponse]],
)
def list_import_errors(
    administrator: AdministratorDependency,
    service: ImportServiceDependency,
    import_job_id: Annotated[int, Path(ge=1)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseModel[PageResponse[ImportErrorResponse]]:
    del administrator
    result = service.list_import_errors(
        import_job_id,
        page=page,
        page_size=page_size,
    )
    return page_response(result, ImportErrorResponse)


@router.post(
    "/{import_job_id}/confirm",
    response_model=ResponseModel[ImportJobResponse],
)
def confirm_import(
    payload: ImportConfirmRequest,
    administrator: AdministratorDependency,
    service: ImportServiceDependency,
    import_job_id: Annotated[int, Path(ge=1)],
) -> ResponseModel[ImportJobResponse]:
    del payload
    entity = service.confirm_import(
        import_job_id,
        administrator_id=administrator.user_id,
    )
    return item_response(entity, ImportJobResponse)

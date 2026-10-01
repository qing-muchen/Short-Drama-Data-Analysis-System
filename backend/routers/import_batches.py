"""Administrator-only Batch Import V1 endpoints."""

from typing import Annotated

from fastapi import APIRouter, File, Path, UploadFile, status

from auth.dependencies import AdministratorDependency
from imports.templates import MAX_IMPORT_FILE_SIZE_BYTES
from routers.dependencies import BatchImportServiceDependency
from routers.errors import ERROR_RESPONSES
from routers.responses import item_response
from schemas.common import ResponseModel
from schemas.import_batch import (
    ImportBatchConfirmRequest,
    ImportBatchCreate,
    ImportBatchResponse,
)
from services.batch_import_service import UploadedBatchFile

router = APIRouter(
    prefix="/import/batches",
    tags=["import-batches"],
    responses=ERROR_RESPONSES,
)


@router.post(
    "",
    response_model=ResponseModel[ImportBatchResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_batch(
    payload: ImportBatchCreate,
    administrator: AdministratorDependency,
    service: BatchImportServiceDependency,
) -> ResponseModel[ImportBatchResponse]:
    entity = service.create_batch(payload, administrator_id=administrator.user_id)
    return item_response(entity, ImportBatchResponse)


@router.post(
    "/{import_batch_id}/files",
    response_model=ResponseModel[ImportBatchResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_batch_files(
    import_batch_id: Annotated[int, Path(ge=1)],
    files: Annotated[list[UploadFile], File()],
    administrator: AdministratorDependency,
    service: BatchImportServiceDependency,
) -> ResponseModel[ImportBatchResponse]:
    uploaded: list[UploadedBatchFile] = []
    for file in files:
        chunks: list[bytes] = []
        size = 0
        try:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                chunks.append(chunk)
                if size > MAX_IMPORT_FILE_SIZE_BYTES:
                    break
        finally:
            await file.close()
        uploaded.append(
            UploadedBatchFile(filename=file.filename or "", content=b"".join(chunks))
        )
    entity = service.upload_files(
        import_batch_id,
        uploaded,
        administrator_id=administrator.user_id,
    )
    return item_response(entity, ImportBatchResponse)


@router.post(
    "/{import_batch_id}/validate",
    response_model=ResponseModel[ImportBatchResponse],
)
def validate_batch(
    import_batch_id: Annotated[int, Path(ge=1)],
    administrator: AdministratorDependency,
    service: BatchImportServiceDependency,
) -> ResponseModel[ImportBatchResponse]:
    entity = service.validate_batch(
        import_batch_id, administrator_id=administrator.user_id
    )
    return item_response(entity, ImportBatchResponse)


@router.post(
    "/{import_batch_id}/confirm",
    response_model=ResponseModel[ImportBatchResponse],
)
def confirm_batch(
    import_batch_id: Annotated[int, Path(ge=1)],
    payload: ImportBatchConfirmRequest,
    administrator: AdministratorDependency,
    service: BatchImportServiceDependency,
) -> ResponseModel[ImportBatchResponse]:
    del payload
    entity = service.confirm_batch(
        import_batch_id, administrator_id=administrator.user_id
    )
    return item_response(entity, ImportBatchResponse)


@router.get(
    "/{import_batch_id}",
    response_model=ResponseModel[ImportBatchResponse],
)
def get_batch(
    import_batch_id: Annotated[int, Path(ge=1)],
    administrator: AdministratorDependency,
    service: BatchImportServiceDependency,
) -> ResponseModel[ImportBatchResponse]:
    del administrator
    return item_response(service.get_batch(import_batch_id), ImportBatchResponse)

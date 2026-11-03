import io
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db.database import init_db
from src.ingestion.importer import DatasetImporter
from src.llm.gemini_client import get_generator
from src.models.schemas import (
    ChatResponse,
    CompareRequest,
    DictionarySearchRequest,
    DictionarySearchResult,
    ImportBatchResponse,
    ImportBatchSummary,
    ImportRequest,
    InventoryQueryResponse,
    QueryRequest,
    RoutedQueryContext,
    SnapshotMetricsResponse,
)
from src.query_engine.comparator import compare_snapshots
from src.query_engine.safe_queries import (
    get_audit_summary,
    get_beneficiaries_summary,
    get_import_summary,
    get_inventory_count,
    get_inventory_status,
    get_latest_import_id,
    get_shop_complaints_ranking,
    get_transactions_summary,
)
from src.rag.vector_store import get_retriever
from src.router.query_router import QueryRouter

logger = logging.getLogger(__name__)

# Ensure DB initialized on startup
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Operational AI Assistant for RationRight PDS weekly imports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

importer = DatasetImporter()
router = QueryRouter()
generator = get_generator()


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify service availability."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/api/info", tags=["System"])
def system_info():
    """Return operational metadata and active data paths."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "data_directory": str(settings.DATA_DIR),
        "db_path": str(settings.DB_PATH),
        "chroma_directory": str(settings.CHROMA_DIR),
        "llm_model": settings.GEMINI_MODEL,
        "llm_configured": bool(settings.GEMINI_API_KEY),
    }


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".zip", ".csv", ".json"}


def _normalize_csv_name(filename: str, file_path: Path) -> str:
    """Map uploaded CSV filename to standard RationRight table CSV filename."""
    lower = filename.lower()
    if "shop" in lower or "dealer" in lower:
        return "pwd_shops.csv"
    if "beneficiar" in lower:
        return "beneficiaries.csv"
    if "inventory" in lower or "stock" in lower:
        return "inventory.csv"
    if "transaction" in lower:
        return "transactions.csv"
    if "audit" in lower or "inspection" in lower:
        return "pwd_audits.csv"

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            first_line = f.readline().lower()
            if "ration_card_id" in first_line or "beneficiary_id" in first_line:
                return "beneficiaries.csv"
            if "dealer_id" in first_line or "shop_name" in first_line:
                return "pwd_shops.csv"
            if "opening_stock" in first_line or "closing_stock" in first_line:
                return "inventory.csv"
            if "transaction_id" in first_line or "auth_mode" in first_line:
                return "transactions.csv"
            if "inspection_status" in first_line or "late_opening" in first_line:
                return "pwd_audits.csv"
    except Exception:
        pass
    return filename


@app.post(
    "/api/import",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Ingestion"],
)
def import_dataset(payload: ImportRequest):
    """
    Ingest a weekly dataset batch (either a directory containing CSVs or a .json file).
    Assigns a unique import_id and preserves historical snapshots.
    """
    try:
        response = importer.import_dataset(
            dataset_path=payload.dataset_path,
            dataset_name=payload.dataset_name,
        )
        return response
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@app.post(
    "/api/import/upload",
    response_model=ImportBatchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Ingestion"],
)
async def upload_dataset(
    file: UploadFile = File(..., description="Multipart upload: ZIP archive, CSV, or JSON dataset file"),
    dataset_name: Optional[str] = Form(None, description="Optional custom name for this weekly dataset batch"),
):
    """
    Accept multipart dataset uploads (ZIP archives, single CSVs, or JSON files).
    Performs security validation (file size limits, extension check, zip-slip defense),
    extracts contents safely into a temporary workspace, runs the ingestion pipeline,
    and preserves historical snapshot integrity without exposing arbitrary filesystem paths.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only .zip, .csv, and .json files are accepted.",
        )

    # Read and validate payload size
    with tempfile.TemporaryDirectory() as temp_work_dir:
        work_path = Path(temp_work_dir)
        temp_uploaded_file = work_path / f"upload_{file.filename}"
        total_bytes = 0

        with open(temp_uploaded_file, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Uploaded file exceeds maximum allowed limit of 50MB.",
                    )
                out_f.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        try:
            if ext == ".zip":
                extract_dir = work_path / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)

                if not zipfile.is_zipfile(temp_uploaded_file):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The uploaded file is not a valid ZIP archive or is corrupted.",
                    )

                with zipfile.ZipFile(temp_uploaded_file, "r") as zf:
                    total_uncompressed = 0
                    for info in zf.infolist():
                        member_path = Path(info.filename)
                        if member_path.is_absolute() or ".." in member_path.parts:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Insecure ZIP archive: illegal path traversal in member '{info.filename}'.",
                            )
                        total_uncompressed += info.file_size
                        if total_uncompressed > 100 * 1024 * 1024:
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="Uncompressed ZIP archive contents exceed the 100MB security limit.",
                            )
                    zf.extractall(extract_dir)

                json_files = list(extract_dir.rglob("*.json"))
                csv_files = list(extract_dir.rglob("*.csv"))

                if json_files:
                    import_target = json_files[0]
                elif csv_files:
                    import_target = csv_files[0].parent
                    for f in import_target.glob("*.csv"):
                        norm_name = _normalize_csv_name(f.name, f)
                        if norm_name != f.name:
                            dest = import_target / norm_name
                            if not dest.exists():
                                f.rename(dest)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP archive does not contain any CSV or JSON dataset files.",
                    )

                result = importer.import_dataset(
                    dataset_path=import_target,
                    dataset_name=dataset_name or Path(file.filename).stem,
                )
                return result

            elif ext == ".csv":
                csv_dir = work_path / "csv_import"
                csv_dir.mkdir(parents=True, exist_ok=True)
                norm_name = _normalize_csv_name(file.filename, temp_uploaded_file)
                dest_csv = csv_dir / norm_name
                shutil.copy(temp_uploaded_file, dest_csv)

                result = importer.import_dataset(
                    dataset_path=csv_dir,
                    dataset_name=dataset_name or Path(file.filename).stem,
                )
                return result

            elif ext == ".json":
                result = importer.import_dataset(
                    dataset_path=temp_uploaded_file,
                    dataset_name=dataset_name or Path(file.filename).stem,
                )
                return result

        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Upload import processing error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload import failed: {str(e)}",
            )


@app.get(
    "/api/imports",
    response_model=List[ImportBatchSummary],
    tags=["Ingestion"],
)
def list_imports():
    """Retrieve all historical weekly import snapshots."""
    try:
        return importer.list_imports()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve imports: {str(e)}",
        )


@app.post("/api/compare", tags=["Comparison"])
def compare_weekly_imports(payload: Optional[CompareRequest] = None):
    """
    Compare two historical weekly imports.
    If baseline_import_id or target_import_id are omitted, defaults to comparing
    the previous import with the latest import.
    """
    try:
        imports = importer.list_imports()
        if len(imports) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"At least 2 historical imports required for comparison. Currently found {len(imports)}.",
            )

        target_id = (payload and payload.target_import_id) or imports[0].import_id
        baseline_id = (payload and payload.baseline_import_id) or imports[1].import_id

        diff = compare_snapshots(baseline_id, target_id, db_path=importer.db_path)
        return diff
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}",
        )


@app.get(
    "/api/metrics/{import_id}",
    response_model=SnapshotMetricsResponse,
    tags=["Metrics"],
)
def get_snapshot_metrics(
    import_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max inventory records to return"),
    offset: int = Query(0, ge=0, description="Offset for inventory records pagination"),
):
    """Retrieve structured metrics for a specific historical import batch with pagination."""
    actual_id = import_id
    if import_id == "latest":
        latest = get_latest_import_id(db_path=importer.db_path)
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No imported datasets found.",
            )
        actual_id = latest

    summary = get_import_summary(actual_id, db_path=importer.db_path)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import snapshot not found: {actual_id}",
        )

    total_inv = get_inventory_count(actual_id, db_path=importer.db_path)
    inv_records = get_inventory_status(
        actual_id, limit=limit, offset=offset, db_path=importer.db_path
    )

    return SnapshotMetricsResponse(
        import_id=actual_id,
        dataset_name=summary["dataset_name"],
        import_timestamp=summary["import_timestamp"],
        beneficiaries=get_beneficiaries_summary(actual_id, db_path=importer.db_path),
        inventory=inv_records,
        audits=get_audit_summary(actual_id, db_path=importer.db_path),
        shop_complaints=get_shop_complaints_ranking(actual_id, db_path=importer.db_path),
        transactions=get_transactions_summary(actual_id, db_path=importer.db_path),
        total_inventory_records=total_inv,
        inventory_limit=limit,
        inventory_offset=offset,
    )


@app.get(
    "/api/inventory/{import_id}",
    response_model=InventoryQueryResponse,
    tags=["Inventory"],
)
def get_inventory_records(
    import_id: str,
    commodity: Optional[str] = Query(None, description="Optional commodity filter (Rice or Wheat)"),
    pwd_id: Optional[str] = Query(None, description="Optional Fair Price Shop ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Retrieve paginated inventory stock ledger records with expected closing and variance."""
    actual_id = import_id
    if import_id == "latest":
        latest = get_latest_import_id(db_path=importer.db_path)
        if not latest:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No imported datasets found.")
        actual_id = latest

    summary = get_import_summary(actual_id, db_path=importer.db_path)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import not found: {actual_id}")

    total = get_inventory_count(actual_id, pwd_id=pwd_id, commodity=commodity, db_path=importer.db_path)
    items = get_inventory_status(actual_id, pwd_id=pwd_id, commodity=commodity, limit=limit, offset=offset, db_path=importer.db_path)

    return InventoryQueryResponse(
        import_id=actual_id,
        dataset_name=summary["dataset_name"],
        total=total,
        limit=limit,
        offset=offset,
        inventory=items,
    )


@app.post(
    "/api/dictionary/search",
    response_model=List[DictionarySearchResult],
    tags=["Knowledge Base"],
)
def search_data_dictionary(payload: DictionarySearchRequest):
    """
    Search the RAG knowledge base for field definitions, welfare policies,
    system flags, and schema descriptions using ChromaDB.
    """
    try:
        retriever = get_retriever()
        results = retriever.query(
            query_text=payload.query,
            top_k=payload.top_k,
            category=payload.category,
        )
        return [DictionarySearchResult(**r) for r in results]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG search failed: {str(e)}",
        )


@app.post(
    "/api/route",
    response_model=RoutedQueryContext,
    tags=["Routing"],
)
def route_query(payload: QueryRequest):
    """
    Analyze question, classify intent, and fetch appropriate evidence from SQLite and ChromaDB.
    """
    try:
        return router.route_and_resolve(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Routing failed: {str(e)}",
        )


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["AI Assistant"],
)
@app.post(
    "/api/query",
    response_model=ChatResponse,
    tags=["AI Assistant"],
    include_in_schema=False,
)
def answer_query(payload: QueryRequest):
    """
    Primary endpoint: Answers official questions strictly using imported RationRight
    weekly datasets and data dictionary documentation, enforcing strict data citations
    and neutrality rules.
    """
    try:
        context = router.route_and_resolve(payload)
        response = generator.generate_response(context)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {str(e)}",
        )

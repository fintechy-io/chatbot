import os
from unstructured_client import UnstructuredClient
from unstructured_client.models import operations, shared
from config import settings

# Comprehensive mapping for all supported file types
MIME_TYPE_MAP = {
    # Images
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".webp": "image/webp",
    # Documents
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    # Spreadsheets
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    # Text
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "text/xml",
    ".json": "application/json",
    ".rtf": "application/rtf",
    ".eml": "message/rfc822",
    ".msg": "application/vnd.ms-outlook",
}


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text and layout from ANY supported document using the Unstructured API.
    Supports images, PDFs, Word, Excel, CSV, PowerPoint, text files, and more.
    """
    if not settings.UNSTRUCTURED_API_KEY:
        raise ValueError("UNSTRUCTURED_API_KEY is not set.")
    if not settings.UNSTRUCTURED_API_URL:
        raise ValueError("UNSTRUCTURED_API_URL is not set.")

    ext = os.path.splitext(file_path)[1].lower()
    content_type = MIME_TYPE_MAP.get(ext, "application/octet-stream")

    client = UnstructuredClient(
        api_key_auth=settings.UNSTRUCTURED_API_KEY,
        server_url=settings.UNSTRUCTURED_API_URL
    )

    with open(file_path, "rb") as f:
        file_content = f.read()

    req = operations.PartitionRequest(
        partition_parameters=shared.PartitionParameters(
            files=shared.Files(
                content=file_content,
                file_name=os.path.basename(file_path),
            ),
            strategy=shared.Strategy.HI_RES,
        ),
    )

    try:
        res = client.general.partition(request=req)
        elements = res.elements
        
        extracted_parts = []
        for el in elements:
            # For tabular data (Excel, CSV, Word tables), Unstructured often returns HTML.
            # Preserving the HTML grid ensures the LLM sees rows/columns intact.
            metadata = el.get("metadata", {})
            html = metadata.get("text_as_html") if isinstance(metadata, dict) else None
            
            if html:
                extracted_parts.append(str(html))
            elif el.get("text"):
                extracted_parts.append(str(el.get("text")))
                
        extracted_text = "\n\n".join(extracted_parts)
        return extracted_text
    except Exception as e:
        raise RuntimeError(f"Unstructured API failed for {os.path.basename(file_path)}: {e}")

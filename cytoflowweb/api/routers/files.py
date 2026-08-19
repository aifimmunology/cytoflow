"""
cytoflowweb.api.routers.files
------------------------------

Endpoints for uploading FCS files.

Files are stored server-side in a per-session upload directory.
The browser never receives raw FCS data — only metadata (channel names,
event count, detected conditions).
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from cytoflowweb.api.models import session_manager
from cytoflowweb import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/files", tags=["files"])

_UPLOAD_ROOT = config.UPLOAD_ROOT


# ── Response models ───────────────────────────────────────────────────────────

class FCSMetadata(BaseModel):
    file_id: str
    original_name: str
    server_path: str
    channels: list[str]
    event_count: int
    text_metadata: dict[str, Any]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_upload_dir(session_id: str) -> Path:
    d = _UPLOAD_ROOT / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_fcs_metadata(path: str) -> dict[str, Any]:
    """Extract channel names, event count, and text segment from an FCS file."""
    from fcsparser import fcsparser as fp
    meta, _ = fp.parse(path, reformat_meta=True, data_set=0)
    channels = [meta["_channel_names_"][i] for i in range(int(meta.get("$PAR", 0)))]
    event_count = int(meta.get("$TOT", 0))
    # Return a subset of text metadata relevant for UI display
    text_keys = {k: v for k, v in meta.items() if not k.startswith("_")}
    return {"channels": channels, "event_count": event_count, "text_metadata": text_keys}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=FCSMetadata, status_code=201)
async def upload_fcs(session_id: str, file: UploadFile) -> FCSMetadata:
    """Upload an FCS file.

    The file is saved on the server and its metadata (channels, event count)
    is returned.  The returned ``server_path`` can be used when constructing
    an ``ImportOp`` ``Tube``.
    """
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not file.filename:
        raise HTTPException(status_code=422, detail="Missing filename")

    # Give the file a stable UUID-based name to avoid collisions
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix or ".fcs"
    dest = _session_upload_dir(session_id) / f"{file_id}{suffix}"

    contents = await file.read()
    dest.write_bytes(contents)

    try:
        meta = _parse_fcs_metadata(str(dest))
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not parse FCS file: {exc}")

    return FCSMetadata(
        file_id=file_id,
        original_name=file.filename,
        server_path=str(dest),
        channels=meta["channels"],
        event_count=meta["event_count"],
        text_metadata=meta["text_metadata"],
    )


@router.get("", response_model=list[dict])
def list_files(session_id: str) -> list[dict]:
    """List all uploaded FCS files for this session."""
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    upload_dir = _session_upload_dir(session_id)
    files = []
    for p in sorted(upload_dir.iterdir()):
        files.append({"file_id": p.stem, "filename": p.name, "server_path": str(p)})
    return files

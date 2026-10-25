"""Resolve Whisper model files: use the local cache first, download only when missing.

faster-whisper otherwise asks the Hugging Face Hub for updates on every load,
which can take minutes on a slow or rate-limited connection.
"""

from __future__ import annotations


def is_cached(name_or_repo: str, mlx: bool = False) -> bool:
    try:
        if mlx:
            from huggingface_hub import snapshot_download

            snapshot_download(name_or_repo, local_files_only=True)
        else:
            from faster_whisper.utils import download_model

            download_model(name_or_repo, local_files_only=True)
        return True
    except Exception:
        return False


def faster_whisper_model_path(name: str) -> str:
    from faster_whisper.utils import download_model

    try:
        return download_model(name, local_files_only=True)
    except Exception:  # not cached yet
        return download_model(name)


def mlx_model_path(repo: str) -> str:
    from huggingface_hub import snapshot_download

    try:
        return snapshot_download(repo, local_files_only=True)
    except Exception:
        return snapshot_download(repo)

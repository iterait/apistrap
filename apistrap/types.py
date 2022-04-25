from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Union
from typing.io import BinaryIO

if TYPE_CHECKING:  # pragma: no cover
    try:
        from aiohttp import StreamReader
    except ImportError:

        class StreamReader:
            pass


class FileResponse:
    """
    File response used instead of `flask.send_file`.
    Note that MIME type should preferably be handled by `responds_with` decorator.
    """

    def __init__(
        self,
        filename_or_fp: Union[str, BinaryIO, BytesIO, StreamReader],
        as_attachment: bool = False,
        attachment_filename: str = None,
        add_etags: bool = True,
        cache_timeout: int = None,
        conditional: bool = False,
        last_modified: Union[datetime, int] = None,
        mimetype=None,
    ):
        self.filename_or_fp = filename_or_fp
        self.as_attachment = as_attachment
        self.attachment_filename = attachment_filename
        self.add_etags = add_etags
        self.cache_timeout = cache_timeout
        self.conditional = conditional
        self.last_modified = last_modified
        self.mimetype = mimetype

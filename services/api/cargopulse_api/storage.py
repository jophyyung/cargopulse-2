"""Private immutable object storage; objects are never served by public path."""

import hashlib
import os
import re
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from botocore.parsers import ResponseParserError

from .storage_xml import StrictResponseParserFactory, register_s3_xml_guard


class PrivateObjects:
    def __init__(self, settings):
        self.root = Path(settings.object_root)
        self.bucket = settings.object_bucket
        self.endpoint = settings.object_endpoint
        self.s3 = None
        if self.bucket:
            import boto3
            import botocore.session
            from botocore.config import Config

            session = botocore.session.get_session()
            session.register_component("response_parser_factory", StrictResponseParserFactory())
            register_s3_xml_guard(session)
            self.s3 = boto3.Session(botocore_session=session).client(
                "s3",
                endpoint_url=self.endpoint or None,
                config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
            )
        else:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def put(self, tenant, raw):
        if not re.fullmatch(r"[a-f0-9-]{36}", tenant):
            raise ValueError("Invalid tenant prefix")
        digest = hashlib.sha256(raw).hexdigest()
        key = f"{tenant}/imports/{digest}"
        if self.s3:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=raw,
                ServerSideEncryption="AES256",
                ContentType="application/octet-stream",
            )
        else:
            directory = self.root / tenant / "imports"
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(directory / digest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return key
            with os.fdopen(fd, "wb") as out:
                out.write(raw)
        return key

    def probe(self):
        if self.s3:
            self.s3.head_bucket(Bucket=self.bucket)
            return "ok"
        return (
            "ok"
            if self.root.is_dir() and os.access(self.root, os.R_OK | os.W_OK)
            else "unavailable"
        )

    def verify(self, tenant, key):
        """Verify the exact private object digest, including bounded S3 reads."""
        prefix = f"{tenant}/imports/"
        if not key.startswith(prefix) or not re.fullmatch(r"[a-f0-9]{64}", key[len(prefix) :]):
            return False
        expected = key[len(prefix) :]
        source = None
        try:
            if self.s3:
                try:
                    response = self.s3.get_object(Bucket=self.bucket, Key=key)
                except (BotoCoreError, ClientError):
                    return False
                if response.get("ContentLength", 8_000_001) > 8_000_000:
                    response["Body"].close()
                    return False
                source = response["Body"]
            else:
                fd = os.open(self.root / key, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                source = os.fdopen(fd, "rb")
            digest = hashlib.sha256()
            size = 0
            while chunk := source.read(65536):
                size += len(chunk)
                if size > 8_000_000:
                    return False
                digest.update(chunk)
            return digest.hexdigest() == expected
        except (OSError, BotoCoreError, ClientError, ResponseParserError):
            return False
        finally:
            if source is not None:
                source.close()

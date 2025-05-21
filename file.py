import patronobuf as pb
from common import write_delimited, read_delimited
import os
import logging

logger = logging.getLogger("patron_client")

def handle_file_request(conn, agent_id):
    req = pb.Request(
        type=pb.FILE,
        file=pb.FileRequest(uuid=agent_id)
    )

    try:
        write_delimited(conn, req)
        logger.debug("Sent file request")
        resp = read_delimited(conn, pb.Response)

        if resp.type != pb.FILE_RESPONSE or not resp.HasField("file_response"):
            logger.warning("Unexpected or missing file_response")
            return None

        return resp.file_response
    except Exception as e:
        logger.error(f"Failed to handle file request: {e}")
        return None

def download_file(file_response):
    path = file_response.filepath
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, "wb") as f:
            f.write(file_response.chunk)
        logger.info(f"Downloaded file to {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write file {path}: {e}")
        return False

def upload_file(conn, file_response):
    try:
        with open(file_response.filepath, "rb") as f:
            chunk = f.read()

        upload = pb.FileToServer(
            fileid=file_response.fileid,
            uuid=file_response.uuid,
            transfertype=file_response.transfertype,
            path=file_response.filepath,
            status="Success",
            chunk=chunk
        )

        req = pb.Request(type=pb.FILE_TO_SERVER, file_to_server=upload)
        write_delimited(conn, req)

        ack = read_delimited(conn, pb.Response)
        logger.debug(f"Received file upload ack: {ack}")
        return ack
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        return None

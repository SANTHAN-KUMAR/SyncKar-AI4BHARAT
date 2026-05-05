import base64
import os
from pathlib import Path
from typing import Dict, Any

from synckar.config import settings


def _ensure_ca_file_if_configured() -> None:
    """
    Ensure the Kafka CA certificate exists on disk if configured via env.

    Railway commonly provides secrets via environment variables; this function
    supports either raw PEM (`KAFKA_SSL_CA_PEM`) or base64 (`KAFKA_SSL_CA_PEM_BASE64`)
    and writes it to `KAFKA_SSL_CA_PATH` (defaulting to /tmp if unset).
    """
    pem = settings.kafka.ssl_ca_pem
    pem_b64 = settings.kafka.ssl_ca_pem_base64
    if not pem and not pem_b64:
        return

    target = settings.kafka.ssl_ca_path or os.environ.get("KAFKA_SSL_CA_PATH") or "/tmp/kafka-ca.pem"
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and target_path.stat().st_size > 0:
        # Already present; don't overwrite.
        return

    if pem_b64:
        decoded = base64.b64decode(pem_b64).decode("utf-8")
        contents = decoded
    else:
        contents = pem or ""

    # Basic sanity: must look like a PEM cert.
    if "BEGIN CERTIFICATE" not in contents:
        raise ValueError("Kafka CA PEM content missing 'BEGIN CERTIFICATE' header")

    target_path.write_text(contents, encoding="utf-8")

    # Ensure the path is used even if caller only set the PEM env var.
    settings.kafka.ssl_ca_path = str(target_path)


def build_kafka_conf() -> Dict[str, Any]:
    _ensure_ca_file_if_configured()

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS") or settings.kafka.bootstrap_servers
    conf: Dict[str, Any] = {"bootstrap.servers": bootstrap_servers}

    if settings.kafka.security_protocol and settings.kafka.security_protocol != "PLAINTEXT":
        conf["security.protocol"] = settings.kafka.security_protocol

    if settings.kafka.sasl_mechanism:
        conf["sasl.mechanism"] = settings.kafka.sasl_mechanism
        if settings.kafka.sasl_username:
            conf["sasl.username"] = settings.kafka.sasl_username
        if settings.kafka.sasl_password:
            conf["sasl.password"] = settings.kafka.sasl_password

    if settings.kafka.ssl_ca_path:
        conf["ssl.ca.location"] = settings.kafka.ssl_ca_path

    return conf


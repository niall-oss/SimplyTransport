# pyright: reportPrivateImportUsage=false
from __future__ import annotations

import logging

import opentelemetry._logs as otel_logs
from litestar.plugins.opentelemetry import OpenTelemetryConfig, OpenTelemetryPlugin
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from . import settings

otel_log_handler: logging.Handler | None = None
_configured = False

open_telemetry_config = OpenTelemetryConfig()
open_telemetry_plugin = OpenTelemetryPlugin(config=open_telemetry_config)


def _otlp_base_url() -> str:
    return settings.app.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")


def configure_opentelemetry() -> None:
    """Enable OTel exporters in local dev and production. Safe to call more than once."""
    global _configured, otel_log_handler
    if _configured:
        return
    _configured = True

    # Tests set ENVIRONMENT=TEST and should not export to a collector
    if settings.app.ENVIRONMENT not in ("DEV", "PROD"):
        return

    _base = _otlp_base_url()
    resource = Resource(
        attributes={
            SERVICE_NAME: settings.app.NAME,
            SERVICE_VERSION: settings.app.VERSION,
            "service.debug": settings.app.DEBUG,
            "service.log_level": settings.app.LOG_LEVEL,
            DEPLOYMENT_ENVIRONMENT: settings.app.ENVIRONMENT,
        }
    )

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{_base}/v1/traces")))
    trace.set_tracer_provider(trace_provider)
    HTTPXClientInstrumentor().instrument()

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{_base}/v1/metrics"))
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    _log_provider = LoggerProvider(resource=resource)
    _log_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{_base}/v1/logs"))
    )
    otel_logs.set_logger_provider(_log_provider)
    otel_log_handler = LoggingHandler(level=logging.NOTSET, logger_provider=_log_provider)

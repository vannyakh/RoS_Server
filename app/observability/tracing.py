"""OpenTelemetry tracer. Spans stay in memory unless a collector is configured later."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

EXPORTED_SPANS: list = []
_READY = False


class MemorySpanExporter(SpanExporter):
    def export(self, spans) -> SpanExportResult:
        EXPORTED_SPANS.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def setup_tracing() -> trace.Tracer:
    global _READY
    if not _READY:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(MemorySpanExporter()))
        trace.set_tracer_provider(provider)
        _READY = True
    return trace.get_tracer("ros.server")


tracer = setup_tracing()

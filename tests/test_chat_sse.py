from src.api.routes.chat import _format_sse_comment, _format_sse_event
from src.api.schemas.chat import StreamEvent, StreamEventType


def test_format_sse_event_uses_standard_framing():
    event = StreamEvent(
        type=StreamEventType.PROGRESS,
        data={"node": "researcher_tools"},
    )

    assert (
        _format_sse_event(event)
        == 'event: progress\ndata: {"node": "researcher_tools"}\n\n'
    )


def test_format_sse_comment_uses_comment_frame():
    assert _format_sse_comment() == ":\n\n"
    assert _format_sse_comment("open") == ": open\n\n"

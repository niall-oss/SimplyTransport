from SimplyTransport.domain.events.event_types import ALL_EVENTS, EventType, event_type_label


def test_event_type_label_covers_all_enum_values() -> None:
    assert event_type_label(ALL_EVENTS) == "All event types"
    for event_type in EventType:
        assert event_type_label(event_type.value) != event_type.value

# Events

## Create a new event

```python
from SimplyTransport.domain.events.event_repo import EventRepo, provide_event_repo

event_repo: EventRepo = provide_event_repo()

await event_repo.create_event(event_type=EventType.Test, description="Test", attributes={"test": "test"})
```

## Event types

There is a string enum that defines the different types of events that can be created.

## Event attributes

Event attributes are a dictionary of key-value pairs that can be used to store additional information about the event.

## Event Expiry

Events can be set to expire after a certain amount of time. This is useful for events that are only relevant for a certain amount of time. After this time, the event may be deleted from the database.

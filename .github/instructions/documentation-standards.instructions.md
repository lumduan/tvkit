---
applyTo: '**'
---
### 📝 DOCUMENTATION STANDARDS - MANDATORY

1. **Docstring Requirements**:

   - ALL public functions MUST have comprehensive docstrings
   - Include parameter descriptions with types
   - Include return value descriptions
   - Include usage examples for complex functions
   - Include exception documentation

2. **Example Format**:

```python
async def multicast_message(
    self,
    user_ids: list[str],
    messages: list[Any],
    notification_disabled: Optional[bool] = None,
) -> bool:
    """
    Send multicast message to multiple users.

    Efficiently sends the same message to multiple user IDs. Cannot send
    messages to group chats or multi-person chats.

    Args:
        user_ids: List of user IDs (max 500)
        messages: List of message objects (max 5)
        notification_disabled: Whether to disable push notifications

    Returns:
        True if successful

    Raises:
        LineMessageError: If message sending fails
        LineRateLimitError: If rate limit exceeded

    Example:
        >>> async with LineMessagingClient(config) as client:
        ...     success = await client.multicast_message(
        ...         user_ids=["user1", "user2"],
        ...         messages=[TextMessage.create("Hello!")],
        ...     )
    """
```
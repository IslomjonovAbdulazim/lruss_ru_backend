# Video URL API

## Endpoint: Get Grammar Topic Video

**URL:** `GET /topics/{topic_id}/video`

**Description:** Retrieves the video URL for a specific grammar topic. Requires an active premium subscription.

### Parameters

#### Path Parameters
- `topic_id` (integer, required): The ID of the grammar topic

#### Query Parameters
- `telegram_id` (integer, required): The Telegram ID of the user requesting the video

### Request Example

```http
GET /topics/1/video?telegram_id=123456789
```

### Response Examples

#### Success Response (200 OK)
User has active premium subscription and video exists:

```json
{
  "video_url": "https://t.me/c/2997699332/2"
}
```

#### Error Responses

##### 403 Forbidden - No Premium Subscription
```json
{
  "detail": "Premium subscription required to access video content"
}
```

##### 404 Not Found - User Not Found
```json
{
  "detail": "User not found"
}
```

##### 404 Not Found - Grammar Topic Not Found
```json
{
  "detail": "Grammar topic not found or no video URL available"
}
```

### Use Cases

1. **Premium User Access**: A user with an active premium subscription can access grammar topic videos
2. **Free User Restriction**: Users without premium subscription are denied access
3. **Content Protection**: Video URLs are only provided to verified premium users

### Authentication

This endpoint does not require traditional authentication tokens. Instead, it uses the `telegram_id` parameter to identify and verify the user's subscription status.

### Business Logic

1. User lookup by `telegram_id`
2. Premium subscription verification (active and not expired)
3. Grammar topic existence check
4. Video URL retrieval and return

### Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success - Video URL returned
- `403`: Forbidden - Premium subscription required
- `404`: Not Found - User, topic, or video not found
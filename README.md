# Educational Platform Backend

A fast, minimal API backend for an educational platform with Telegram bot authentication.

## Features

- 🤖 **Telegram Bot Authentication**: Users share phone number via Telegram bot
- 🔐 **JWT Authentication**: 7-day access tokens, 30-day refresh tokens
- 👤 **User Profiles**: Manage names and avatars from Telegram
- 🚀 **Fast & Minimal**: Designed for minimal API requests
- 🗃️ **PostgreSQL**: Async database operations
- 📱 **Mobile-Optimized**: Long-lived tokens for mobile apps

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python run.py
```

3. API will be available at `http://localhost:8000`
4. API documentation at `http://localhost:8000/docs`

## Authentication Flow

1. User starts bot with `/start` command
2. Bot requests phone number
3. User shares phone number
4. Bot generates 4-digit code (5-min expiration)
5. User enters phone + code in app
6. App receives JWT tokens

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with phone + code
- `POST /api/auth/refresh` - Refresh tokens

### Profile
- `GET /api/profile/me` - Get user profile
- `PUT /api/profile/me` - Update profile (first_name, last_name)
- `POST /api/profile/refresh-avatar` - Refresh avatar from Telegram

## Environment Variables

See `.env` file for configuration.

## Database Models

- **User**: id, telegram_id, phone_number, first_name, last_name, avatar_url
- **TempCode**: phone_number, code (4-digit), created_at (5-min TTL)

## Security Features

- Name sanitization (English/Russian only)
- Phone number validation
- Code expiration (5 minutes)
- JWT token validation
- Immutable phone numbers
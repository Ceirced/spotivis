# Flask Web App with HTMX

## Project Overview

This project is a Flask web application designed to be used as a template for building web applications with HTMX. It focuses on server-side rendering, minimal JavaScript, and a clean, responsive UI using TailwindCSS.

## Tech Stack

### Backend

- **Framework**: Flask 3.x with Flask-Security for authentication
- **Task Queue**: Celery with Redis
- **File Processing**: PyArrow for .parquet file handling
- **Python Version**: ^3.12

### Frontend

- **Approach**: Server-side rendering with HTMX (NO JavaScript business logic)
- **CSS Framework**: TailwindCSS v4 with DaisyUI components
- **Build Tool**: NPM scripts for Tailwind compilation

## Project Structure

```
spotivis/
├── app/
│   ├── main/
│   │   ├── first/        # Primary features
│   │   ├── second_page/  # Secondary features
│   │   └── users/        # User profiles and settings
│   ├── templates/        # Jinja2 templates with HTMX
│   ├── static/          # CSS, images, etc.
│   ├── models.py        # SQLAlchemy models
│   └── extensions/      # Flask extensions setup
├── tests/              # Pytest test suite
├── migrations/         # Database migrations (Flask-Migrate)
├── config.py           # App configuration
└── flask_app.py        # Application entry point
```

## Key Features

### Current Implementation

1. **User Authentication**: Flask-Security with email/password
2. **Responsive UI**: Mobile-first design with bottom navigation
3. **Theme Support**: Light/dark theme switcher

## Development Guidelines

### Code Style

- **Python**: Use Black formatter, Ruff linter, MyPy for type checking
- **HTML**: Use Prettier with Jinja template plugin
- **Templates**: Follow existing partials pattern for HTMX responses

### Testing

- Run tests: `pytest`
- Test structure follows app structure
- Focus on integration tests for HTMX endpoints

### Commands

```bash
# Development Setup
make local                       # Start only Redis and Celery in Docker
flask run                        # Run Flask app locally (after make local)

# Alternative Development (all in Docker)
make dev                         # Run everything in Docker containers
make stop                        # Stop all containers
make clean                       # Stop containers and remove volumes

# Production
make prod                        # Run in production mode

# Backend
ruff check .                     # Lint Python code
black .                          # Format Python code
mypy .                           # Type check

# Frontend
npm run dev                      # Watch and compile Tailwind CSS
npm run prod                     # Build minified CSS for production


# Database
flask db migrate -m "message"    # Create new migration
flask db upgrade                 # Apply migrations
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required
SECRET_KEY=your-secret-key                    # Generate a secure random key
SECURITY_PASSWORD_SALT=your-salt-here         # Generate a random salt for password hashing
SQLALCHEMY_DATABASE_URI=sqlite:///dev.db      # Database connection string
APP_SETTINGS=config.DevelopmentConfig         # Configuration class to use
APP_NAME=Flask App                            # Application name

# Mail Configuration (Required for email features)
MAIL_SERVER=smtp.example.com                  # SMTP server address
MAIL_PORT=587                                 # SMTP port
MAIL_USERNAME=your-email@example.com          # Email username
MAIL_PASSWORD=your-password                   # Email password

# Redis Configuration
REDIS_URL=redis://localhost:6379              # Redis connection URL

# Optional
HOST_NAME=localhost:5000                      # Server name for production
MAINTENANCE_MODE=False                         # Enable maintenance mode
LOG_TO_STDOUT=False                           # Log to stdout instead of file
STRIPE_SECRET_KEY=                           # Stripe API key for payments
STRIPE_WEBHOOK_SECRET=                        # Stripe webhook secret
POSTHOG_API_KEY=                             # PostHog analytics key
```

## HTMX Patterns

1. **Boosted Navigation**: Main layout uses hx-boost for SPA-like navigation but not the body is swapped but the innerHTML of the #content div.
2. **Partial Updates**: Forms return partial HTML templates
3. **Error Handling**: Return appropriate HTTP status codes with error partials

## Security Considerations

- Flask-Security handles authentication and authorization
- CSRF protection enabled via Flask-WTF
- Secure session cookies in production

## Important Notes

- prefer HTMX over JavaScript for business logic
- Follow existing template structure for consistency
- Use server-side rendering for all UI updates

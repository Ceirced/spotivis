# Flask Web App with HTMX

A modern Flask web application template designed for building web applications with HTMX. It focuses on server-side rendering, minimal JavaScript, and a clean, responsive UI using TailwindCSS.

## Tech Stack

### Backend

- **Framework**: Flask 3.x with Flask-Security for authentication
- **Task Queue**: Celery with Redis
- **Database**: SQLAlchemy with Flask-Migrate
- **Python Version**: ^3.12

### Frontend

- **Approach**: Server-side rendering with HTMX (NO JavaScript business logic)
- **CSS Framework**: TailwindCSS v4 with DaisyUI components
- **Build Tool**: NPM scripts for Tailwind compilation

## Setup Instructions

### Prerequisites

- Python 3.12+
- Node.js and npm
- Docker and Docker Compose
- Poetry (for Python dependency management)

### Initial Setup

1. **Clone the repository and install dependencies:**

    ```bash
    npm install          # Install Tailwind CSS dependencies
    poetry install       # Install Python dependencies
    ```

2. **Configure environment variables:**

    ```bash
    cp .env.example .env
    # Edit .env and fill in your configuration
    ```

3. **Required environment variables:**

    - `SECRET_KEY` - Generate a secure random key
    - `SECURITY_PASSWORD_SALT` - Generate a random salt for password hashing (REQUIRED - app will fail without it)
    - `SQLALCHEMY_DATABASE_URI` - Database connection string
    - `APP_SETTINGS` - Configuration class (e.g., `config.DevelopmentConfig`)
    - See `.env.example` for all available options

4. **Set up the database:**
    ```bash
    flask db upgrade
    ```

## Running the Application

### Development Mode

**Option 1: Local development (recommended)**

```bash
make local      # Start only Redis and Celery in Docker
flask run       # Run Flask app locally
npm run dev     # In another terminal, watch and compile Tailwind CSS
```

**Option 2: Full Docker development**

```bash
make dev        # Run everything in Docker containers
```

### Production Mode

```bash
make prod       # Run in production mode with Docker
```

### Stop Services

```bash
make stop       # Stop all containers
make clean      # Stop containers and remove volumes
```

## Project Structure

```
app/
├── main/
│   ├── first/        # Primary features
│   ├── second_page/  # Secondary features
│   └── users/        # User profiles and settings
├── templates/        # Jinja2 templates with HTMX
├── static/          # CSS, images, etc.
├── models.py        # SQLAlchemy models
└── extensions/      # Flask extensions setup
tests/              # Pytest test suite
migrations/         # Database migrations (Flask-Migrate)
config.py           # App configuration
flask_app.py        # Application entry point
```

## Development Commands

### Backend

```bash
ruff check .                     # Lint Python code
black .                          # Format Python code
mypy .                           # Type check

# Database
flask db migrate -m "message"    # Create new migration
flask db upgrade                 # Apply migrations

# Testing
pytest                           # Run test suite
```

### Frontend

```bash
npm run dev                      # Watch and compile Tailwind CSS
npm run prod                     # Build minified CSS for production
```

## Docker Configuration

Before running in Docker:

- [ ] Rename the project in `docker-compose.yml` at the `name` property
- [ ] Configure PostHog analytics key or remove from compose
- [ ] Configure Stripe payment key or remove from compose
- [ ] Review nginx configuration if using reverse proxy

## Environment Variables

Copy `.env.example` to `.env` and configure. Key variables include:

- **Flask & Security**: `SECRET_KEY`, `SECURITY_PASSWORD_SALT` (required)
- **Database**: `SQLALCHEMY_DATABASE_URI`
- **Mail**: SMTP configuration for email features
- **Optional**: Stripe, PostHog, maintenance mode settings

See `.env.example` for complete list with descriptions.

## Security Considerations

- Flask-Security handles authentication and authorization
- CSRF protection enabled via Flask-WTF
- Secure session cookies in production
- Password salt must be configured (app will fail without it)

## HTMX Patterns

The application uses HTMX for dynamic updates:

- **Boosted Navigation**: SPA-like navigation with `hx-boost`
- **Partial Updates**: Forms return partial HTML templates
- **Error Handling**: Appropriate HTTP status codes with error partials

## Contributing

1. Follow existing code conventions
2. Use Ruff
3. Write tests for new features
4. Update documentation as needed

## License

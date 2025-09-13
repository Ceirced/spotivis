# SpotiVis - Spotify Streaming Data Visualization

## Project Overview

SpotiVis is a web application that visualizes Spotify streaming data from .parquet files. Users can upload their Spotify data exports and view the connections between playlists in an interactive graph format using D3.js.

## Tech Stack

### Backend

- **Framework**: Flask 3.x with Flask-Security for authentication
- **Task Queue**: Celery with Redis
- **File Processing**: PyArrow for .parquet file handling
- **Python Version**: ^3.12

### Frontend

- **Approach**: Server-side rendering with HTMX (NO JavaScript business logic)
- **CSS Framework**: TailwindCSS v4 with DaisyUI components
- **Visualization**: D3.js (only for graph visualization)
- **Build Tool**: NPM scripts for Tailwind compilation

## Project Structure

```
spotivis/
├── app/
│   ├── main/
│   │   ├── first/        # File upload functionality
│   │   ├── second_page/  # Secondary features
│   │   └── users/        # User profiles and settings
│   ├── templates/        # Jinja2 templates with HTMX
│   ├── static/          # CSS, images, etc.
│   ├── models.py        # SQLAlchemy models
│   └── extensions/      # Flask extensions setup
├── uploads/             # User uploaded .parquet files
├── tests/              # Pytest test suite
├── migrations/         # Database migrations (Flask-Migrate)
├── config.py           # App configuration
└── flask_app.py        # Application entry point
```

## Key Features

### Current Implementation

1. **User Authentication**: Flask-Security with email/password
2. **File Upload**:
    - Accepts .parquet files up to 500MB
    - Validates parquet format using PyArrow
    - Stores files with timestamp prefixes
    - Lists uploaded files with metadata
3. **Responsive UI**: Mobile-first design with bottom navigation
4. **Theme Support**: Light/dark theme switcher

### Planned Features

1. **Data Visualization**: D3.js graph showing playlist connections
2. **Data Processing**: Parse Spotify streaming data from parquet files
3. **Analytics**: Streaming statistics and insights

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

# Testing
pytest                          # Run all tests
pytest tests/test_file_upload.py  # Run specific test file

# Database
flask db migrate -m "message"    # Create new migration
flask db upgrade                 # Apply migrations
```

## Environment Variables

```bash
# Required
SECRET_KEY=your-secret-key
SQLALCHEMY_DATABASE_URI=sqlite:///dev.db  # or MySQL URI

# Optional
HOST_NAME=localhost:5000
REDIS_URL=redis://localhost
IN_CONTAINER=1  # Set when running in Docker
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

# SpotiVis - Spotify Streaming Data Visualization

SpotiVis is a web application that visualizes Spotify streaming data from .parquet files. Users can upload their Spotify data exports and view the connections between playlists in an interactive graph format using D3.js.

## Tech Stack

### Backend

- **Framework**: Flask 3.x with Flask-Security for authentication
- **Task Queue**: Celery with Redis
- **File Processing**: PyArrow for .parquet file handling
- **Database**: SQLAlchemy with Flask-Migrate
- **Python Version**: ^3.12

### Frontend

- **Approach**: Server-side rendering with HTMX (NO JavaScript business logic)
- **CSS Framework**: TailwindCSS v4 with DaisyUI components
- **Visualization**: D3.js (only for graph visualization)
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

## Key Features

### Current Implementation

1. **User Authentication**: Flask-Security with email/password
2. **File Upload**:
    - Accepts .parquet files up to 500MB
    - Validates parquet format using PyArrow
    - Stores files with timestamp prefixes
    - Lists uploaded files with metadata
3. **Data Visualization**: Interactive D3.js graphs showing playlist connections
4. **Graph Features**: Canvas-based rendering with zoom, pan, and node dragging
5. **Responsive UI**: Mobile-first design with bottom navigation
6. **Theme Support**: Light/dark theme switcher

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
npm run dev                      # Watch and compile Tailwind CSS + TypeScript
npm run build                    # Build everything optimized for production

# Individual commands
npm run dev:css                  # Watch CSS only
npm run dev:ts                   # Watch TypeScript only
npm run build:css                # Minified CSS
npm run build:ts                 # Minified, tree-shaken JavaScript
```

### Build Features

**Development:**

- Hot reload for TypeScript files
- Inline source maps for debugging
- No minification for readable output
- Fast incremental compilation

**Production:**

- Minification for smaller file sizes
- Tree shaking removes unused D3 code
- Optimized builds (~22KB gzipped)

### TypeScript Development

All TypeScript files in `app/typescript/` are automatically built - no config needed!

**File Structure:**

- **Input:** `app/typescript/*.ts`
- **Output:** `app/static/js/build/` (gitignored)

**Development Workflow:**

1. Run `npm run dev` in one terminal
2. Run `flask run` in another terminal
3. Edit TypeScript files in `app/typescript/`
4. Changes auto-compile and Flask auto-reloads

**Adding New TypeScript Files:**

1. Create new `.ts` file in `app/typescript/`
2. Export functions using ES module syntax:
    ```typescript
    // app/typescript/new-feature.ts
    export function myFeature() {
        // Your code here
    }
    ```
3. Import in templates using ES modules:
    ```html
    <script type="module">
        import { myFeature } from "{{ url_for('static', filename='js/build/new-feature.js') }}";
        myFeature();
    </script>
    ```

## Docker Configuration

Before running in Docker:

- [ ] Rename the project in `docker-compose.yml` at the `name` property
- [ ] Configure PostHog analytics key or remove from compose
- [ ] Configure Stripe payment key or remove from compose
- [ ] Review nginx configuration if using reverse proxy

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Required Variables

```bash
SECRET_KEY=your-secret-key                    # Generate a secure random key
SECURITY_PASSWORD_SALT=your-salt-here         # Generate a random salt for password hashing
SQLALCHEMY_DATABASE_URI=sqlite:///dev.db      # Database connection string
APP_SETTINGS=config.DevelopmentConfig         # Configuration class to use
APP_NAME=Flask App                            # Application name
```

### Mail Configuration (Required for email features)

```bash
MAIL_SERVER=smtp.example.com                  # SMTP server address
MAIL_PORT=587                                 # SMTP port
MAIL_USERNAME=your-email@example.com          # Email username
MAIL_PASSWORD=your-password                   # Email password
```

### Spotify API (Required for playlist enrichment)

```bash
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
```

### Optional Variables

```bash
HOST_NAME=localhost:5000                      # Server name for production
REDIS_URL=redis://localhost:6379              # Redis connection URL
MAINTENANCE_MODE=False                         # Enable maintenance mode
LOG_TO_STDOUT=False                           # Log to stdout instead of file
STRIPE_SECRET_KEY=                           # Stripe API key for payments
STRIPE_WEBHOOK_SECRET=                        # Stripe webhook secret
POSTHOG_API_KEY=                             # PostHog analytics key
```

## Security Considerations

- Flask-Security handles authentication and authorization
- CSRF protection enabled via Flask-WTF
- Secure session cookies in production
- Password salt must be configured (app will fail without it)

## HTMX Patterns

The application uses HTMX for dynamic updates:

- **Boosted Navigation**: Main layout uses hx-boost for SPA-like navigation but swaps the innerHTML of the #content div
- **Partial Updates**: Forms return partial HTML templates
- **Error Handling**: Appropriate HTTP status codes with error partials

## Development Guidelines

### Code Style

- **Python**: Use Black formatter, Ruff linter, MyPy for type checking
- **HTML**: Use Prettier with Jinja template plugin
- **Templates**: Follow existing partials pattern for HTMX responses

### Important Notes

- Prefer HTMX over JavaScript for business logic
- Follow existing template structure for consistency
- Use server-side rendering for all UI updates

### Testing

- Test structure follows app structure
- Focus on integration tests for HTMX endpoints

## Contributing

1. Follow existing code conventions and development guidelines
2. Use Ruff, Black, and MyPy for code quality
3. Write tests for new features
4. Update documentation as needed

## License

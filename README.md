# golf
golf with friends

## Starting the Django project

```bash
make setup
```

This will create a virtual environment and install all dependencies from `requirements.txt`.

## Running the server

```bash
make run
```

The Django development server will start and be available at `http://localhost:8000`.

## Database setup

```bash
make migrate
```

Generates and applies all database migrations.

## Available commands

- `make setup` - Create venv and install dependencies
- `make migrate` - Generate and apply database migrations
- `make run` - Start the Django development server
- `make test` - Run the test suite
- `make shell` - Open the Django interactive shell
- `make backup` - Export database to timestamped JSON
- `make restore` - Load data from the most recent backup file
- `make format` - Format code with Ruff and djlint
- `make lint` - Run linting checks
- `make check` - Run format, test, and backup in sequence
- `make clean` - Remove __pycache__ and build artifacts
- `make handicap` - Update all player handicaps based on their rounds
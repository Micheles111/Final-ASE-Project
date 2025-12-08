Preguntar por el tem de la base de datos El proyecto original es Flask/Python (microservicios con Docker)
- Este entorno de v0 es Next.js/React, no Flask
- No hay base de datos configurada actualmente

El proyecto original incluía:

- 40 cartas españolas (Oros, Copas, Espadas, Bastos)
- Un servicio de backend en Python/Flask
- Base de datos PostgreSQL (según el docker-compose.yml)
- Frontend Flask que muestra las cartas
La interfaz no se por que no me va

Cosas comprobadas de los casos de uso :
create an account - Si
login into the game - Si
check/modify my profile - Si
be safe about my account data - Creo que si
see the overall card collection - Si
view the details of a card - 1. Si pero quiero perfeccionarlo hacinedo una pagina por cada carta puede ser una option o un añadido para meterle algo de nuevo texto
start a new game - Si
select the subset of cards - Si
select a card - Si
know the score - si
know the turns - si
see the score -su
know who won the turn - si
know who won a match -si
that the rules are not violated - si
view the list of my old matches - si
view the details of one of my matches - si
view the leaderboards - si entre amigos
prevent people to tamper my old matches - 2.no lo se a q se refiere

Green: 
the timer of the move - si
who's turn it is  - si
see which cards I have and which cards I have to play - no
to be able to see the cards in my hand - si
I want set a maximum playing time - no 
I want to join a tournument - no
play against a bot - yes
request to a rematch - yes
I want to send a battle invitation - yes
to able to surrender - yes
be able to ask for a rematch - yes
I want to receive one hint per game - no
I want to distinguish ranked or friendly matches - no
I wanto to play locally - si
I want to use emojis during the match - si, solo emojis no se si quieren mas
add friends - yes
view my firends list - si
remove a firend from my friends list - si
view my friend matches - no
unlock achievements/objective - no pero se podria hacer, ganas new emojis,avatar


# FinalASEProject1 - La Escoba Card Game

A **La Escoba** card game platform (classic Spanish card game) with **microservices architecture**. The project includes a web frontend, API Gateway, and multiple specialized services deployed with Docker.

## Overview

**La Escoba** is a traditional Spanish card game for 2-4 players. In this version:
- ♠️ Played with a Spanish deck (40 cards: 4 suits, values 1-7, jack, knight, king)
- 🎮 Support for playing against CPU, local (Guest), or against other players
- 👥 Friend system and challenges between players
- 📊 Global leaderboard and personal statistics
- 🔐 Secure authentication with JWT and encrypted passwords
- ⚡ Scalable microservices architecture

## Architecture

The project uses a **microservices architecture** with the following components:

### Backend Services (Python/Flask + HTTPS)
- **API Gateway** (Port 5000): Centralized proxy that routes requests to specialized services
- **Auth Service**: Handles registration, login, and user validation with JWT
- **Player Service**: Player profiles, statistics, and friend system
- **Cards Service**: Spanish deck management
- **Match Service**: Game logic, turns, and La Escoba rules
- **History Service**: Storage of played games and statistics
- **Matchmaking Service** (integrated in Match Service): Automatic opponent search

### Frontend
- **Frontend Service** (Port 8080): Web interface with Flask + HTML/CSS
  - Login/Registration
  - Main board (dashboard)
  - Interactive game room
  - Friends and challenges management
  - Leaderboard
  - Game history
  - Admin panel

### Databases and Infrastructure
- **PostgreSQL**: Persistent database for users, players, history
- **Redis**: In-memory cache for active game states
- **Docker Compose**: Container orchestration

## Quick Start

### Requirements
- Docker and Docker Compose
- Python 3.10+ (if running locally without Docker)

### Installation and Execution

\`\`\`bash
# Clone the repository
git clone <repo-url>
cd FinalASEProject1

# Start all services with Docker
docker-compose up --build

# The application will be available at:
# - Frontend: http://localhost:8080
# - API Gateway: https://localhost:5000
\`\`\`

### Environment Variables

The `docker-compose.yml` file already configures the necessary variables:
- `DATABASE_URL`: PostgreSQL connection
- `REDIS_HOST`: Redis host for caching
- `SECRET_KEY`: JWT key for auth-service

### Admin Credentials

Username: `admin`
Password: `Admin123!`

Access at: http://localhost:8080/admin

## Directory Structure

\`\`\`
FinalASEProject1/
├── services/
│   ├── api-gateway/           # Central proxy (Flask)
│   ├── auth-service/          # Authentication with JWT
│   ├── cards-service/         # Deck management
│   ├── player-service/        # Profiles and friends
│   ├── match-service/         # Game logic and matchmaking
│   ├── history-service/       # Game history
│   └── frontend/              # Web interface (Flask + Jinja2)
│       ├── static/
│       │   └── cards/         # Card images (40 Spanish cards)
│       └── templates/         # HTML templates
├── certs/                      # SSL/TLS certificates (auto-generated)
├── docs/
│   └── openapi/               # OpenAPI/Swagger specification
├── scripts/                    # Utility scripts
├── tests/                      # Tests and performance (Locust, Postman)
├── docker-compose.yml         # Container configuration
└── package.json               # (Frontend Next.js - optional)
\`\`\`

## Key Concepts of La Escoba

### Game Rules
1. **Objective**: Capture the most cards and points
2. **Capture**: One card can capture another(s) on the table if their values sum to the same total
3. **Escoba**: When capturing ALL cards on the table, gains bonus points
4. **Scoring**:
   - Escoba (clear the table): Variable according to local rules
   - Majority of cards
   - Majority of golds (coins)
   - Seven of golds (special, 1 point)
   - Seven in any suit

## Main Endpoints

### Authentication
- `POST /auth/register` - Register user
- `POST /auth/login` - Login (returns JWT token)
- `GET /auth/me` - Current user information
- `PUT /auth/update` - Update profile

### Players
- `GET /players/{username}` - Player statistics
- `POST /players/{username}` - Create player profile
- `GET /players/leaderboard/top` - Top 10 players

### Matches
- `POST /matches` - Create new match
- `GET /matches/{match_id}` - Current state
- `POST /matches/{match_id}/play` - Play a card
- `POST /matches/{match_id}/surrender` - Surrender

### Friends
- `POST /friends/request` - Send friend request
- `POST /friends/response` - Accept/reject request
- `GET /friends/list/{username}` - Friends list
- `POST /friends/remove` - Remove friend

### History
- `GET /history/{username}` - Game history
- `GET /history/match/{match_id}` - Match details

### Matchmaking
- `POST /matchmaking/join` - Join search queue
- `GET /matchmaking/status/{username}` - Search status
- `POST /matchmaking/leave` - Leave queue

See complete specification in `/docs/openapi/openapi.yaml`

## Security

### Authentication
- JWT tokens with 24-hour expiration
- Passwords encrypted with bcrypt
- Password complexity validation

### Communication
- HTTPS with SSL/TLS certificates (self-signed in development)
- Certificate warnings disabled for development

### Database
- Protected connectors
- Input validation on all endpoints

## Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: PostgreSQL
- **Cache**: Redis
- **Authentication**: JWT (PyJWT)
- **Encryption**: bcrypt
- **API Gateway**: Flask + Gunicorn

### Frontend
- **Framework**: Flask + Jinja2 Templates
- **Styling**: HTML/CSS Bootstrap (implicit in templates)
- **Communication**: HTTP/HTTPS Requests

### DevOps
- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **Testing**: Locust (load testing), Postman (API testing)

## Development

### Running Services Locally (without Docker)
\`\`\`bash
# Terminal 1: PostgreSQL
docker run -e POSTGRES_PASSWORD=password123 -p 5432:5432 postgres:15

# Terminal 2: Redis
docker run -p 6379:6379 redis:7

# Terminal 3+: Each service
cd services/auth-service
pip install -r requirements.txt
python app.py
\`\`\`

### Testing
\`\`\`bash
# Load testing with Locust
cd tests/locust
locust -f locustfile.py --host=https://localhost:5000

# Postman collection available in tests/postman/
\`\`\`

### Generate SSL Certificates (if needed)
\`\`\`bash
cd certs
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
\`\`\`

## Project Statistics

- **6 Microservices** specialized
- **40 Cards** in the Spanish deck (images included)
- **10+ HTML Templates** for the interface
- **Multiple API Endpoints** (Auth, Players, Matches, History, Friends, Matchmaking)
- **PostgreSQL + Redis** for persistence and caching

## Troubleshooting

### Service unable to connect
1. Verify all containers are running: `docker-compose ps`
2. Check logs: `docker-compose logs <service-name>`
3. Verify SSL certificates: `ls certs/`

### Database connection failed
1. Wait for PostgreSQL to be healthy (5-10 seconds)
2. Verify credentials in docker-compose.yml

### Token expired or invalid
1. Login again to get a fresh token
2. Tokens expire every 24 hours

## Additional Documentation

- [Detailed Architecture](./ARCHITECTURE.md)
- [OpenAPI Specification](./docs/openapi/openapi.yaml)

## Team

**Project**: FinalASEProject1
**Subject**: Advanced Software Engineering (ASE)
**Course**: 2024-2025
**Members**:
- Elena Martínez Vazquez (e.martinezvazquez@student.unipi.it)
- Mario Perez Perez (@student.unipi.it)
- Michele F. P. Sagone (@student.unipi.it)

---
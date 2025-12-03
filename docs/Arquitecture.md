# Architecture Documentation - FinalASEProject1

## Architecture Overview

The project uses a **microservices architecture** with the following principles:

1. **Separation of concerns**: Each service has a specific domain
2. **Independence**: Services can be deployed and scaled independently
3. **Centralized communication**: All requests pass through an API Gateway
4. **Distributed persistence**: Each service accesses the same PostgreSQL database
5. **Distributed cache**: Redis for active game states

## Component Diagram

```bash
┌─────────────────────────────────────────────────────────────┐
│                    WEB CLIENT                               │
│              (Frontend Service - Port 8080)                 │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Login      │  │   Dashboard  │  │   Gameplay  │     │
│  │   Register   │  │   Leaderboard│  │   Friends   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTPS
┌─────────────────────────────────────────────────────────────┐
│              API GATEWAY (Port 5000)                         │
│         Central proxy for all services                       │
│                                                              │
│  Routes:                                                     │
│  /auth         → Auth-Service                               │
│  /cards        → Cards-Service                              │
│  /players      → Player-Service                             │
│  /matches      → Match-Service                              │
│  /history      → History-Service                            │
│  /friends      → Player-Service                             │
│  /matchmaking  → Match-Service                              │
└─────────────────────────────────────────────────────────────┘
        ↓                           ↓                  ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   AUTH       │  │   CARDS      │  │   PLAYER     │
│   SERVICE    │  │   SERVICE    │  │   SERVICE    │
│              │  │              │  │              │
│ • Register   │  │ • Get Deck   │  │ • Profiles   │
│ • Login      │  │ • Card Info  │  │ • Stats      │
│ • Tokens     │  │ • Validation │  │ • Friends    │
└──────────────┘  └──────────────┘  └──────────────┘
        │                                    │
        ├────────────────┬───────────────────┤
        │                │                   │
    [PostgreSQL Database]                [Redis Cache]
    ┌──────────────────┐          ┌──────────────────┐
    │ users            │          │ Game States      │
    │ players          │          │ Active Matches   │
    │ match_history    │          │ Matchmaking Q    │
    │ friends          │          │ User Sessions    │
    │ ...              │          └──────────────────┘
    └──────────────────┘
        ↑                                    ↑
        │                │                   │
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   MATCH      │  │   HISTORY    │  │   MATCH      │
│   SERVICE    │  │   SERVICE    │  │   SERVICE    │
│              │  │              │  │  (continued) │
│ • Game Logic │  │ • Store      │  │ • Matchmaking│
│ • Turns      │  │ • Query      │  │ • Queue Mgmt │
│ • Card Play  │  │ • Stats      │  │ • Pairing    │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Each Service's Responsibilities

### 1. API Gateway (Flask + Gunicorn)

**Purpose**: Single entry point. Routes requests to specialized services.

**Features**:
- Transparent proxy of HTTP/HTTPS requests
- Centralized header and authentication handling
- Disabling of self-signed SSL certificate warnings
- All services communicate via HTTPS (internal security)

**Root endpoints**: `/auth`, `/cards`, `/players`, `/matches`, `/history`, `/friends`, `/invites`, `/matchmaking`

**Dependencies**: All other services

### 2. Auth Service (Python/Flask + PostgreSQL)

**Purpose**: Authentication management, registration, and user validation.

**Responsibilities**:
- Register new users with complex password validation
- Authenticate users and generate JWT tokens (valid 24h)
- Validate tokens on each request
- Encrypt passwords with bcrypt
- Update user profiles

**Database**:
```sql
users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE,
  email VARCHAR(120) UNIQUE,
  password_hash VARCHAR(128)
)
```

**Endpoints**:
- `POST /auth/register` - Create user
- `POST /auth/login` - Get JWT token
- `GET /auth/me` - Current user information (requires token)
- `PUT /auth/update` - Update profile
- `POST /auth/validate` - Validate token
- `GET /auth/users` - User list (admin)

**Business Rules**:
- Password: 8-20 characters, uppercase, number, special character
- Username and email unique
- JWT with 24-hour expiration

### 3. Cards Service (Python/Flask)

**Purpose**: Management of the deck of cards and its information.

**Responsibilities**:
- Provide the complete list of 40 Spanish cards
- Information about each card (number, suit, value)
- Card validation during gameplay

**Card Data**:
```
Suits: Gold, Cups, Swords, Clubs
Values: 1-7, Jack(8), Knight(9), King(10)
```

**Endpoints**:
- `GET /cards/cards` - Get complete deck

**State**: Stateless (no state)

### 4. Player Service (Python/Flask + PostgreSQL)

**Purpose**: Management of player profiles, statistics, and friendship relationships.

**Responsibilities**:
- Create and maintain player profiles
- Calculate and store statistics (games won, total score, etc.)
- Friend system (add, remove, pending)
- Global leaderboard

**Database**:
```sql
players (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE,
  matches_played INT DEFAULT 0,
  matches_won INT DEFAULT 0,
  total_score INT DEFAULT 0,
  ...
)

friends (
  id SERIAL PRIMARY KEY,
  user_id INT,
  friend_id INT,
  status VARCHAR(20),  -- 'accepted', 'pending'
  created_at TIMESTAMP
)
```

**Endpoints**:
- `POST /players/{username}` - Create profile
- `GET /players/{username}` - Get statistics
- `GET /players/leaderboard/top` - Top 10
- `POST /players/{username}/heartbeat` - Update online status
- `POST /friends/request` - Send friend request
- `POST /friends/response` - Accept/reject
- `GET /friends/list/{username}` - Friends list
- `POST /friends/remove` - Remove friend

### 5. Match Service (Python/Flask + Redis)

**Purpose**: Orchestrates game logic, turns, and player matching.

**Responsibilities**:
- Create new matches
- Maintain game state (table cards, each player's hand, current turn)
- Process plays (card plays)
- Apply La Escoba rules
- Detect end of game
- Automatic matchmaking system (simple FIFO)

**State in Redis**:
```json
{
  "match_id": "uuid",
  "player1": "username1",
  "player2": "username2",
  "status": "active",
  "turn": "username1",
  "table": [card_ids],
  "hands": {
    "username1": [card_ids],
    "username2": [card_ids]
  },
  "scores": { "username1": 0, "username2": 0 }
}
```

**Endpoints**:
- `POST /matches` - Create match
- `GET /matches/{match_id}?player=username` - State (hides opponent's cards)
- `POST /matches/{match_id}/play` - Play card
- `POST /matches/{match_id}/surrender` - Surrender
- `POST /matchmaking/join` - Join queue
- `GET /matchmaking/status/{username}` - Check search status
- `POST /matchmaking/leave` - Leave queue

**La Escoba Rules Implemented**:
- One card captures others if values match
- Escoba (clear table): Special bonus
- End of game when deck cards run out

### 6. History Service (Python/Flask + PostgreSQL)

**Purpose**: Register and query game history.

**Responsibilities**:
- Store result of each match (winner, score, date)
- Save complete match details (moves, cards played)
- Generate historical statistics
- Match analysis

**Database**:
```sql
match_history (
  id SERIAL PRIMARY KEY,
  match_id VARCHAR(36) UNIQUE,
  player1 VARCHAR(50),
  player2 VARCHAR(50),
  winner VARCHAR(50),
  p1_score INT,
  p2_score INT,
  duration INT,
  played_at TIMESTAMP,
  moves JSON  -- Move details
)
```

**Endpoints**:
- `GET /history/{username}` - Player history
- `GET /history/match/{match_id}` - Match details
- `POST /history` - Save match (internal)

### 7. Frontend Service (Flask + Templates)

**Purpose**: Interactive web interface for players.

**Responsibilities**:
- Present user interface
- Session authentication
- Consume API Gateway for operations
- Render dynamic templates

**Main Pages**:
- `login.html` - Login
- `singUp.html` - Registration
- `dashboard.html` - Main board
- `game.html` - Game room
- `leaderboard.html` - Rankings
- `friends.html` - Friends management
- `history.html` - Game history
- `profile.html` - User profile
- `admin_dashboard.html` - Admin panel

**Static Resources**:
- `/static/cards/` - 40 Spanish card images
- Mapping: `{number}_{suit}.png` (e.g: `3_cups.png`)

## Data Model

### Tables in PostgreSQL

```sql
-- Auth Service
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(120) UNIQUE NOT NULL,
  password_hash VARCHAR(128) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player Service
CREATE TABLE players (
  id SERIAL PRIMARY KEY,
  user_id INT UNIQUE REFERENCES users(id),
  username VARCHAR(50) UNIQUE,
  matches_played INT DEFAULT 0,
  matches_won INT DEFAULT 0,
  total_score INT DEFAULT 0,
  win_rate FLOAT DEFAULT 0,
  last_login TIMESTAMP,
  is_online BOOLEAN DEFAULT FALSE
);

CREATE TABLE friends (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES players(id),
  friend_id INT REFERENCES players(id),
  status VARCHAR(20),  -- 'accepted', 'pending'
  created_at TIMESTAMP,
  UNIQUE(user_id, friend_id)
);

-- History Service
CREATE TABLE match_history (
  id SERIAL PRIMARY KEY,
  match_id VARCHAR(36) UNIQUE,
  player1 VARCHAR(50),
  player2 VARCHAR(50),
  winner VARCHAR(50),
  player1_score INT,
  player2_score INT,
  duration INT,  -- seconds
  played_at TIMESTAMP,
  moves JSONB  -- Array of moves
);
```

### Cache in Redis

```
matchmaking:queue          -- List of players searching
matchmaking:searching:{u}  -- Player u searching
match:{match_id}           -- Active match state
match:info:{match_id}      -- Match metadata
```

## Main Usage Flows

### 1. Registration and Login

```
Client → Frontend → Auth-Service → PostgreSQL
         (HTML form)   (JWT creation) (User store)
                                    ↓
                            JWT Token Generated
                                    ↓
                           Frontend stores in session
```

### 2. Create Match (vs CPU)

```
Client → Frontend → API-Gateway
                         ↓
                    Match-Service
                    ↓          ↓
                 Redis      PostgreSQL
              (State)    (History)
                    ↓
              Game State created
                    ↓
         Frontend redirects to /game/{match_id}
```

### 3. Play a Card

```
Client (JavaScript) → Frontend API Proxy → API-Gateway
                                               ↓
                                          Match-Service
                                          ↓          ↓
                    Validate move    Update
                    Apply rules      state in Redis
                         ↓                    ↓
                    JSON Response    Notify change
                         ↓
                   Frontend updates board
```

### 4. Friend System

```
Client → Frontend → Player-Service → PostgreSQL
         (Form)    (Register          (Store
                   request)           relationship)
                         ↓
              Notification to other user
                         ↓
        Other user can accept/reject
```

### 5. Automatic Matchmaking

```
Player1 joins queue → Redis:queue += Player1
                           ↓
Player2 joins queue → Redis:queue += Player2
                           ↓
        Match-Service detects 2+ players
                           ↓
        Create match, update Match Service
                           ↓
        Both clients redirected to /game
```

## Security

### Authentication and Authorization
- JWT tokens in `Authorization: Bearer <token>` header
- Tokens with 24-hour expiration
- Token validated on each sensitive request

### Encryption
- Passwords: bcrypt with salt
- Communication: HTTPS (self-signed certs in dev, Let's Encrypt in prod)

### Input Validation
- Complex password (8-20 characters, uppercase, number, special)
- Username validation (unique)
- Email validation

## Scalability and Performance

### Implemented Strategies
1. **Redis cache**: Active game states (fast access)
2. **PostgreSQL**: Persistent data (history, users)
3. **Microservices**: Independent scaling
4. **Docker**: Facilitates instance replication
5. **Stateless APIs**: Facilitates load balancing

### Future Optimization Points
- Load balancer (Nginx/HAProxy)
- Replicated databases
- Message queue (RabbitMQ) for events
- GraphQL instead of REST

## Testing

### Available Test Types

**Load Testing** (Locust):
```bash
cd tests/locust
locust -f locustfile.py --host=https://localhost:5000
```

**API Testing** (Postman):
```
Import collection: tests/postman/Escoba_Collection.json
```

## Deployment

### Production (Recommendations)

```yaml
# Upgrades for production
1. Use real SSL certificates (Let's Encrypt)
2. Configure environment variables (not in code)
3. Use managed PostgreSQL (AWS RDS, etc.)
4. Use managed Redis (AWS ElastiCache, etc.)
5. Add Load Balancer
6. Configure centralized logging
7. Monitoring with Prometheus + Grafana
```

## Design Notes

### Why microservices?
- **Separation of concerns**: Each team can work independently
- **Selective scalability**: Match-Service can replicate under demand
- **Fault tolerance**: One service down doesn't crash everything
- **Technology flexibility**: Each service can use different tech

### Why Flask?
- Lightweight and easy to learn
- Native HTTPS support
- Active Python community
- Easy to deploy in Docker

### Why Redis for game states?
- Very fast in-memory access
- Automatic TTL for cleaning old states
- Support for complex data structures

## Next Improvements

- [ ] Implement WebSockets for real-time updates
- [ ] Add push notifications
- [ ] Multi-language support
- [ ] Analytics dashboard
- [ ] Rating system and elo
- [ ] Match replays
- [ ] In-game chat

---
# Database Schema (PostgreSQL)

## users
| Column         | Type                     | Notes                          |
|----------------|--------------------------|---------------------------------|
| id             | UUID, primary key        | default gen_random_uuid()      |
| email          | TEXT, unique, not null   |                                  |
| password_hash  | TEXT, not null           | never store plaintext passwords |
| created_at     | TIMESTAMP, default now() |                                  |

## trips
| Column        | Type                         | Notes                                    |
|----------------|------------------------------|-------------------------------------------|
| id             | UUID, primary key            | default gen_random_uuid()                 |
| user_id        | UUID, FK → users.id          | ON DELETE CASCADE                          |
| destination    | TEXT, not null               |                                             |
| budget_total   | NUMERIC, not null            |                                             |
| days_count     | INTEGER, not null            |                                             |
| preferences    | TEXT[]                       | e.g. {"food","adventure"}                  |
| status         | TEXT, not null, default 'planning' | 'planning' \| 'active' \| 'completed' |
| created_at     | TIMESTAMP, default now()     |                                             |

## days
| Column       | Type                      | Notes                              |
|--------------|---------------------------|--------------------------------------|
| id           | UUID, primary key         | default gen_random_uuid()           |
| trip_id      | UUID, FK → trips.id       | ON DELETE CASCADE                    |
| day_number   | INTEGER, not null         |                                       |
| date         | DATE, nullable            |                                       |

Unique constraint: (trip_id, day_number) — a trip can't have two "Day 2"s.

## itinerary_items
| Column         | Type                      | Notes                                          |
|----------------|---------------------------|--------------------------------------------------|
| id             | UUID, primary key         | default gen_random_uuid()                        |
| day_id         | UUID, FK → days.id        | ON DELETE CASCADE                                 |
| place_name     | TEXT, not null            |                                                    |
| category       | TEXT, not null            | 'hotel' \| 'restaurant' \| 'attraction' \| 'transport' |
| estimated_cost | NUMERIC, not null         | set by the itinerary generator                    |
| visited        | BOOLEAN, not null, default false |                                              |
| order_in_day   | INTEGER, not null         |                                                    |
| notes          | TEXT, nullable            |                                                    |

No actual_cost column — per data-model.md, actual spend is derived by summing
the expenses table (next step), not stored here.

## expenses
| Column             | Type                      | Notes                                    |
|--------------------|---------------------------|---------------------------------------------|
| id                 | UUID, primary key         | default gen_random_uuid()                    |
| trip_id            | UUID, FK → trips.id       | ON DELETE CASCADE                             |
| itinerary_item_id  | UUID, FK → itinerary_items.id, nullable | null = unplanned spend (e.g. "bought water") |
| amount             | NUMERIC, not null         |                                                |
| category           | TEXT, nullable            | e.g. "food", "transport", "shopping"          |
| logged_at          | TIMESTAMP, default now()  |                                                |

## chat_messages
| Column            | Type                      | Notes                                |
|-------------------|---------------------------|-----------------------------------------|
| id                | UUID, primary key         | default gen_random_uuid()               |
| trip_id           | UUID, FK → trips.id, nullable | ON DELETE CASCADE; nullable because messages sent before CONFIRM (see conversation-flow.md) happen before a Trip row exists |
| role              | TEXT, not null            | 'user' \| 'assistant'                    |
| content           | TEXT, not null            |                                           |
| extracted_fields  | JSONB, nullable           |                                           |
| created_at        | TIMESTAMP, default now()  |                                           |

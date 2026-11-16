# FleetFreight TMS

[![backend](https://github.com/Vode72/fleetfreight-tms/actions/workflows/backend.yml/badge.svg)](https://github.com/Vode72/fleetfreight-tms/actions/workflows/backend.yml)
[![frontend](https://github.com/Vode72/fleetfreight-tms/actions/workflows/frontend.yml/badge.svg)](https://github.com/Vode72/fleetfreight-tms/actions/workflows/frontend.yml)
[![api-types](https://github.com/Vode72/fleetfreight-tms/actions/workflows/api-types.yml/badge.svg)](https://github.com/Vode72/fleetfreight-tms/actions/workflows/api-types.yml)

Transport management system that combines **load planning** (orders, routing, trips, costs and margin) with **day-level fleet planning** (which jobs a driver and truck can complete today within EU driving, working and rest time rules).

> Portfolio project. All data is fictional demo data.

## Background

FleetFreight TMS merges two earlier prototypes by the same author:

- [Freight Planner](https://github.com/Vode72/freight-planner): order-to-trip planning, cost and pricing engine, carriers, trailers, ferries
- [FleetFlow Planner](https://github.com/Vode72/fleetflow-planner): daily traffic planning cockpit, job sequencing, map and driving-time checks

The new system is designed from what both prototypes taught, built by a traffic coordinator with ~25 years of logistics experience.

## Core ideas

- **Node–Leg model:** every trip is a chain of nodes (tractor start, trailer pickup, loading, terminal, port departure and arrival, unloading, workshop, washing) with a leg between each pair
- **Trip = one loaded round of a trailer.** Tractors can be swapped at any node, and each tractor and driver gets its own job
- **Feasibility first:** the system calculates, checks and suggests; the traffic coordinator decides
- Accompanied and unaccompanied ferries, ADR, GDP, temperature-controlled and curtain-side transport, trailer pool, port handling

## Stack

React · TypeScript · Vite · Python · FastAPI · PostgreSQL · Alembic · pytest · Vitest

## Status

Phase 1 (skeleton, authentication, themes, CI) is complete; phase 2 (data model) is next. See [docs/suunnitelma.md](docs/suunnitelma.md) (Finnish) for the decision register, data model and roadmap, and [backend/README.md](backend/README.md) for running the app.

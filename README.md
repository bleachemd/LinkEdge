# LinkEdge
Infrastructure:
postgres (timescale/timescaledb:pg15, port 5432): Time-series storage for telemetry
redis (redis:7, port 6379): Cache and retry-buffer queue
mosquitto (eclipse-mosquitto:2, ports 1883/9001): MQTT message broker
chirpstack-gateway-bridge (chirpstack/cgb:4, port 1700/udp): Translates Semtech UDP to MQTT
chirpstack (chirpstack/chirpstack:4, port 8080): LoRaWAN network server
hub (builds from ./hub, port 8000): LinkEdge FastAPI core engine

rest api:
POST /api/v1/ingest: Direct HTTP ingestion (for non-LoRaWAN sources)
GET /api/v1/telemetry: Query history (filter by device, time, validity)
GET /api/v1/telemetry/{id}: Get a single readin
WS /api/v1/telemetry/ws/stream: Live WebSocket feed
CRUD /api/v1/devices: Register devices and map them to validation profiles
GET /api/v1/devices/profiles: List loaded decoder/validation profile
CRUD /api/v1/export-targets: Manage webhook destinations for cloud sy
POST /api/v1/export-targets/{id}/test: Fire a test payload to a target webhook
GET /health: System health check

device profiles:
generic: Pass-through mode with no strict rules (default for unknown devices).
soil_sensor_v1: JSON decoder. Strictly validates physical ranges for pH, temperature, moisture, EC, CO2, O2, CH4, N2O, vibroacoustic frequency, and amplitude.

quick start:
copy variablesfile: cp .env.example .env
edit env.
boot with docker compose up --build -d



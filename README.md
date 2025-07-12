# Scrobblarr

Scrobblarr is a Flask-based application designed to handle media scrobbling events and interact with Sonarr for managing TV series episodes. It listens for webhook events, processes them, and performs actions such as deleting or unmonitoring episodes based on the configuration.

## Features

- **Webhook Listener**: Handles `media.scrobble` events from media servers.
- **Database Management**: Stores scrobbling data in a SQLite database.
- **Sonarr Integration**: Deletes or unmonitors episodes in Sonarr based on configuration.
- **Dynamic Configuration**: Watches for changes in `config.json` and reloads automatically.

## Requirements

- Docker
- Docker Compose

## Quick Start

1. Create a `config.json` file in the root directory with the following structure:
   ```json
   {
       "sonarr": {
           "url": "http://your-sonarr-url",
           "api_key": "your-sonarr-api-key"
       },
       "grace_days": 2,           # Global grace days before deleting episodes
       "unmonitor_after_delete": true,
       "series_settings": {       # Series-specific settings
           "Example Series": {
               "grace_days": 0
           }
       }
   }
   ```

2. Create a `docker-compose.yml` file with the following content:
   ```yaml
   version: '3.8'

   services:
     scrobblarr:
       image: ibooker88/scrobblarr
       container_name: scrobblarr
       ports:
         - "5000:5000"
       volumes:
         - ./config.json:/app/config.json
       restart: unless-stopped
   ```

3. Start the application using Docker Compose:
   ```bash
   docker-compose up -d
   ```

## Setting Up a Webhook from Plex

To configure Plex to send webhook events to Scrobblarr, follow these steps:

1. Open Plex and navigate to `Settings`.
2. Under `Webhooks`, add a new webhook.
3. Enter the following URL as the webhook target:
   ```
   http://<scrobblarr-host>:5000/webhook
   ```
   Replace `<scrobblarr-host>` with the IP address or hostname of the machine running Scrobblarr.
4. Save the webhook configuration.

Once configured, Plex will send `media.scrobble` events to Scrobblarr, which will process them based on your settings.

## Database

The application uses a SQLite database (`watched.db`) to store scrobbling data. The database is initialized automatically if it does not exist.

## Logging

Logs are printed to the console with different levels (INFO, WARNING, ERROR) to help monitor the application's behavior.

## Hot Reloading Configuration

Scrobblarr supports hot reloading of the `config.json` file. This means that any changes made to the configuration file will be automatically detected and applied without needing to restart the application.

### How It Works

- The application continuously monitors the `config.json` file for changes.
- When a change is detected, the configuration is reloaded, and the new settings are applied immediately.
- This allows you to update settings such as Sonarr integration, grace days, or series-specific overrides on the fly.

### Benefits

- No downtime required for configuration updates.
- Simplifies the process of fine-tuning application behavior.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Docker Hub

The Docker image for Scrobblarr is available on Docker Hub. You can find it here:

[Scrobblarr on Docker Hub](https://hub.docker.com/r/ibooker88/scrobblarr)

# Race Ready

**Collaborative Checklist System for Racing Events**

RaceReady is a web-based collaborative checklist application designed for communicating between teams on large events. It was developed for the GT World Series eSports events, however is flexible enough to be used for various types of events. It provides real-time synchronization of checklist items across multiple devices and integrates seamlessly with Companion for streamlined workflow management.

## Features

### 🎯 Core Functionality
- **Real-time Collaborative Checklists**: Multiple team members can check off items simultaneously
- **WebSocket Synchronization**: Instant updates across all connected devices
- **Multiple Checklist Management**: Support for multiple independent checklists
- **Status Tracking**: Visual indicators for completed/pending items

### 🎮 Companion Integration
- **Stream Deck Support**: Direct integration with Elgato Stream Deck via the [companion module](https://github.com/pingue/companion-module-raceready)
- **Visual Feedback**: Button states reflect checklist item status
- **Remote Control**: Toggle checklist items directly from hardware controllers
- **Real-time Updates**: Button states update automatically as items are completed

### 🔧 Administration
- **Web-based Admin Panel**: Easy management of checklists and items
- **SQLite Database**: Lightweight, reliable data storage
- **Companion**: Pre-configured companion page for easy setup

## Quick Start

### Prerequisites
- Python 3.7+
- SQLite3
- Modern web browser

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd raceready
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up the database** (optional - auto-created on first run)
   ```bash
   export DB_PATH=/path/to/your/database.sqlite3
   ```

4. **Run the application**
   ```bash
   python raceready.py
   ```

5. **Access the application**
   - Main interface: `http://localhost:5000`
   - Admin panel: `http://localhost:5000/admin`

### Docker Deployment from dockerhub
```bash
docker pull pingue/raceready:latest
docker run -p 5000:5000 -v ./data:/data pingue/raceready:latest
```

## Configuration

### Environment Variables
- `DB_PATH`: Path to SQLite database file (default: `/data/db.sqlite3`)

### Database Setup
The application automatically creates the necessary database tables on first run:
- `checklists`: Stores checklist metadata
- `actions`: Stores individual checklist items with status

## Usage

### Web Interface
1. **Main Dashboard**: View and interact with checklist items
2. **Checklist Selection**: Switch between different checklists using the dropdown
3. **Item Management**: Click items to toggle their completion status
4. **Reset Function**: Clear all item statuses with the "Reset All" button

### Admin Panel
- Create and manage multiple checklists
- Add, edit, or remove checklist items
- Monitor system status and version information

### Companion Integration
1. **Install the Companion Module**
   ```bash
   cd companion-module-raceready
   npm install
   ```

2. **Configure Connection**
   - Host: Your RaceReady server IP
   - Port: 5000 (default)

3. **Import Configuration**
   - Download configuration from `/companion_export`
   - Import into Companion software

## API Endpoints

### REST API
- `GET /` - Main dashboard
- `GET /admin` - Administration interface
- `POST /toggle_by_title` - Toggle item status by title
- `GET /action_title` - Get action title by ID
- `GET /companion_export` - Export Companion configuration

### WebSocket Events
- Real-time updates for checklist changes
- Automatic synchronization across all connected clients

## Architecture

### Technology Stack
- **Backend**: Python Flask with SocketIO
- **Frontend**: HTML/CSS/JavaScript with Bootstrap
- **Database**: SQLite3
- **Real-time**: WebSocket communication
- **Integration**: Companion module for hardware control

### Project Structure
```
raceready/
├── raceready.py           # Main application server
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── index.html        # Main dashboard
│   └── admin.html        # Admin interface
├── static/              # Static assets
│   ├── index.js         # Frontend JavaScript
│   └── raceready.companionconfig  # Companion configuration
└── data/               # Database storage
    └── db.sqlite3      # SQLite database
```

## Development

### Running in Development Mode
```bash
export FLASK_ENV=development
python raceready.py
```

### Database Management
For database operations requiring elevated privileges:
```bash
# Unlock database (if needed)
echo .dump | sudo sqlite3 data/db.sqlite3 | sudo sqlite3 data/db2.sqlite3 && sudo mv data/db2.sqlite3 data/db.sqlite3
```

## Deployment

### Docker Deployment
```bash
docker build -t raceready .
docker run -p 5000:5000 -v ./data:/data raceready
```

### Production Considerations
- Use a reverse proxy (nginx/Apache) for production
- Configure appropriate database permissions
- Set up SSL/TLS for secure connections
- Consider using a more robust database for high-scale deployments

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the terms specified in the LICENSE file.

## Support

For issues, feature requests, or questions:
- Check existing GitHub issues
- Create a new issue with detailed information
- Include system information and steps to reproduce

---

**RaceReady** - Making event preparation seamless and collaborative.

# Rave Ramen Reviews 🍜

A RESTful API for managing and querying ramen reviews built with Python and Flask

## Description

Rave Ramen Reviews is a comprehensive REST API that allows users to create, read, update, and delete ramen review data. The API stores ramen information including brand, country of origin, type, packaging, and ratings in a SQLite database. It provides both programmatic API access and a web-based documentation interface for easy integration.

## Features

- Create and manage a SQLite database for ramen reviews
- Add single or bulk ramen reviews from CSV files
- Search reviews with flexible filtering and sorting options
- Edit existing reviews with partial update support
- Delete individual or all reviews
- RESTful API endpoints with JSON responses
- Web-based API documentation
- Keyword search functionality for ramen types

## Technologies Used

- Python 3
- Flask (Web Framework)
- Flask-RESTful (REST API)
- SQLite (Database)
- HTML/CSS/JavaScript (Documentation UI)
- Gunicorn (Production Server)

## Installation

```bash
# Clone the repository
git clone https://github.com/hongyime/ramenreviews.git

# Navigate to project directory
cd ramenreviews

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Run the application
python main.py
```

The API will be available at `http://127.0.0.1:5000/`

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/createone` | GET | Create a new database and table |
| `/api/addone` | PUT | Add a single ramen review |
| `/api/addmany` | GET | Import reviews from CSV file |
| `/api/searchsome` | PUT | Search reviews with filters |
| `/api/selectall` | GET | Get all reviews |
| `/api/editsome` | PUT | Update existing reviews |
| `/api/deletesome` | PUT | Delete specific reviews |
| `/api/deleteall` | GET | Delete all reviews |

### Example Request

```bash
# Search for ramen reviews by brand
curl -X PUT http://127.0.0.1:5000/api/searchsome \
  -d "brand=Brand A" \
  -d "sortby=rating"
```

## Demo

~~https://rave-ramenapi.herokuapp.com~~ (No longer available)

## Disclaimer

1. FOR EDUCATIONAL PURPOSES ONLY
2. USE AT YOUR OWN DISCRETION

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

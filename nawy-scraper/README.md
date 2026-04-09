# Nawy.com Real Estate Web Scraper

A production-grade Python web scraper for [Nawy.com](https://www.nawy.com/ar) that collects real estate data and stores it in MongoDB.

## ✨ Features

- **Compounds Scraper**: Extracts compound details, amenities, prices, images
- **Developers Scraper**: Collects developer portfolios and project counts
- **Units Scraper**: Scrapes individual property listings with payment plans
- **Anti-Detection**: User-agent rotation, human-like delays, stealth browser config
- **MongoDB Integration**: Upserts data with deduplication
- **Export Options**: JSON and CSV output with summary reports

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd nawy-scraper
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

The `.env` file is pre-configured with MongoDB credentials. Customize if needed:

```env
MONGO_URI=mongodb+srv://...
HEADLESS=true
DELAY_MIN=3.0
DELAY_MAX=6.0
```

### 3. Run Scraper

```bash
# Full scrape (compounds + developers + units)
python main.py --mode full

# Test with 3 compounds first
python main.py --test

# Scrape only compounds
python main.py --mode compounds

# With visible browser (for debugging)
python main.py --mode compounds --limit 5 --no-headless

# Export to CSV only
python main.py --mode full --export csv
```

## 📁 Project Structure

```
nawy-scraper/
├── config/
│   └── settings.py         # Configuration (MongoDB, delays, UA rotation)
├── database/
│   ├── connection.py       # MongoDB client with CRUD operations
│   └── models.py           # Pydantic models matching schemas
├── scrapers/
│   ├── base_scraper.py     # Playwright + anti-detection base
│   ├── compound_scraper.py # Compound list + detail pages
│   ├── developer_scraper.py# Developer pages
│   └── unit_scraper.py     # Unit listings
├── utils/
│   ├── data_cleaner.py     # Normalization, deduplication
│   └── export.py           # JSON/CSV/Excel export
├── exports/                # Output files
├── main.py                 # CLI entry point
├── requirements.txt
└── .env
```

## 🔧 CLI Options

| Option | Description |
|--------|-------------|
| `--mode` | `full`, `compounds`, `developers`, `units` |
| `--limit N` | Limit number of items to scrape |
| `--test` | Quick test (3 items only) |
| `--export` | `json`, `csv`, or `both` |
| `--headless/--no-headless` | Browser visibility |
| `--dry-run` | Scrape without saving to DB |

## 📊 Data Models

### Compound
- name, location, developer_name
- price_min, price_max
- amenities_list, images_urls
- unit_count, delivery_year

### Developer
- dev_name, compounds_count
- logo_url, description
- compounds_list

### Unit
- type (apartment/villa/etc)
- area, price, bedrooms, bathrooms
- down_payment, installment_years
- finishing, status

## ⚠️ Important Notes

1. **Rate Limiting**: Default 3-6 second delays between requests
2. **First Run**: Test with `--limit 5` before full scrape
3. **Logs**: Check `scraper.log` for detailed output
4. **MongoDB**: Data is upserted (no duplicates)

## 🔒 Anti-Detection Features

- Random User-Agent rotation (5 agents)
- Random viewport sizes
- Human-like scroll behavior
- Stealth Chromium configuration
- Exponential backoff on errors

## 📝 License

For research and educational purposes only.

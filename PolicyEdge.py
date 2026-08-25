# =============================================================================
# PolicyEdge — Flask app (agenda tracking for California local government)
# =============================================================================
from flask_pymongo import PyMongo
from flask_compress import Compress
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, send_from_directory, Blueprint, abort, Response
from forms import searchForm, monitorListform, chartForm
import bcrypt
from datetime import date, datetime, timedelta
import os
import re
import logging
from collections import Counter
from flask_mail import Mail
from stripe_service import init as stripe_init, create_checkout_session, handle_webhook, get_user_stripe_customer, validate_registration
from helpers import (get_date_threshold, handle_issue_operation, get_user_saved_agendas, int2date,)
from map_utils import fetch_geo_info, create_folium_map
from jobs import start_scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from static_routes import static_pages
from error_handlers import register_error_handlers
import stripe
from dotenv import load_dotenv

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Computed
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from authlib.integrations.flask_client import OAuth

from flask_wtf import CSRFProtect

from werkzeug.middleware.proxy_fix import ProxyFix

import math
# =============================================================================
# INITIALIZATION AND CONFIGURATION
# =============================================================================
load_dotenv()

app = Flask(__name__)
Compress(app)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db = SQLAlchemy()

# Configuration - Using environment variables for security
app.config['MONGO_URI'] = os.environ.get("MONGO_URI")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.secret_key = os.environ.get("SESS_KEY")
app.config['YOUR_DOMAIN'] = os.environ.get("YOUR_DOMAIN", "http://127.0.0.1:5001/")
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db.init_app(app)

# Initialize extensions
mongo = PyMongo(app)
mail = Mail(app)

csrf = CSRFProtect(app)

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

# Constants
stripe_keys = {
    'secret_key': os.environ['SECRET_KEY'],
    'publishable_key': os.environ['PUBLISHABLE_KEY']
}
stripe.api_key = stripe_keys['secret_key']

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE MODELS (SQLAlchemy)
# =============================================================================
class County(db.Model):
    __tablename__ = "counties"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)


class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    county_id = db.Column(db.Integer, db.ForeignKey("counties.id"))


class Meeting(db.Model):
    __tablename__ = "meetings"
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"))
    meeting_type = db.Column(db.Text)
    meeting_date = db.Column(db.Date)


class Agenda(db.Model):
    __tablename__ = "Agendas"
    __table_args__ = (
        db.Index("agenda_search_idx", "search_vector", postgresql_using="gin"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    county = db.Column(db.Text)
    city = db.Column(db.Text)
    date = db.Column(db.Integer)
    num = db.Column(db.Text)
    meeting_type = db.Column(db.Text)
    item_type = db.Column(db.Text)
    description = db.Column(db.Text)
    search_vector = db.Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', "
            "coalesce(county, '') || ' ' || "
            "coalesce(city, '') || ' ' || "
            "coalesce(meeting_type, '') || ' ' || "
            "coalesce(item_type, '') || ' ' || "
            "coalesce(description, ''))",
            persisted=True
        )
    )

class GeoLocation(db.Model):
    __tablename__ = "geoloc"

    mongo_id = db.Column("_id", db.Text, primary_key=True)
    city = db.Column(db.Text, nullable=False, index=True)
    state_id = db.Column(db.Text)
    county_name = db.Column(db.Text)
    latitude = db.Column("lat", db.Float)
    longitude = db.Column("lng", db.Float)
    website = db.Column("webadress", db.Text)

from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.dialects.postgresql import JSONB

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.Text, nullable=False, unique=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=True)  # allow Google-only users
    google_sub = db.Column(db.Text, unique=True, nullable=True)
    auth_provider = db.Column(db.Text, nullable=False, default="local")
    stripe_customer_id = db.Column(db.Text)
    stripe_subscription_id = db.Column(db.Text)
    subscription_active = db.Column(db.Boolean, nullable=False, default=False)
    issues = db.Column(MutableList.as_mutable(JSONB), nullable=False, default=list)
    agenda_unique_ids = db.Column(MutableList.as_mutable(JSONB), nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)


# Must be below the User class
stripe_init(db, User)
# -------------------------------
# COUNTY AGENDA HELPERS
# -------------------------------
def get_county_agendas(county_name, weeks_back=16):
    """Return recent City Council agenda items for a county."""
    threshold_date = int((date.today() - timedelta(weeks=weeks_back)).strftime("%Y%m%d"))

    try:
        rows = (
            Agenda.query
            .filter(Agenda.meeting_type.ilike("%City Council%"))
            .filter(Agenda.county.ilike(f"%{county_name}%"))
            .filter(Agenda.date >= threshold_date)
            .filter(Agenda.description.isnot(None))
            .filter(db.func.length(db.func.trim(Agenda.description)) > 5)
            .filter(~Agenda.description.ilike("%minute%"))
            .filter(~Agenda.description.ilike("%warrant%"))
            .order_by(Agenda.date.desc())
            .all()
        )

        return [
            {
                "County": item.county,
                "City": item.city,
                "Date": item.date,
                "Num": item.num,
                "MeetingType": item.meeting_type,
                "ItemType": item.item_type,
                "Description": item.description,
            }
            for item in rows
        ]

    except Exception:
        logger.exception("Failed to fetch agendas for county %s", county_name)
        return []



# =============================================================================
# CITY DATA BY COUNTY
# =============================================================================
# Comprehensive city lists organized by county
CITIES = {
    'LA': [
        'Agoura Hills', 'Alhambra', 'Arcadia', 'Artesia', 'Azusa', 'Baldwin Park', 'Bell',
        'Bellflower', 'Bell Gardens', 'Beverly Hills', 'Bradbury', 'Burbank', 'Calabasas',
        'Carson', 'Cerritos', 'City of Industry', 'Claremont', 'Commerce', 'Compton',
        'Covina', 'Cudahy', 'Culver City', 'Diamond Bar', 'Downey', 'Duarte', 'El Monte',
        'El Segundo', 'Gardena', 'Glendale', 'Glendora', 'Hawaiian Gardens', 'Hawthorne',
        'Hermosa Beach', 'Hidden Hills', 'Huntington Park', 'Inglewood', 'Irwindale',
        'La Canada Flintridge', 'La Habra Heights', 'La Mirada', 'La Puente', 'La Verne',
        'Lakewood', 'Lancaster', 'Lawndale', 'Lomita', 'Long Beach', 'Los Angeles',
        'Lynwood', 'Malibu', 'Manhattan Beach', 'Maywood', 'Monrovia', 'Montebello',
        'Monterey Park', 'Norwalk', 'Palmdale', 'Palos Verdes Estates', 'Paramount',
        'Pasadena', 'Pico Rivera', 'Pomona', 'Rancho Palos Verdes', 'Redondo Beach',
        'Rolling Hills', 'Rolling Hills Estates', 'Rosemead', 'South Pasadena',
        'San Dimas', 'San Fernando', 'San Gabriel', 'San Marino', 'Santa Clarita',
        'Santa Fe Springs', 'Santa Monica', 'Sierra Madre', 'Signal Hill', 'South El Monte',
        'South Gate', 'Temple City', 'Torrance', 'Vernon', 'Walnut', 'West Covina',
        'West Hollywood', 'Westlake Village', 'Whittier'
    ],
    'OC': [
        'Aliso Viejo', 'Anaheim', 'Brea', 'Buena Park', 'Costa Mesa', 'Cypress', 'Dana Point',
        'Fountain Valley', 'Fullerton', 'Garden Grove', 'Huntington Beach', 'Irvine', 
        'La Habra', 'La Palma', 'Laguna Beach', 'Laguna Hills', 'Laguna Niguel', 
        'Laguna Woods', 'Lake Forest', 'Los Alamitos', 'Mission Viejo', 'Newport Beach', 
        'Orange', 'Placentia', 'Rancho Santa Margarita', 'San Clemente', 'San Juan Capistrano', 
        'Santa Ana', 'Seal Beach', 'Stanton', 'Tustin', 'Villa Park', 'Westminster', 'Yorba Linda'
    ],
    'RS': [
        'Banning', 'Beaumont', 'Blythe', 'Calimesa', 'Canyon Lake', 'Cathedral City', 
        'Coachella', 'Corona', 'Desert Hot Springs', 'Eastvale', 'Hemet', 'Indian Wells', 
        'Indio', 'Jurupa Valley', 'Lake Elsinore', 'La Quinta', 'Menifee', 'Moreno Valley', 
        'Murrieta', 'Norco', 'Palm Desert', 'Palm Springs', 'Perris', 'Rancho Mirage', 
        'Riverside', 'San Jacinto', 'Temecula', 'Wildomar'
    ],
    'SB': [
        'Adelanto', 'Apple Valley', 'Barstow', 'Big Bear Lake', 'Chino', 'Chino Hills',
        'Colton', 'Fontana', 'Grand Terrace', 'Hesperia', 'Highland', 'Loma Linda',
        'Montclair', 'Needles', 'Ontario', 'Rancho Cucamonga', 'Redlands', 'Rialto',
        'San Bernardino', 'Twentynine Palms', 'Upland', 'Victorville', 'Yucaipa', 'Yucca Valley'
    ],
    'SD': [
        'Carlsbad', 'Chula Vista', 'Coronado', 'Del Mar', 'El Cajon', 'Encinitas', 
        'Escondido', 'Imperial Beach', 'La Mesa', 'Lemon Grove', 'National City', 
        'Oceanside', 'Poway', 'San Diego', 'San Marcos', 'Santee', 'Solana Beach', 'Vista'
    ]
}

# Combined list of all cities for dropdowns
ALL_CITIES = [city for county_cities in CITIES.values() for city in county_cities]

# =============================================================================
# REQUEST HOOKS (BEFORE-REQUEST)
# =============================================================================
@app.before_request
def log_requests():
    pass

@app.before_request
def refresh_subscription_status():
    """Keep the session's subscription flag in sync with the database."""
    if request.path.startswith('/static/'):
        return

    username = session.get("username")
    if not username:
        return

    user = User.query.filter_by(username=username).first()
    if user:
        session["subscribed"] = bool(user.subscription_active)


# =============================================================================
# SEO & SITE-LEVEL ROUTES (sitemap, robots, favicon, redirects)
# =============================================================================
SITEMAP_SIZE = 50000
SITEMAP_CACHE_TTL = 24 * 60 * 60  # regenerate sitemaps at most once per day
SITEMAP_DAYS = 180                # only include the last 6 months of items

_sitemap_cache = {}  # key -> (generated_at, xml)


def _sitemap_cutoff():
    """YYYYMMDD cutoff: only items from the last 6 months."""
    return int((date.today() - timedelta(days=SITEMAP_DAYS)).strftime('%Y%m%d'))


def _cached_sitemap(key, builder):
    """Return cached XML if fresh, otherwise rebuild (and cache valid pages)."""
    now = time.time()
    entry = _sitemap_cache.get(key)
    if entry and now - entry[0] < SITEMAP_CACHE_TTL:
        return entry[1]

    result = builder()
    if result is not None:
        _sitemap_cache[key] = (now, result)
    return result


@app.route('/sitemap.xml')
def sitemap_index():
    def build():
        total = (
            db.session.query(db.func.count(Agenda.id))
            .filter(Agenda.date >= _sitemap_cutoff())
            .scalar()
        )
        sitemap_count = max(1, math.ceil(total / SITEMAP_SIZE))

        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        ]
        for page in range(1, sitemap_count + 1):
            xml.append(
                '<sitemap>'
                f'<loc>{url_for("sitemap_page", page=page, _external=True)}</loc>'
                '</sitemap>'
            )
        xml.append('</sitemapindex>')
        return ''.join(xml)

    return Response(_cached_sitemap('index', build), mimetype='application/xml')


@app.route('/sitemap-<int:page>.xml')
def sitemap_page(page):
    def build():
        total = (
            db.session.query(db.func.count(Agenda.id))
            .filter(Agenda.date >= _sitemap_cutoff())
            .scalar()
        )
        sitemap_count = max(1, math.ceil(total / SITEMAP_SIZE))
        if page < 1 or page > sitemap_count:
            return None  # 404, not cached

        items = (
            Agenda.query
            .with_entities(Agenda.id)
            .filter(Agenda.date >= _sitemap_cutoff())
            .order_by(Agenda.id.asc())
            .offset((page - 1) * SITEMAP_SIZE)
            .limit(SITEMAP_SIZE)
            .all()
        )

        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        ]
        for item in items:
            xml.append(
                '<url>'
                f'<loc>{url_for("agenda_item", item_id=item.id, _external=True)}</loc>'
                '</url>'
            )
        xml.append('</urlset>')
        return ''.join(xml)

    xml = _cached_sitemap(f'page-{page}', build)
    if xml is None:
        return Response("Sitemap not found", status=404)
    return Response(xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engines"""
    return send_from_directory(app.static_folder, 'robots.txt')

# =============================================================================
# Image
# =============================================================================
@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    return send_from_directory(
        app.static_folder, 
        'favicon.ico', 
        mimetype='image/vnd.microsoft.icon'
    )

# =============================================================================
# HOMEPAGE
# =============================================================================
@app.route('/')
def httpsroute():
    """Redirect root to HTTPS index page"""
    return redirect("https://www.policyedge.net/index", code=301)

@app.route('/index', methods=['GET', 'POST'])
def index():
    form = chartForm()

    table_start = int((date.today() - timedelta(days=7)).strftime("%Y%m%d"))
    table_end = int((date.today() + timedelta(days=7)).strftime("%Y%m%d"))

    if request.method == 'POST' and request.form.get('chartSearch'):
        search_term = request.form['chartSearch'].strip()
        chosen = search_term
    else:
        chosen = 'cannabis'

    # TABLES: no chosen word, just date window
    table_query = (
        Agenda.query
        .filter(Agenda.meeting_type.ilike("%City Council%"))
        .filter(Agenda.date >= table_start)
        .filter(Agenda.date <= table_end)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
        .filter(~Agenda.description.ilike("%minute%"))
        .filter(~Agenda.description.ilike("%warrant%"))
    )

    table_results = table_query.order_by(Agenda.date.desc()).all()

    agenda_items = [
        {
            "ID": item.id,
            "County": item.county,
            "City": item.city,
            "Date": item.date,
            "Num": item.num,
            "MeetingType": item.meeting_type,
            "ItemType": item.item_type,
            "Description": item.description,
        }
        for item in table_results
    ]

    city_agendas = {}
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}
        city_agendas[city]["agendas"].append(agenda)

    initial_cities = dict(list(city_agendas.items())[:6])
    # MAP: chosen word only
    map_query = (
        Agenda.query
        .filter(Agenda.meeting_type.ilike("%City Council%"))
        .filter(Agenda.date >= table_start)
        .filter(Agenda.date <= table_end)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
    )

    if request.method == 'POST' and request.form.get('chartSearch'):
        search_term = request.form['chartSearch'].strip()
        chosen = search_term
    else:
        chosen = 'cannabis'

    map_query = (
        Agenda.query
        .filter(Agenda.meeting_type.ilike("%City Council%"))
        .filter(Agenda.date >= table_start)
        .filter(Agenda.date <= table_end)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
        .filter(Agenda.search_vector.op('@@')(db.func.plainto_tsquery('english', chosen)))
        .filter(~Agenda.description.ilike("%minute%"))
        .filter(~Agenda.description.ilike("%warrant%"))
    )

    map_results = map_query.order_by(Agenda.date.desc()).all()

    folium_agendas = {}
    cities_matched = []

    for item in map_results:
        city = item.city
        if not city:
            continue

        if city not in folium_agendas:
            folium_agendas[city] = {"agendas": []}

        folium_agendas[city]["agendas"].append({
            "County": item.county,
            "City": item.city,
            "Date": item.date,
            "Num": item.num,
            "MeetingType": item.meeting_type,
            "ItemType": item.item_type,
            "Description": item.description,
        })

        if chosen.lower() in (item.description or "").lower():
            cities_matched.append(city)

    city_issue_counts = Counter(cities_matched)
    geo_info = fetch_geo_info(db, GeoLocation, city_issue_counts)
    folium_map = create_folium_map(geo_info, folium_agendas)

    num_agenda_items = sum(len(data["agendas"]) for data in folium_agendas.values())
    num_cities = len(set(cities_matched))

    return render_template(
        'index.html',
        folium_map=folium_map._repr_html_(),
        num_agenda_items=num_agenda_items,
        num_cities=num_cities,
        form=form,
        city_agendas=initial_cities,
        title="California City Council Agendas | PolicyEdge",
        chosen=chosen
    )

# =============================================================================
# SEARCH, RESULTS & AGENDA ITEM PAGES
# =============================================================================
@app.route('/search')
def search():
    """Search page for agenda items"""
    form = searchForm()
    return render_template('search.html', form=form, title='Search California Government Agendas | PolicyEdge')

@app.route('/results', methods=['GET', 'POST'])
def results():
    if request.method == 'POST':
        data = request.form
    else:
        data = request.args

    form = searchForm(data)

    primeKey = (data.get('primary_search') or '').strip()
    start_date = form.startdate_field.data
    end_date = form.enddate_field.data

    start = int(start_date.strftime("%Y%m%d")) if start_date else get_date_threshold(weeks=-52)
    end = int(end_date.strftime("%Y%m%d")) if end_date else int(date.today().strftime("%Y%m%d"))
    criteria = form.select.data

    # Agenda.date is stored as an integer in YYYYMMDD format

    query = (
        Agenda.query
        .filter(Agenda.date >= start)
        .filter(Agenda.date <= end)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
    )

    if primeKey:
        query = query.filter(
            Agenda.search_vector.op('@@')(
                db.func.plainto_tsquery('english', primeKey)
            )
        )

    county_names = [
        'LA County',
        'Orange County',
        'Riverside County',
        'San Diego County',
        'San Bernardino County'
    ]

    if criteria in county_names:
        query = query.filter(
            Agenda.county.ilike(f"%{criteria}%")
        )

        city_field_map = {
            'LA County': 'selectLA',
            'Orange County': 'selectOC',
            'Riverside County': 'selectRS',
            'San Bernardino County': 'selectSB',
            'San Diego County': 'selectSD'
        }

        selected_city_field = city_field_map.get(criteria)

        if selected_city_field:
            selected_city = getattr(form, selected_city_field).data
            if selected_city:
                query = query.filter(
                    Agenda.city.ilike(f"%{selected_city}%")
                )

    elif criteria in ['LA Committees', 'Long Beach Committees']:
        query = query.filter(
            Agenda.county.ilike("%LA County%")
        )

        committee_field = (
            'selectLACM'
            if criteria == 'LA Committees'
            else 'selectLBCM'
        )

        selected_committee = getattr(form, committee_field).data

        if selected_committee:
            query = query.filter(
                Agenda.meeting_type.ilike(f"%{selected_committee}%")
            )

    # Tracked-issue card links pass city/county/committee directly
    card_city = (data.get('city') or '').strip()
    card_county = (data.get('county') or '').strip()
    card_committee = (data.get('committee') or '').strip()

    if card_county:
        query = query.filter(Agenda.county.ilike(f"%{card_county}%"))
    if card_city:
        query = query.filter(Agenda.city.ilike(f"%{card_city}%"))
    if card_committee:
        query = query.filter(Agenda.meeting_type.ilike(f"%{card_committee}%"))

    results_rows = (
        query
        .order_by(Agenda.date.desc())
        .limit(300)
        .all()
    )

    agenda_list = [
        {
            "ID": item.id,
            "County": item.county,
            "City": item.city,
            "Date": item.date,
            "Num": item.num,
            "MeetingType": item.meeting_type,
            "ItemType": item.item_type,
            "Description": item.description,
        }
        for item in results_rows
    ]

    cities_matched = []
    city_agendas = {}

    for agenda in agenda_list:
        city = agenda.get('City', '')
        description = agenda.get('Description', '')

        if not city:
            continue

        if city not in city_agendas:
            city_agendas[city] = {
                "agendas": [],
            }

        city_agendas[city]["agendas"].append(agenda)

        if not primeKey or primeKey.lower() in description.lower():
            cities_matched.append(city)

    initial_cities = dict(
        list(city_agendas.items())[:6]
    )

    city_issue_counts = Counter(cities_matched)

    geo_info = fetch_geo_info(
        db,
        GeoLocation,
        city_issue_counts
    )

    folium_map = create_folium_map(
        geo_info,
        city_agendas
    )

    return render_template(
        'search.html',
        folium_map=folium_map._repr_html_(),
        primeKey=primeKey,
        city_issue_counts=city_issue_counts,
        city_agendas=initial_cities,
        form=form,
        agendas=agenda_list,
        title="Search California Government Agendas Results| PolicyEdge"
    )

@app.route('/item/<int:item_id>')
def agenda_item(item_id):
    item = Agenda.query.get_or_404(item_id)

    agendas = (
        Agenda.query
        .filter_by(city=item.city)
        .order_by(Agenda.date.desc())
        .limit(20)
        .all()
    )

    city_agendas = {
        item.city: {
            'agendas': agendas
        }
    }

    return render_template(
        'agenda_item.html',
        item=item,
        city_slug=slugify(item.city or ''),
        meeting_date=fmt_date_yyyy_mm_dd(item.date),
        city_agendas=city_agendas
    )

# =============================================================================
# LOAD-MORE ENDPOINTS (INFINITE SCROLL)
# =============================================================================
@app.route('/load_more_cities_index')
def load_more_cities_index():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))

    table_start = int((date.today() - timedelta(days=7)).strftime("%Y%m%d"))
    table_end = int((date.today() + timedelta(days=7)).strftime("%Y%m%d"))

    city_agendas = {}

    rows = (
        Agenda.query
        .filter(Agenda.meeting_type.ilike("%City Council%"))
        .filter(Agenda.date >= table_start)
        .filter(Agenda.date <= table_end)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
        .filter(~Agenda.description.ilike("%minute%"))
        .filter(~Agenda.description.ilike("%warrant%"))
        .order_by(Agenda.date.desc())
        .all()
    )

    agenda_list = [
        {
            "ID": item.id,
            "County": item.county,
            "City": item.city,
            "Date": item.date,
            "Num": item.num,
            "MeetingType": item.meeting_type,
            "ItemType": item.item_type,
            "Description": item.description,
        }
        for item in rows
    ]

    for agenda in agenda_list:
        city = agenda.get('City', '')

        if not city:
            continue

        if city not in city_agendas:
            city_agendas[city] = {
                "agendas": [],
            }

        city_agendas[city]["agendas"].append(agenda)

    cities_list = list(city_agendas.items())
    cities_to_load = dict(cities_list[start:start + count])

    rendered = ""
    for city, data in cities_to_load.items():
        rendered += render_template(
            'partials/city_table_wrapper.html',
            _city=city,
            _data=data
        )

    return rendered

@app.route('/load_more_cities_results')
def load_more_cities_results():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))

    primeKey = (request.args.get('primary_search') or '').strip()
    criteria = (request.args.get('select') or '').strip()
    selectLA = (request.args.get('selectLA') or '').strip()
    selectOC = (request.args.get('selectOC') or '').strip()
    selectRS = (request.args.get('selectRS') or '').strip()
    selectSB = (request.args.get('selectSB') or '').strip()
    selectSD = (request.args.get('selectSD') or '').strip()
    selectLACM = (request.args.get('selectLACM') or '').strip()
    selectLBCM = (request.args.get('selectLBCM') or '').strip()
    city = (request.args.get('city') or '').strip()
    county = (request.args.get('county') or '').strip()
    committee = (request.args.get('committee') or '').strip()

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date:
        start_date = int(start_date.replace('-', ''))
    else:
        start_date = get_date_threshold(weeks=-52)

    if end_date:
        end_date = int(end_date.replace('-', ''))
    else:
        end_date = int(date.today().strftime("%Y%m%d"))

    query = (
        Agenda.query
        .filter(Agenda.date >= start_date)
        .filter(Agenda.date <= end_date)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
    )

    if primeKey:
        query = query.filter(
            Agenda.search_vector.op('@@')(
                db.func.plainto_tsquery('english', primeKey)
            )
        )

    county_names = [
        'LA County',
        'Orange County',
        'Riverside County',
        'San Diego County',
        'San Bernardino County'
    ]

    if criteria in county_names:
        query = query.filter(Agenda.county.ilike(f"%{criteria}%"))

        city_field_map = {
            'LA County': selectLA,
            'Orange County': selectOC,
            'Riverside County': selectRS,
            'San Bernardino County': selectSB,
            'San Diego County': selectSD
        }

        selected_city = city_field_map.get(criteria)
        if selected_city:
            query = query.filter(Agenda.city.ilike(f"%{selected_city}%"))

    elif criteria in ['LA Committees', 'Long Beach Committees']:
        query = query.filter(Agenda.county.ilike("%LA County%"))

        selected_committee = selectLACM if criteria == 'LA Committees' else selectLBCM
        if selected_committee:
            query = query.filter(Agenda.meeting_type.ilike(f"%{selected_committee}%"))

    if county:
        query = query.filter(Agenda.county.ilike(f"%{county}%"))
    if city:
        query = query.filter(Agenda.city.ilike(f"%{city}%"))
    if committee:
        query = query.filter(Agenda.meeting_type.ilike(f"%{committee}%"))

    rows = query.order_by(Agenda.date.desc()).all()

    agenda_list = [
        {
            "ID": item.id,
            "County": item.county,
            "City": item.city,
            "Date": item.date,
            "Num": item.num,
            "MeetingType": item.meeting_type,
            "ItemType": item.item_type,
            "Description": item.description,
        }
        for item in rows
    ]

    city_agendas = {}

    for agenda in agenda_list:
        city = agenda.get('City', '')
        if not city:
            continue

        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}

        city_agendas[city]["agendas"].append(agenda)

    cities_list = list(city_agendas.items())
    cities_to_load = dict(cities_list[start:start + count])

    rendered = ""
    for city, data in cities_to_load.items():
        rendered += render_template(
            'partials/city_table_wrapper.html',
            _city=city,
            _data=data
        )

    return rendered

@app.route('/load_more_cities')
def load_more_cities():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))
    username = session.get('username')
    county_name = (request.args.get('county') or '').strip()

    if county_name:
        agenda_list = get_county_agendas(county_name)

    elif username:
        # User accounts and saved agendas remain in MongoDB for now
        agenda_list = get_user_saved_agendas(User, Agenda, username)

    else:
        rows = (
            Agenda.query
            .filter(Agenda.description.isnot(None))
            .filter(Agenda.description != "")
            .order_by(Agenda.date.desc())
            .limit(300)
            .all()
        )

        agenda_list = [
            {
                "ID": item.id,
                "County": item.county,
                "City": item.city,
                "Date": item.date,
                "Num": item.num,
                "MeetingType": item.meeting_type,
                "ItemType": item.item_type,
                "Description": item.description,
            }
            for item in rows
        ]

    city_agendas = {}
    for agenda in agenda_list:
        city = agenda.get('City', '')

        if not city:
            continue

        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}

        city_agendas[city]["agendas"].append(agenda)

    cities_list = list(city_agendas.items())
    cities_to_load = dict(cities_list[start:start + count])

    rendered = ""
    for city, data in cities_to_load.items():
        rendered += render_template(
            'partials/city_table_wrapper.html',
            _city=city,
            _data=data
        )

    return rendered

# =============================================================================
# AUTHENTICATION (register, login, Google, logout)
# =============================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if "username" in session or "email" in session:
        return redirect(url_for("index"))
    return render_template("register.html", title="Sign Up for PolicyEdge | Track California City Council Agendas")

@app.route('/createAccount', methods=['POST'])
def create_account():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password1 = request.form.get("password1", "")
    password2 = request.form.get("password2", "")

    errors = validate_registration(
        username,
        email,
        password1,
        password2
    )

    if errors:
        for error in errors:
            flash(error)
        return render_template("register.html", title="Sign Up for PolicyEdge | Track California City Council Agendas")

    password_hash = bcrypt.hashpw(
        password1.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        subscription_active=False,
        issues=[],
        agenda_unique_ids=[]
    )

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        app.logger.exception("Failed to create user: %s", error)
        flash("Unable to create your account. Please try again.")
        return render_template("register.html", title="Sign Up for PolicyEdge | Track California City Council Agendas")

    session["username"] = user.username
    session["email"] = user.email
    session["subscribed"] = False

    flash("Account created successfully.")
    return redirect(url_for("trackedIssues"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""

    if "username" in session or "email" in session:
        return redirect(url_for('index'))

    if request.method == "POST":
        identifier = (
            request.form.get("username") or ""
        ).strip()

        password = request.form.get("password") or ""

        if not identifier or not password:
            flash("Missing credentials")
            return redirect(url_for('login'))

        user = (
            User.query
            .filter(
                db.or_(
                    db.func.lower(User.email)
                    == identifier.lower(),

                    db.func.lower(User.username)
                    == identifier.lower()
                )
            )
            .first()
        )

        password_matches = (
            user is not None
            and bool(user.password_hash)
            and bcrypt.checkpw(
                password.encode("utf-8"),
                user.password_hash.encode("utf-8")
            )
        )

        if password_matches:
            session["username"] = user.username
            session["email"] = user.email
            session["subscribed"] = user.subscription_active

            flash("Login successful!")
            return redirect(url_for("index"))

        flash("Invalid login credentials")

    return render_template(
        "login.html",
        title="Log into PolicyEdge | Track California City Council Agendas"
    )

@app.route("/login/google")
def login_google():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo")

    if not userinfo:
        resp = google.get("https://openidconnect.googleapis.com/v1/userinfo")
        userinfo = resp.json()

    google_sub = userinfo.get("sub")
    email = (userinfo.get("email") or "").lower().strip()
    username = (userinfo.get("name") or "").strip()

    if not email:
        flash("Google login did not return an email address.")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()

    if user:
        user.google_sub = google_sub
        user.auth_provider = "google"
    else:
        base_username = username or email.split("@")[0]
        final_username = base_username

        existing_username = User.query.filter_by(username=final_username).first()
        if existing_username:
            final_username = f"{base_username}_{google_sub[:6]}"

        user = User(
            username=final_username,
            email=email,
            password_hash=None,
            google_sub=google_sub,
            auth_provider="google",
            subscription_active=False,
            issues=[],
            agenda_unique_ids=[]
        )
        db.session.add(user)

    db.session.commit()

    session["username"] = user.username
    session["email"] = user.email
    session["subscribed"] = user.subscription_active

    flash("Google login successful!")
    return redirect(url_for("index"))

@app.route('/logout')
def logout():
    """Log out user and clear session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect(url_for("index"))

@app.route('/subscription')
def get_index():
    """Subscription management page"""
    if "username" in session:
        return render_template('subscription.html', title='Subscribe to California Government Agenda Alerts | PolicyEdge')
    else:
        return redirect(url_for("login"))

# =============================================================================
# STRIPE PAYMENT ROUTES
# =============================================================================

@app.route('/create-checkout-session', methods=['POST'])
def route_create_checkout_session():
    username = session.get("username")

    if not username:
        flash("Please log in first.")
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()

    if not user:
        flash("User not found.")
        return redirect(url_for("login"))

    return create_checkout_session(
        user.email,
        your_domain=app.config["YOUR_DOMAIN"],
        existing_customer_id=user.stripe_customer_id
    )

@app.route('/create-portal-session', methods=['POST'])
def create_portal_session():
    username = session.get("username")

    if not username:
        flash("Please log in first.")
        return redirect(url_for("login"))

    user = User.query.filter_by(username=username).first()

    if not user:
        flash("User not found.")
        return redirect(url_for("login"))

    if not user.stripe_customer_id:
        flash("No billing account found yet.")
        return redirect(url_for("subscription"))

    portal_session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=url_for("index", _external=True)
    )

    return redirect(portal_session.url, code=303)


@csrf.exempt
@app.route('/webhook', methods=['POST'])
def route_webhook():
    return handle_webhook(request.data, request.headers)
# =============================================================================
# TRACKED ISSUES (SAVED SEARCHES & ALERTS)
# =============================================================================
@app.route('/trackedIssues', methods=['GET', 'POST'])
def trackedIssues():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))

    current_user = User.query.filter_by(username=username).first()
    if not current_user:
        session.clear()
        return redirect(url_for("login"))

    form = monitorListform()
    subscription_active = bool(current_user.subscription_active)
    free_limit = 3
    threshold_date = int((date.today() - timedelta(days=7)).strftime('%Y%m%d'))
    issues_with_counts = []

    for issue in current_user.issues or []:
        searchWord = (issue.get('searchWord') or '').strip()
        city = (issue.get('City') or '').strip()
        committee = (issue.get('Committee') or '').strip()
        county = (issue.get('County') or '').strip()

        query = (
            Agenda.query
            .filter(Agenda.date >= threshold_date)
            .filter(Agenda.description.isnot(None))
            .filter(Agenda.description != "")
        )

        if searchWord:
            query = query.filter(Agenda.description.ilike(f"%{searchWord}%"))

        if committee:
            query = query.filter(Agenda.meeting_type.ilike(f"%{committee}%"))

        if city:
            query = query.filter(Agenda.city.ilike(f"%{city}%"))

        if county:
            query = query.filter(Agenda.county.ilike(f"%{county}%"))

        item_count = query.count()

        issue_copy = dict(issue)
        issue_copy["item_count"] = item_count
        issues_with_counts.append(issue_copy)
    if request.method == 'POST':
        operation = request.form.get('action')

        if operation == 'Add' and not subscription_active and len(current_user.issues or []) >= free_limit:
            flash(f"Free accounts can follow up to {free_limit} topics. Upgrade to add more.")
        else:
            success = handle_issue_operation(
                db,
                User,
                username,
                request.form,
                operation,
                subscription_active=subscription_active,
                free_limit=free_limit
            )

            if not success:
                flash("Unable to update your saved issues.")

        return redirect(url_for("trackedIssues"))

        db.session.refresh(current_user)
        issues_placeholder = current_user.issues or []

    user_agendas = get_user_saved_agendas(User, Agenda, username)

    city_agendas_dict = {}
    for agenda in user_agendas:
        city = agenda.get("City", "")
        if city not in city_agendas_dict:
            city_agendas_dict[city] = {"agendas": []}
        city_agendas_dict[city]["agendas"].append(agenda)

    initial_cities = dict(list(city_agendas_dict.items())[:6])

    return render_template(
        'trackedIssues.html',
        issues_placeholders=issues_with_counts,
        form=form,
        city_agendas=initial_cities,
        title='Track California Government Issues | PolicyEdge',
        subscription_active=subscription_active,
        free_limit=free_limit
    )

# =============================================================================
# CITY & MEETING HIERARCHY PAGES
# =============================================================================
def slugify(name):
    """'Los Angeles' -> 'los-angeles'"""
    slug = name.lower().strip()
    parts = [p for p in re.split(r'[^a-z0-9]+', slug) if p]
    return '-'.join(parts)


def city_name_from_slug(slug):
    """Resolve a URL slug back to the real city name from the database."""
    names = db.session.query(Agenda.city).filter(Agenda.city.isnot(None)).distinct().all()
    for (name,) in names:
        if slugify(name) == slug:
            return name
    return None


def fmt_date_yyyy_mm_dd(date_int):
    """20260819 -> '2026-08-19'"""
    ds = str(date_int)
    if len(ds) != 8:
        return None
    return f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"


@app.route('/city/<slug>')
def city_page(slug):
    city = city_name_from_slug(slug)
    if not city:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = 20

    meeting_query = (
        db.session.query(
            Agenda.city,
            Agenda.date,
            Agenda.meeting_type,
            db.func.count(Agenda.id).label('item_count')
        )
        .filter(Agenda.city == city)
        .group_by(Agenda.city, Agenda.date, Agenda.meeting_type)
        .order_by(Agenda.date.desc(), Agenda.meeting_type.asc())
    )

    total = meeting_query.count()
    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, pages))

    rows = meeting_query.offset((page - 1) * per_page).limit(per_page).all()

    meetings = [
        {
            'date': fmt_date_yyyy_mm_dd(date_int),
            'date_display': int2date(date_int),
            'meeting_type': meeting_type,
            'item_count': item_count,
        }
        for city_name, date_int, meeting_type, item_count in rows
    ]

    pagination = {
        'page': page,
        'pages': pages,
        'has_prev': page > 1,
        'has_next': page < pages,
        'prev_num': page - 1,
        'next_num': page + 1,
    }

    return render_template(
        'city.html',
        city=city,
        slug=slug,
        meetings=meetings,
        pagination=pagination,
        title=f"{city} Government Agendas | PolicyEdge"
    )


@app.route('/city/<slug>/meeting/<meeting_date>')
def meeting_page(slug, meeting_date):
    city = city_name_from_slug(slug)
    if not city:
        abort(404)

    try:
        date_int = int(datetime.strptime(meeting_date, '%Y-%m-%d').strftime('%Y%m%d'))
    except ValueError:
        abort(404)

    items = (
        Agenda.query
        .filter(Agenda.city == city, Agenda.date == date_int)
        .order_by(Agenda.meeting_type, Agenda.item_type, Agenda.num)
        .all()
    )

    if not items:
        abort(404)

    # A single date can host multiple meeting types — group them
    grouped = {}

    for item in items:
        agenda_dict = {
            'ID': item.id,
            'Date': item.date,
            'ItemType': item.item_type,
            'Num': item.num,
            'Description': item.description,
            'County': item.county,
            'City': item.city,
            'MeetingType': item.meeting_type,
        }

        grouped.setdefault(
            item.meeting_type or 'General',
            []
        ).append(agenda_dict)

    return render_template(
        'meeting.html',
        city=city,
        slug=slug,
        meeting_date=meeting_date,
        grouped=grouped,
        title=f"{city} - {meeting_date} | PolicyEdge"
    )

# -------------------------------
# COUNTY ROUTES CONFIGURATION
# -------------------------------
# Map custom route keys to full county names
COUNTY_KEY_MAP = {
    "losangeles": "LA County",
    "orange": "Orange County",
    "riverside": "Riverside County",
    "sanbernardino": "San Bernardino County",
    "sandiego": "San Diego County",
}
# Build COUNTY_ROUTES dynamically using the map
COUNTY_ROUTES = {
    key: {
        "name": name,
        "template": "county.html",
        "title": f"PolicyEdge agenda tracking monitoring all of {name}"
    }
    for key, name in COUNTY_KEY_MAP.items()
}
# -------------------------------
# ROUTE FACTORY FOR COUNTIES
# -------------------------------
def render_county_agendas(county_key):
    county_info = COUNTY_ROUTES[county_key]
    # Fetch agendas dynamically for this county
    agenda_items = get_county_agendas(county_info["name"],)
    # Build city dictionary
    city_agendas = {}
    cities_matched = []

    for agenda in agenda_items:
        city = agenda.get("City", "")
        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}
        city_agendas[city]["agendas"].append(agenda)

    # Only show first 6 cities
    initial_cities = dict(list(city_agendas.items())[:6])

    return render_template(
        county_info["template"],
        city_agendas=initial_cities,
        title=county_info["title"],
        county_name=county_info["name"]
    )
# -------------------------------
# REGISTER COUNTY ROUTES
# -------------------------------
for route_name in COUNTY_ROUTES:
    # Use lambda with default argument to capture route_name correctly
    app.add_url_rule(
        f'/{route_name}',
        endpoint=route_name,
        view_func=lambda route_name=route_name: render_county_agendas(route_name)
    )
# =============================================================================
# TEMPLATE FILTERS
# =============================================================================
app.template_filter('aTime')(int2date)
# =============================================================================
# SCHEDULER CONFIGURATION
# =============================================================================
scheduler = None
if os.environ.get("RUN_EMAIL_SCHEDULER") == "1":
    scheduler = start_scheduler(app, User, Agenda, db)
# =============================================================================
# STATIC PAGES AND COUNTY-SPECIFIC ROUTES
# =============================================================================
app.register_blueprint(static_pages)
# =============================================================================
# ERROR HANDLERS
# =============================================================================
register_error_handlers(app)
# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'False') == 'True'

    app.run(debug=debug, host='0.0.0.0', port=port)

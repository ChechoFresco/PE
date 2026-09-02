

from flask_pymongo import PyMongo
from flask_compress import Compress
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, send_from_directory, Blueprint, abort, Response
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth
from itsdangerous import URLSafeTimedSerializer
from bson import ObjectId
from forms import searchForm, monitorListform, chartForm
import bcrypt
from datetime import date, datetime, timedelta
import os
import re
import logging
import math
import time
from collections import Counter
from flask_mail import Mail
from stripe_service import init as stripe_init, create_checkout_session, handle_webhook, get_user_stripe_customer, validate_registration
from helpers import (get_date_threshold, handle_issue_operation, get_user_saved_agendas, int2date, get_county_agendas,
                     make_unsubscribe_token, load_unsubscribe_token, to_table_agenda, to_item_dict)
from map_utils import fetch_geo_info, create_folium_map
from watcher import start_watcher
from static_routes import static_pages
from error_handlers import register_error_handlers
import stripe
from dotenv import load_dotenv
# =============================================================================
# INITIALIZATION AND CONFIGURATION
# =============================================================================
load_dotenv()

app = Flask(__name__)
Compress(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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
stripe_init(mongo)

# Constants
stripe_keys = {
    'secret_key': os.environ['SECRET_KEY'],
    'publishable_key': os.environ['PUBLISHABLE_KEY']
}
stripe.api_key = stripe_keys['secret_key']

# Unsubscribe tokens and sitemaps
UNSUBSCRIBE_SALT = "email-unsubscribe"
UNSUBSCRIBE_MAX_AGE = 365 * 24 * 3600  # unsubscribe links valid for a year
SITEMAP_SIZE = 50000
SITEMAP_CACHE_TTL = 24 * 60 * 60
SITEMAP_DAYS = 180
_sitemap_cache = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS AND CONFIGURATION DATA
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
# Stop bots
# =============================================================================
@app.before_request
def log_requests():
    if app.debug:
        return  # Skip in development

    # Static assets, metadata files, and local dev traffic don't count
    if (request.path.startswith('/static/')
            or request.path in ('/robots.txt', '/favicon.ico')
            or request.remote_addr in ('127.0.0.1', '::1')):
        return

    ip = request.remote_addr
    ua = request.headers.get("User-Agent")
    path = request.path
    ts = datetime.utcnow()

    mongo.db.RequestLogs.insert_one({
        "ip": ip,
        "user_agent": ua,
        "path": path,
        "timestamp": ts
    })

    one_min_ago = ts - timedelta(seconds=60)
    recent_count = mongo.db.RequestLogs.count_documents({
        "ip": ip,
        "timestamp": {"$gte": one_min_ago}
    })

    if recent_count > 60:
        abort(429)
# =============================================================================
# ROUTES
# =============================================================================
@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engines"""
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    return send_from_directory(
        app.static_folder, 
        'favicon.ico', 
        mimetype='image/vnd.microsoft.icon'
    )

@app.route('/')
def httpsroute():
    """Redirect root to HTTPS index page"""
    return redirect("https://www.policyedge.net/index", code=301)

@app.route('/index', methods=['GET', 'POST'])
def index():
    form = chartForm()

    table_start = int((date.today() - timedelta(days=7)).strftime("%Y%m%d"))
    table_end = int((date.today() + timedelta(days=7)).strftime("%Y%m%d"))

    if request.method == 'POST' and request.form.get('chartSearch', '').strip():
        search_term = request.form['chartSearch'].strip()
        chosen = search_term
    else:
        chosen = 'cannabis'

    # TABLES: no chosen word, just the recent date window
    table_query = {
        '$and': [
            {"MeetingType": {'$regex': "City Council", '$options': 'i'}},
            {'Date': {'$gte': table_start, '$lte': table_end}},
            {'Description': {'$nin': ["", None]}},
            {"Description": {'$not': {'$regex': "(minute|warrant)", '$options': 'i'}}}
        ]
    }
    table_results = list(mongo.db.Agenda.find(table_query).sort('Date', -1))
    agenda_items = [to_table_agenda(a) for a in table_results]

    city_agendas = {}
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}
        city_agendas[city]["agendas"].append(agenda)

    initial_cities = dict(list(city_agendas.items())[:6])

    # MAP: chosen word only
    map_query = {
        '$and': [
            {"MeetingType": {'$regex': "City Council", '$options': 'i'}},
            {'Date': {'$gte': table_start, '$lte': table_end}},
            {'Description': {'$nin': ["", None]}},
            {'Description': {'$regex': re.escape(chosen), '$options': 'i'}},
            {"Description": {'$not': {'$regex': "(minute|warrant)", '$options': 'i'}}}
        ]
    }
    map_results = list(mongo.db.Agenda.find(map_query).sort('Date', -1))

    folium_agendas = {}
    cities_matched = []

    for item in map_results:
        city = item.get('City') or ''
        if not city:
            continue

        if city not in folium_agendas:
            folium_agendas[city] = {"agendas": []}
        folium_agendas[city]["agendas"].append(to_table_agenda(item))

        if chosen.lower() in (item.get('Description') or '').lower():
            cities_matched.append(city)

    city_issue_counts = Counter(cities_matched)
    geo_info = fetch_geo_info(mongo, city_issue_counts)
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

@app.route('/search')
def search():
    """Search page for agenda items"""
    form = searchForm()
    return render_template('search.html', form=form, title='Search')

@app.route('/results', methods=['GET', 'POST'])
def results():
    """Handle search form submission and display results"""
    data = request.form if request.method == 'POST' else request.args
    form = searchForm(data)

    primeKey = (data.get('primary_search') or '').strip()
    if request.method == 'POST' and not primeKey:
        flash('Please enter a keyword to search.')
        return render_template('search.html', form=form, title="PolicyEdge Search")

    start_date = form.startdate_field.data
    end_date = form.enddate_field.data
    start = int(start_date.strftime('%Y%m%d')) if start_date else get_date_threshold(weeks=-52)
    end = int(end_date.strftime('%Y%m%d')) if end_date else int(date.today().strftime('%Y%m%d'))

    # Empty source dropdown => keyword search across everything
    criteria = form.select.data or 'Issue'
    filters = [
        {'Description': {'$nin': ["", None]}},
        {'Date': {'$gte': start, '$lte': end}},
    ]
    if primeKey:
        filters.append({'Description': {'$regex': re.escape(primeKey), '$options': 'i'}})

    county_names = ['LA County', 'Orange County', 'Riverside County', 'San Diego County', 'San Bernardino County']
    if criteria in county_names:
        filters.append({'County': {'$regex': criteria, '$options': 'i'}})
        city_field_map = {
            'LA County': 'selectLA', 'Orange County': 'selectOC',
            'Riverside County': 'selectRS', 'San Bernardino County': 'selectSB',
            'San Diego County': 'selectSD'
        }
        selected_city_field = city_field_map.get(criteria)
        if selected_city_field:
            selected_city = getattr(form, selected_city_field).data
            if selected_city:
                filters.append({'City': {'$regex': selected_city, '$options': 'i'}})

    elif criteria in ['LA Committees', 'Long Beach Committees']:
        filters.append({'County': {'$regex': 'LA County', '$options': 'i'}})
        committee_field = 'selectLACM' if criteria == 'LA Committees' else 'selectLBCM'
        selected_committee = getattr(form, committee_field).data
        if selected_committee:
            filters.append({'MeetingType': {'$regex': selected_committee, '$options': 'i'}})

    # Tracked-issue card links pass city/county/committee directly
    card_city = (data.get('city') or '').strip()
    card_county = (data.get('county') or '').strip()
    card_committee = (data.get('committee') or '').strip()
    if card_county:
        filters.append({'County': {'$regex': card_county, '$options': 'i'}})
    if card_city:
        filters.append({'City': {'$regex': card_city, '$options': 'i'}})
    if card_committee:
        filters.append({'MeetingType': {'$regex': card_committee, '$options': 'i'}})

    # Execute search
    results_rows = list(mongo.db.Agenda.find({'$and': filters}).sort('Date', -1).limit(300))
    agenda_list = [to_table_agenda(a) for a in results_rows]

    cities_matched = []
    city_agendas = {}

    for agenda in agenda_list:
        city = agenda.get('City', '')
        description = agenda.get('Description', '')
        if not city:
            continue
        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}
        city_agendas[city]["agendas"].append(agenda)
        if not primeKey or primeKey.lower() in description.lower():
            cities_matched.append(city)

    initial_cities = dict(list(city_agendas.items())[:6])
    city_issue_counts = Counter(cities_matched)
    geo_info = fetch_geo_info(mongo, city_issue_counts)
    folium_map = create_folium_map(geo_info, city_agendas)

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

# ---------------------------
# Load more cities via AJAX
# ---------------------------
@app.route('/load_more_cities_index')
def load_more_cities_index():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))
    table_start = int((date.today() - timedelta(days=7)).strftime("%Y%m%d"))
    table_end = int((date.today() + timedelta(days=7)).strftime("%Y%m%d"))

    query = {
        '$and': [
            {"MeetingType": {'$regex': "City Council", '$options': 'i'}},
            {'Date': {'$gte': table_start, '$lte': table_end}},
            {'Description': {'$nin': ["", None]}},
            {"Description": {'$not': {'$regex': "(minute|warrant)", '$options': 'i'}}}
        ]
    }
    rows = list(mongo.db.Agenda.find(query).sort('Date', -1))
    agenda_list = [to_table_agenda(a) for a in rows]

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
        rendered += render_template('partials/city_table_wrapper.html', _city=city, _data=data)

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
        end_date = int(date.today().strftime('%Y%m%d'))

    filters = [
        {'Description': {'$nin': ["", None]}},
        {'Date': {'$gte': start_date, '$lte': end_date}},
    ]
    if primeKey:
        filters.append({'Description': {'$regex': re.escape(primeKey), '$options': 'i'}})

    county_names = ['LA County', 'Orange County', 'Riverside County', 'San Diego County', 'San Bernardino County']
    if criteria in county_names:
        filters.append({'County': {'$regex': criteria, '$options': 'i'}})
        city_field_map = {
            'LA County': selectLA, 'Orange County': selectOC,
            'Riverside County': selectRS, 'San Bernardino County': selectSB,
            'San Diego County': selectSD
        }
        selected_city = city_field_map.get(criteria)
        if selected_city:
            filters.append({'City': {'$regex': selected_city, '$options': 'i'}})
    elif criteria in ['LA Committees', 'Long Beach Committees']:
        filters.append({'County': {'$regex': 'LA County', '$options': 'i'}})
        selected_committee = selectLACM if criteria == 'LA Committees' else selectLBCM
        if selected_committee:
            filters.append({'MeetingType': {'$regex': selected_committee, '$options': 'i'}})

    if county:
        filters.append({'County': {'$regex': county, '$options': 'i'}})
    if city:
        filters.append({'City': {'$regex': city, '$options': 'i'}})
    if committee:
        filters.append({'MeetingType': {'$regex': committee, '$options': 'i'}})

    rows = list(mongo.db.Agenda.find({'$and': filters}).sort('Date', -1))
    agenda_list = [to_table_agenda(a) for a in rows]

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
        rendered += render_template('partials/city_table_wrapper.html', _city=city, _data=data)

    return rendered


@app.route('/load_more_cities')
def load_more_cities():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))
    username = session.get('username')
    county_name = (request.args.get('county') or '').strip()

    if county_name:
        agenda_list = get_county_agendas(mongo, county_name)
    elif username:
        agenda_list = get_user_saved_agendas(mongo, username)
    else:
        agenda_list = list(mongo.db.Agenda.find(
            {'Description': {'$nin': ["", None]}}
        ).sort('Date', -1).limit(300))

    agenda_list = [to_table_agenda(a) for a in agenda_list]
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
        rendered += render_template('partials/city_table_wrapper.html', _city=city, _data=data)

    return rendered

# =============================================================================
# Resgister Login
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

    errors = validate_registration(username, email, password1, password2)
    if errors:
        for error in errors:
            flash(error)
        return render_template("register.html", title="Sign Up for PolicyEdge | Track California City Council Agendas")

    hashed = bcrypt.hashpw(password1.encode("utf-8"), bcrypt.gensalt())
    mongo.db.User.insert_one({
        'username': username,
        'email': email,
        'password': hashed,
        'stripe_customer_id': None,
        'stripe_subscription_id': None,
        'subscriptionActive': False,
        'email_alerts_enabled': True,
        'issues': [],
        'agendaUnique_id': []
    })

    session["username"] = username
    session["email"] = email
    session["subscribed"] = False
    flash("Account created successfully.")
    return redirect(url_for("trackedIssues"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if "username" in session or "email" in session:
        return redirect(url_for('index'))

    if request.method == "POST":
        identifier = request.form.get("username")  # can be email OR username
        password = request.form.get("password")

        if not identifier or not password:
            flash("Missing credentials")
            return redirect(url_for('login'))

        user = mongo.db.User.find_one({
            "$or": [
                {"email": identifier},
                {"username": identifier}
            ]
        })

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            session['username'] = user["username"]
            session['email'] = user["email"]
            session['subscribed'] = user.get("subscriptionActive", False)
            flash('Login successful!')
            return redirect(url_for('index'))
        else:
            flash('Invalid login credentials')
    return render_template('login.html', title="Log into PolicyEdge | Track California City Council Agendas")


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
    name = (userinfo.get("name") or "").strip()

    if not email:
        flash("Google login did not return an email address.")
        return redirect(url_for("login"))

    user = mongo.db.User.find_one({"email": email})
    if user:
        mongo.db.User.update_one(
            {"_id": user["_id"]},
            {"$set": {"google_sub": google_sub, "auth_provider": "google"}}
        )
        username = user["username"]
        subscribed = bool(user.get("subscriptionActive", False))
    else:
        base_username = name or email.split("@")[0]
        final_username = base_username
        if mongo.db.User.find_one({"username": final_username}):
            final_username = f"{base_username}_{google_sub[:6]}"
        username = final_username
        subscribed = False
        mongo.db.User.insert_one({
            'username': username,
            'email': email,
            'password': None,
            'google_sub': google_sub,
            'auth_provider': "google",
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
            'subscriptionActive': False,
            'email_alerts_enabled': True,
            'issues': [],
            'agendaUnique_id': []
        })

    session["username"] = username
    session["email"] = email
    session["subscribed"] = subscribed
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
    if "username" in session or "email" in session:
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

    user = mongo.db.User.find_one({"username": username})
    if not user:
        flash("User not found.")
        return redirect(url_for("login"))

    return create_checkout_session(
        user["email"],
        your_domain=app.config["YOUR_DOMAIN"],
        existing_customer_id=user.get("stripe_customer_id")
    )


@app.route('/create-portal-session', methods=['POST'])
def create_portal_session():
    username = session.get("username")
    if not username:
        flash("Please log in first.")
        return redirect(url_for("login"))

    user = mongo.db.User.find_one({"username": username})
    if not user:
        flash("User not found.")
        return redirect(url_for("login"))

    if not user.get("stripe_customer_id"):
        flash("No billing account found yet.")
        return redirect(url_for("subscription"))

    portal_session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=url_for("index", _external=True)
    )
    return redirect(portal_session.url, code=303)


@csrf.exempt
@app.route('/webhook', methods=['POST'])
def route_webhook():
    return handle_webhook(request.data, request.headers)
# =============================================================================
# SEARCH AND AGENDA ROUTES
# =============================================================================
@app.route('/trackedIssues', methods=['GET', 'POST'])
def trackedIssues():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))

    current_user = mongo.db.User.find_one({"username": username})
    if not current_user:
        session.clear()
        return redirect(url_for("login"))

    form = monitorListform()
    subscription_active = bool(current_user.get("subscriptionActive", False))
    free_limit = 3
    threshold_date = int((date.today() - timedelta(days=7)).strftime('%Y%m%d'))
    issues_with_counts = []

    for issue in current_user.get("issues", []) or []:
        searchWord = (issue.get('searchWord') or '').strip()
        city = (issue.get('City') or '').strip()
        committee = (issue.get('Committee') or '').strip()
        county = (issue.get('County') or '').strip()

        filters = [
            {'Date': {'$gte': threshold_date}},
            {'Description': {'$nin': ["", None]}},
        ]
        if searchWord:
            filters.append({'Description': {'$regex': re.escape(searchWord), '$options': 'i'}})
        if committee:
            filters.append({'MeetingType': {'$regex': re.escape(committee), '$options': 'i'}})
        if city:
            filters.append({'City': {'$regex': re.escape(city), '$options': 'i'}})
        if county:
            filters.append({'County': {'$regex': re.escape(county), '$options': 'i'}})

        item_count = mongo.db.Agenda.count_documents({'$and': filters})
        issue_copy = dict(issue)
        issue_copy["item_count"] = item_count
        issues_with_counts.append(issue_copy)

    if request.method == 'POST':
        operation = request.form.get('action')
        if operation == 'Add' and not subscription_active and len(current_user.get("issues", []) or []) >= free_limit:
            flash(f"Free accounts can follow up to {free_limit} topics. Upgrade to add more.")
        else:
            handle_issue_operation(mongo, username, request.form, operation)
        return redirect(url_for("trackedIssues"))

    user_agendas = get_user_saved_agendas(mongo, username)
    city_agendas_dict = {}
    for agenda in user_agendas:
        city = agenda.get('City', '')
        if city not in city_agendas_dict:
            city_agendas_dict[city] = {"agendas": []}
        city_agendas_dict[city]["agendas"].append(to_table_agenda(agenda))

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


@app.route('/savedIssues', methods=['GET', 'POST'])
def savedIssues():
    """Old route kept for bookmarks; redirect to tracked issues."""
    return redirect(url_for("trackedIssues"))
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
    agenda_items = get_county_agendas(mongo, county_info["name"])
    # Build city dictionary
    city_agendas = {}

    for agenda in agenda_items:
        city = agenda.get("City", "")
        if city not in city_agendas:
            city_agendas[city] = {"agendas": []}
        city_agendas[city]["agendas"].append(to_table_agenda(agenda))
    # Only show first 6 cities
    initial_cities = dict(list(city_agendas.items())[:6])

    return render_template(
        county_info["template"],
        city_agendas=initial_cities,
        title=county_info["title"],
        county_name=county_info["name"]
    )

# =============================================================================
# EMAIL UNSUBSCRIBE
# =============================================================================
@app.route('/unsubscribe/<token>', methods=['GET', 'POST'])
@csrf.exempt
def unsubscribe(token):
    try:
        email = load_unsubscribe_token(app.secret_key, token, max_age_days=365)
    except Exception:
        return render_template(
            'unsubscribe.html',
            valid=False,
            title='Unsubscribe | PolicyEdge'
        ), 404

    user = mongo.db.User.find_one({"email": email})
    if user:
        mongo.db.User.update_one(
            {"_id": user["_id"]},
            {"$set": {"email_alerts_enabled": False}}
        )

    if request.method == 'POST':  # Gmail/Yahoo one-click
        return Response("Unsubscribed", status=200)

    return render_template(
        'unsubscribe.html',
        valid=True,
        email=email if user else None,
        title='Unsubscribe | PolicyEdge'
    )

# =============================================================================
# CITY & MEETING HIERARCHY PAGES
# =============================================================================
def slugify(name):
    """'Los Angeles' -> 'los-angeles'"""
    slug = (name or '').lower().strip()
    parts = [p for p in re.split(r'[^a-z0-9]+', slug) if p]
    return '-'.join(parts)


_city_slug_cache = {'ts': 0, 'map': {}}

def city_name_from_slug(slug):
    """Resolve a URL slug back to the real city name (cached for 10 min)."""
    now = time.time()
    if now - _city_slug_cache['ts'] > 600:
        names = mongo.db.Agenda.distinct("City", {"City": {"$nin": ["", None]}})
        _city_slug_cache['map'] = {slugify(n): n for n in names}
        _city_slug_cache['ts'] = now
    return _city_slug_cache['map'].get(slug)


def fmt_date_yyyy_mm_dd(date_int):
    """20260819 -> '2026-08-19'"""
    ds = str(date_int)
    if len(ds) != 8:
        return None
    return f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"


@app.route('/item/<item_id>')
def agenda_item(item_id):
    try:
        item = mongo.db.Agenda.find_one({"_id": ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        abort(404)

    city = item.get("City", "") or ""
    agendas = list(mongo.db.Agenda.find({"City": city}).sort("Date", -1).limit(20))
    city_agendas = {
        city: {
            'agendas': [to_table_agenda(a) for a in agendas]
        }
    }

    return render_template(
        'agenda_item.html',
        item=to_item_dict(item),
        city_slug=slugify(city),
        meeting_date=fmt_date_yyyy_mm_dd(item.get("Date")),
        city_agendas=city_agendas
    )


@app.route('/city/<slug>')
def city_page(slug):
    city = city_name_from_slug(slug)
    if not city:
        abort(404)

    page = request.args.get('page', 1, type=int)
    per_page = 20

    pipeline = [
        {"$match": {"City": city}},
        {"$group": {"_id": {"Date": "$Date", "MeetingType": "$MeetingType"}, "item_count": {"$sum": 1}}},
        {"$sort": {"_id.Date": -1, "_id.MeetingType": 1}},
    ]
    total = len(list(mongo.db.Agenda.aggregate(pipeline)))
    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, pages))

    rows = list(mongo.db.Agenda.aggregate(
        pipeline + [{"$skip": (page - 1) * per_page}, {"$limit": per_page}]
    ))

    meetings = [
        {
            'date': fmt_date_yyyy_mm_dd(row['_id']['Date']),
            'date_display': int2date(row['_id']['Date']),
            'meeting_type': row['_id']['MeetingType'],
            'item_count': row['item_count'],
        }
        for row in rows
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

    items = list(mongo.db.Agenda.find(
        {"City": city, "Date": date_int}
    ).sort([("MeetingType", 1), ("ItemType", 1), ("Num", 1)]))

    if not items:
        abort(404)

    grouped = {}
    for item in items:
        grouped.setdefault(item.get("MeetingType") or "General", []).append(to_table_agenda(item))

    return render_template(
        'meeting.html',
        city=city,
        slug=slug,
        meeting_date=meeting_date,
        grouped=grouped,
        title=f"{city} - {meeting_date} | PolicyEdge"
    )

# =============================================================================
# SITEMAP
# =============================================================================
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
        total = mongo.db.Agenda.count_documents({"Date": {"$gte": _sitemap_cutoff()}})
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
        total = mongo.db.Agenda.count_documents({"Date": {"$gte": _sitemap_cutoff()}})
        sitemap_count = max(1, math.ceil(total / SITEMAP_SIZE))
        if page < 1 or page > sitemap_count:
            return None  # 404, not cached

        items = list(mongo.db.Agenda.find(
            {"Date": {"$gte": _sitemap_cutoff()}}, {"_id": 1}
        ).sort("_id", 1).skip((page - 1) * SITEMAP_SIZE).limit(SITEMAP_SIZE))

        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        ]
        for item in items:
            xml.append(
                '<url>'
                f'<loc>{url_for("agenda_item", item_id=str(item["_id"]), _external=True)}</loc>'
                '</url>'
            )
        xml.append('</urlset>')
        return ''.join(xml)

    xml = _cached_sitemap(f'page-{page}', build)
    if xml is None:
        return Response("Sitemap not found", status=404)
    return Response(xml, mimetype='application/xml')

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
CAPS_ACRONYMS = {
    "ADU", "BMR", "CEQA", "LA", "LADWP", "LAPD", "LAFD", "PLUM",
    "SCE", "SB", "AB", "MOU", "RFP", "RFQ", "PSA", "CD", "FY", "DOT",
}

def soften_caps(text):
    """Title-case long ALL-CAPS words, keep real acronyms, lowercase short words."""
    def repl(match):
        word = match.group(0)
        upper = word.upper()
        if upper in CAPS_ACRONYMS:
            return word
        if word.isupper() and word.isalpha():
            if len(word) <= 3:
                return word.lower()
            return word.capitalize()
        return word
    return re.sub(r"[A-Za-z']+", repl, text or "")


app.template_filter('aTime')(int2date)
app.template_filter('soften_caps')(soften_caps)
# =============================================================================
# CHANGE-STREAM WATCHER (emails on new agenda inserts)
# =============================================================================
watcher = start_watcher(app, mongo, mail)
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

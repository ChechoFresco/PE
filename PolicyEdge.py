

from flask_pymongo import PyMongo
from flask_compress import Compress
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, send_from_directory, Blueprint, abort
from forms import searchForm, monitorListform, chartForm
import bcrypt
from datetime import date, datetime, timedelta
import os
import logging
from collections import Counter
from flask_mail import Mail
from stripe_service import init as stripe_init, create_checkout_session, handle_webhook, get_user_stripe_customer, validate_registration
from helpers import (get_date_threshold,handle_issue_operation,get_user_saved_agendas,int2date,)
from map_utils import fetch_geo_info, create_folium_map
from jobs import check4Issues2email, start_scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from static_routes import static_pages
from error_handlers import register_error_handlers
import stripe
from dotenv import load_dotenv

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
# =============================================================================
# INITIALIZATION AND CONFIGURATION
# =============================================================================
load_dotenv()

app = Flask(__name__)
Compress(app)

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

    id = db.Column(db.BigInteger, primary_key=True)
    county = db.Column(db.Text)
    city = db.Column(db.Text)
    date = db.Column(db.Integer)
    num = db.Column(db.Text)
    meeting_type = db.Column(db.Text)
    item_type = db.Column(db.Text)
    description = db.Column(db.Text)

class GeoLocation(db.Model):
    __tablename__ = "geoloc"

    mongo_id = db.Column("_id", db.Text, primary_key=True)
    city = db.Column(db.Text, nullable=False, index=True)
    state_id = db.Column(db.Text)
    county_name = db.Column(db.Text)
    latitude = db.Column("lat", db.Float)
    longitude = db.Column("lng", db.Float)
    website = db.Column("webadress", db.Text)

from sqlalchemy.dialects.postgresql import JSONB


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.Text, nullable=False, unique=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    stripe_customer_id = db.Column(db.Text)
    stripe_subscription_id = db.Column(db.Text)
    subscription_active = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    issues = db.Column(
        JSONB,
        nullable=False,
        default=list
    )
    agenda_unique_ids = db.Column(
        JSONB,
        nullable=False,
        default=list
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        nullable=False
    )


# Must be below the User class
stripe_init(db, User)

# -------------------------------
# HELPER: GET COUNTY AGENDAS
# -------------------------------
def get_county_agendas(county_name, weeks_back=16):
    """Return recent City Council agenda items for a county."""
    threshold_date = date.today() - timedelta(weeks=weeks_back)

    try:
        rows = (
            db.session.query(Agenda, Meeting, City, County)
            .join(Meeting, Agenda.meeting_id == Meeting.id)
            .join(City, Meeting.city_id == City.id)
            .join(County, City.county_id == County.id)
            .filter(Meeting.meeting_date >= threshold_date)
            .filter(Meeting.meeting_type.ilike("%City Council%"))
            .filter(County.name.ilike(f"%{county_name}%"))
            .filter(Agenda.description.isnot(None))
            .filter(db.func.length(db.func.trim(Agenda.description)) > 5)
            .filter(~Agenda.description.ilike("%minute%"))
            .filter(~Agenda.description.ilike("%warrant%"))
            .order_by(Meeting.meeting_date.desc())
            .all()
        )

        return [
            {
                "County": county.name,
                "City": city.name,
                "Date": int(meeting.meeting_date.strftime("%Y%m%d")),
                "Num": item.item_number,
                "MeetingType": meeting.meeting_type,
                "ItemType": item.item_type,
                "Description": item.description,
                "Topics": [],
            }
            for item, meeting, city, county in rows
        ]

    except Exception:
        logger.exception(
            "Failed to fetch agendas for county %s",
            county_name,
        )
        return []

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

@app.route("/pg-test")
def pg_test():
    count = db.session.execute(
        db.text('SELECT COUNT(*) FROM "Agendas"')
    ).scalar()

    return f"Postgres connected. Agendas: {count}"
# =============================================================================
# Stop bots
# =============================================================================
@app.before_request
def log_requests():
    pass
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
    date_threshold = get_date_threshold(weeks=-1)

    if request.method == 'POST' and request.form.get('chartSearch'):
        search_term = request.form['chartSearch'].strip()
        chosen = f'"{search_term}"'
        search_clean = search_term
    else:
        chosen = 'cannabis'
        search_clean = 'cannabis'

    query = (
        Agenda.query
        .filter(Agenda.meeting_type.ilike("%City Council%"))
        .filter(Agenda.date >= date_threshold)
        .filter(Agenda.description.isnot(None))
        .filter(Agenda.description != "")
    )

    if request.method == 'POST' and request.form.get('chartSearch'):
        query = query.filter(
            Agenda.description.ilike(f"%{search_clean}%")
        )
    else:
        query = query.filter(
            ~Agenda.description.ilike("%minute%"),
            ~Agenda.description.ilike("%warrant%")
        )

    results = query.order_by(Agenda.date.desc()).all()

    agenda_items = [
        {
            "County": item.county,
            "City": item.city,
            "Date": item.date,
            "Num": item.num,
            "MeetingType": item.meeting_type,
            "ItemType": item.item_type,
            "Description": item.description,
            "Topics": []
        }
        for item in results
    ]

    cities_matched = []
    city_agendas = {}
    folium_agendas = {}

    for agenda in agenda_items:
        city = agenda.get('City', '')
        description = agenda.get('Description', '')
        topics = agenda.get('Topics', [])

        if city not in city_agendas:
            city_agendas[city] = {
                "agendas": [],
                "topic_counts": Counter()
            }

        city_agendas[city]["agendas"].append(agenda)

        if isinstance(topics, list):
            city_agendas[city]["topic_counts"].update(topics)
        else:
            city_agendas[city]["topic_counts"].update([topics])

        if search_clean.lower() in description.lower():
            if city not in folium_agendas:
                folium_agendas[city] = {
                    "agendas": [],
                    "topic_counts": Counter()
                }

            folium_agendas[city]["agendas"].append(agenda)

            if isinstance(topics, list):
                folium_agendas[city]["topic_counts"].update(topics)
            else:
                folium_agendas[city]["topic_counts"].update([topics])

            cities_matched.append(city)

    initial_cities = dict(list(city_agendas.items())[:6])

    city_issue_counts = Counter(cities_matched)

    geo_info = fetch_geo_info(
        db,
        GeoLocation,
        city_issue_counts
    )

    folium_map = create_folium_map(
        geo_info,
        folium_agendas
    )

    num_agenda_items = sum(
        len(data["agendas"])
        for data in folium_agendas.values()
    )

    num_cities = len(set(cities_matched))

    return render_template(
        'index.html',
        folium_map=folium_map._repr_html_(),
        num_agenda_items=num_agenda_items,
        num_cities=num_cities,
        form=form,
        city_agendas=initial_cities,
        title="Policy Edge Tracking Agendas",
        chosen=chosen
    )

@app.route('/search')
def search():
    """Search page for agenda items"""
    form = searchForm()
    return render_template('search.html', form=form, title='Search')

@app.route('/results', methods=['GET', 'POST'])
def results():
    form = searchForm(request.form)

    if request.method == 'POST':
        primeKey = (form.primary_search.data or '').strip()
        start_date = form.startdate_field.data
        end_date = form.enddate_field.data
        criteria = form.select.data

        # Agenda.date is stored as an integer in YYYYMMDD format
        if start_date:
            start = int(start_date.strftime("%Y%m%d"))
        else:
            start = get_date_threshold(weeks=-52)

        if end_date:
            end = int(end_date.strftime("%Y%m%d"))
        else:
            end = int(date.today().strftime("%Y%m%d"))

        query = (
            Agenda.query
            .filter(Agenda.date >= start)
            .filter(Agenda.date <= end)
            .filter(Agenda.description.isnot(None))
            .filter(Agenda.description != "")
        )

        if primeKey:
            query = query.filter(
                Agenda.description.ilike(f"%{primeKey}%")
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
                selected_city = getattr(
                    form,
                    selected_city_field
                ).data

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

            selected_committee = getattr(
                form,
                committee_field
            ).data

            if selected_committee:
                query = query.filter(
                    Agenda.meeting_type.ilike(
                        f"%{selected_committee}%"
                    )
                )

        results_rows = (
            query
            .order_by(Agenda.date.desc())
            .limit(300)
            .all()
        )

        agenda_list = [
            {
                "County": item.county,
                "City": item.city,
                "Date": item.date,
                "Num": item.num,
                "MeetingType": item.meeting_type,
                "ItemType": item.item_type,
                "Description": item.description,
                "Topics": []
            }
            for item in results_rows
        ]

        cities_matched = []
        city_agendas = {}

        for agenda in agenda_list:
            city = agenda.get('City', '')
            description = agenda.get('Description', '')
            topics = agenda.get('Topics', [])

            if not city:
                continue

            if city not in city_agendas:
                city_agendas[city] = {
                    "agendas": [],
                    "topic_counts": Counter()
                }

            city_agendas[city]["agendas"].append(agenda)

            if isinstance(topics, list):
                city_agendas[city]["topic_counts"].update(topics)
            else:
                city_agendas[city]["topic_counts"].update([topics])

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
            title="PolicyEdge Search Results"
        )

    return render_template(
        'search.html',
        form=form,
        title="PolicyEdge Search"
    )

# ---------------------------
# Load more cities via AJAX
# ---------------------------
@app.route('/load_more_cities')
def load_more_cities():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))
    username = session.get('username')

    city_agendas = {}

    if username:
        # User accounts and saved agendas remain in MongoDB for now
        agenda_list = get_user_saved_agendas(mongo, username)

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
                "County": item.county,
                "City": item.city,
                "Date": item.date,
                "Num": item.num,
                "MeetingType": item.meeting_type,
                "ItemType": item.item_type,
                "Description": item.description,
                "Topics": []
            }
            for item in rows
        ]

    for agenda in agenda_list:
        city = agenda.get('City', '')
        topics = agenda.get('Topics', [])

        if not city:
            continue

        if city not in city_agendas:
            city_agendas[city] = {
                "agendas": [],
                "topic_counts": Counter()
            }

        city_agendas[city]["agendas"].append(agenda)

        if isinstance(topics, list):
            city_agendas[city]["topic_counts"].update(topics)
        else:
            city_agendas[city]["topic_counts"].update([topics])

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
# Resgister Login
# =============================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if "username" in session or "email" in session:
        return redirect(url_for("index"))
    return render_template("register.html", title="Register for PolicyEdge")

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
        title="Please Login"
    )

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
        return render_template('subscription.html', title='Re-subscribe to PolicyEdge')
    else:
        return redirect(url_for("login"))

# =============================================================================
# STRIPE PAYMENT ROUTES
# =============================================================================

@app.route(
    '/create-checkout-session',
    methods=['POST']
)
def route_create_checkout_session():
    username = request.form.get(
        "username",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password1 = request.form.get(
        "password1",
        ""
    )

    password2 = request.form.get(
        "password2",
        ""
    )

    errors = validate_registration(
        username,
        email,
        password1,
        password2
    )

    if errors:
        for error in errors:
            flash(error)

        return render_template(
            "register.html",
            title="Register for PolicyEdge"
        )

    password_hash = bcrypt.hashpw(
        password2.encode("utf-8"),
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

        app.logger.exception(
            "Failed to create user: %s",
            error
        )

        flash(
            "Unable to create your account. "
            "Please try again."
        )

        return render_template(
            "register.html",
            title="Register for PolicyEdge"
        )

    session["username"] = user.username
    session["email"] = user.email
    session["subscribed"] = False

    return create_checkout_session(
        user.email,
        your_domain=app.config["YOUR_DOMAIN"]
    )

@app.route('/webhook', methods=['POST'])
def route_webhook():
    env = os.environ.get("FLASK_ENV", "development")
    return handle_webhook(request.data, request.headers, your_domain=app.config['YOUR_DOMAIN'], env=env)
# =============================================================================
# SEARCH AND AGENDA ROUTES
# =============================================================================
@app.route('/savedIssues', methods=['GET', 'POST'])
def savedIssues():
    """Manage user's saved search issues and show matching agendas"""
    if "username" not in session:
        return redirect(url_for("login"))
        
    # Check if user has active subscription
    user_subscribed = mongo.db.User.find_one({
        'username': session['username'],
        'subscriptionActive': True
    })
    
    if not user_subscribed:
        return render_template('noSubscription.html')
    
    form = monitorListform()
    user = session["username"]
    
    if request.method == 'GET':
        # Get user's saved issues
        user_data = mongo.db.User.find_one(
            {'username': user}, 
            {'_id': 0, 'issues': 1}
        )
        issues_placeholder = user_data.get('issues', []) if user_data else []

        user_agendas = get_user_saved_agendas(mongo, user)  # returns list
        print(user_agendas)
        # Organize by city like search.html
        city_agendas_dict = {}
        for agenda in user_agendas:
            city = agenda.get('City', '')
            if city not in city_agendas_dict:
                city_agendas_dict[city] = {"agendas": []}
            city_agendas_dict[city]["agendas"].append(agenda)

        # Slice first 6 cities
        initial_cities = dict(list(city_agendas_dict.items())[:6])

        # Pass to template
        return render_template(
            'savedIssues.html',
            issues_placeholders=issues_placeholder,
            form=form,
            city_agendas=initial_cities,  # 🔹 now a dict, not a list
            title='Subscription List'
        )
    
    elif request.method == 'POST':
        # Handle add/delete operations for saved issues
        operation = request.form.get('action')
        handle_issue_operation(mongo, user, request.form, operation)
        
        # Refresh the page with updated data
        user_data = mongo.db.User.find_one(
            {'username': user}, 
            {'_id': 0, 'issues': 1}
        )
        issues_placeholder = user_data.get('issues', []) if user_data else []
        
        user_agendas = get_user_saved_agendas(mongo, user)  # returns list

        city_agendas_dict = {}
        for agenda in user_agendas:
            city = agenda.get('City', '')
            if city not in city_agendas_dict:
                city_agendas_dict[city] = {"agendas": []}
            city_agendas_dict[city]["agendas"].append(agenda)

                    # Slice first 6 cities
        initial_cities = dict(list(city_agendas_dict.items())[:6])

        return render_template(
            'savedIssues.html',
            issues_placeholders=issues_placeholder,
            form=form,
            city_agendas=initial_cities,
            title='Subscription List'
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
        topics = agenda.get("Topics", [])
        if city not in city_agendas:
            city_agendas[city] = {"agendas": [], "topic_counts": Counter()}
        city_agendas[city]["agendas"].append(agenda)
        if isinstance(topics, list):
            city_agendas[city]["topic_counts"].update(topics)
        else:
            city_agendas[city]["topic_counts"].update([topics])
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
#scheduler = start_scheduler(mongo, mail)
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
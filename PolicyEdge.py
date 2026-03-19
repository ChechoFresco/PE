

from flask_pymongo import PyMongo
from flask_compress import Compress
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, send_from_directory, Blueprint
from forms import searchForm, monitorListform, chartForm, monitorListform2, searchForm2
import bcrypt
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import os
import re
import json
import logging
from collections import Counter
from werkzeug.exceptions import BadRequest
from flask_mail import Mail
import atexit
from urllib.parse import unquote
from stripe_service import init as stripe_init, create_checkout_session, handle_webhook, get_user_stripe_customer, validate_registration
from helpers import get_date_threshold, handle_issue_operation, get_user_saved_agendas, int2date, get_county_agendas
from map_utils import fetch_geo_info, create_folium_map
from jobs import check4Issues2email, start_scheduler
from apscheduler.schedulers.background import BackgroundScheduler
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

# Initialize extensions
mongo = PyMongo(app)
mail = Mail(app)
stripe_init(mongo)

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
# CONSTANTS AND CONFIGURATION DATA
# =============================================================================

global ALL_CITY_AGENDAS_CACHE
ALL_CITY_AGENDAS_CACHE = {}
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
# TEMPLATE FILTERS
# =============================================================================
app.template_filter('aTime')(int2date)
# =============================================================================
# SCHEDULER CONFIGURATION
# =============================================================================
scheduler = start_scheduler(mongo, mail)
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

    # Determine search term
    if request.method == 'POST' and request.form.get('chartSearch'):
        search_term = request.form['chartSearch'].strip()
        chosen = f'"{search_term}"'

        # Log search
        mongo.db.User.find_one_and_update(
            {'username': 'Esther'},
            {'$push': {'searches': chosen}},
            upsert=True
        )

        # Query agendas
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {'$text': {"$search": chosen}},
                {"MeetingType": {'$regex': "City Council", '$options': 'i'}},
                {'Date': {'$gte': date_threshold}}
            ]
        }).sort('Date', -1)

    else:
        # Default GET: last week's agendas
        chosen = 'water'
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {"MeetingType": {'$regex': "City Council", '$options': 'i'}},
                {'Date': {'$gte': date_threshold}},
                {'Description': {'$nin': ["", None]}},
                {"Description": {'$not': {'$regex': "(minute|warrant)", '$options': 'i'}}}
            ]
        }).sort('Date', -1)

    # Organize agendas by city
    cities_matched = []
    folium_agendas = {}  # key = city, value = list of matching agenda dicts

    for agenda in agenda_items:
        city = agenda.get('City', '')
        description = agenda.get('Description', '')
        topics = agenda.get('Topics', [])

        # Update the full cache (if you still need it)
        if city not in ALL_CITY_AGENDAS_CACHE:
            ALL_CITY_AGENDAS_CACHE[city] = {"agendas": [], "topic_counts": Counter()}
        ALL_CITY_AGENDAS_CACHE[city]["agendas"].append(agenda)
        if isinstance(topics, list):
            ALL_CITY_AGENDAS_CACHE[city]["topic_counts"].update(topics)
        else:
            ALL_CITY_AGENDAS_CACHE[city]["topic_counts"].update([topics])

        # Only keep agendas that match `chosen`
        if chosen.strip('"') in description:
            if city not in folium_agendas:
                folium_agendas[city] = {"agendas": [], "topic_counts": Counter()}
            folium_agendas[city]["agendas"].append(agenda)
            # Optionally track topic counts
            if isinstance(topics, list):
                folium_agendas[city]["topic_counts"].update(topics)
            else:
                folium_agendas[city]["topic_counts"].update([topics])
            cities_matched.append(city)

    # Only send first 6 cities to template
    initial_cities = dict(list(ALL_CITY_AGENDAS_CACHE.items())[:6])

    # Map visualization
    city_issue_counts = Counter(cities_matched)

    # Get geo info from Mongo
    geo_info = fetch_geo_info(mongo, city_issue_counts)

    # Build Folium map
    folium_map = create_folium_map(geo_info, folium_agendas)

    # Pass folium_map to template (use _repr_html_ in template)
    return render_template(
        'index.html',
        folium_map=folium_map._repr_html_(),  # keep original name
        form=form,
        city_agendas=initial_cities,
        title="Policy Edge Tracking Agendas",
        chosen=chosen
    )

@app.route('/search')
def search():
    """Search page for agenda items"""
    form = searchForm2()
    return render_template('search.html', form=form, title='Search')

@app.route('/results', methods=['GET', 'POST'])
def results():
    """Handle search form submission and display results"""
    form = searchForm2(request.form)
    
    if request.method == 'POST':
        primeKey = form.primary_search.data.strip()
        start_date = form.startdate_field.data
        end_date = form.enddate_field.data

        # Set date range defaults
        start = int(start_date.strftime('%Y%m%d')) if start_date else get_date_threshold(weeks=-52)
        end = int(end_date.strftime('%Y%m%d')) if end_date else int(date.today().strftime('%Y%m%d'))
        
        criteria = form.select.data
        filters = []

        # Build search filters based on criteria
        if criteria == 'Issue':
            filters.append({'$text': {"$search": primeKey}})
        elif criteria in ['LA County', 'Orange County', 'Riverside County', 'San Diego County', 'San Bernardino County']:
            filters.append({'$text': {"$search": primeKey}})
            filters.append({'County': {'$regex': criteria, '$options': 'i'}})

            # Handle city selection
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
            filters.append({'$text': {"$search": primeKey}})
            filters.append({'County': {'$regex': 'LA County', '$options': 'i'}})
            committee_field = 'selectLACM' if criteria == 'LA Committees' else 'selectLBCM'
            selected_committee = getattr(form, committee_field).data
            if selected_committee:
                filters.append({'MeetingType': {'$regex': selected_committee, '$options': 'i'}})

        # Add date range filter
        filters.append({'Date': {'$gte': start, '$lte': end}})

        # Execute search
        agenda_list = list(mongo.db.Agenda.find({'$and': filters}).sort('Date', -1).limit(300))
            # Organize agendas by city

        cities_matched = []

        for agenda in agenda_list:
            city = agenda.get('City', '')
            topics = agenda.get('Topics', [])
            if city not in ALL_CITY_AGENDAS_CACHE:
                ALL_CITY_AGENDAS_CACHE[city] = {"agendas": [], "topic_counts": Counter()}
            ALL_CITY_AGENDAS_CACHE[city]["agendas"].append(agenda)
            if isinstance(topics, list):
                ALL_CITY_AGENDAS_CACHE[city]["topic_counts"].update(topics)
            else:
                ALL_CITY_AGENDAS_CACHE[city]["topic_counts"].update([topics])
            if primeKey.strip('"') in agenda.get('Description', ''):
                cities_matched.append(city)

        # Only send first 6 cities to template
        initial_cities = dict(list(ALL_CITY_AGENDAS_CACHE.items())[:6])

        # Map visualization
        city_issue_counts = Counter(cities_matched)

        # Get geo info from Mongo
        geo_info = fetch_geo_info(mongo, city_issue_counts)

        # Build Folium map **with agenda details**
        folium_map = create_folium_map(geo_info, ALL_CITY_AGENDAS_CACHE)

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

    return render_template('search.html', form=form, title="PolicyEdge Search")

# ---------------------------
# Load more cities via AJAX
# ---------------------------
@app.route('/load_more_cities')
def load_more_cities():
    start = int(request.args.get('start', 0))
    count = int(request.args.get('count', 6))
    cities_list = list(ALL_CITY_AGENDAS_CACHE.items())
    cities_to_load = dict(cities_list[start:start+count])

    rendered = ""
    for city, data in cities_to_load.items():
        rendered += render_template('partials/city_table_wrapper.html', _city=city, _data=data)

    return rendered

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if "username" in session:
        return redirect(url_for("index"))
    return render_template("register.html", title="Register for PolicyEdge")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if "username" in session:
        return redirect(url_for('index'))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = mongo.db.User.find_one({"username": username})

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            session['username'] = user["username"]
            session['email'] = user["email"]
            session['subscribed'] = user.get("subscriptionActive", False)
            flash('Login successful!')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    print("Rendering template from:", os.path.abspath("templates/login.html"))
    return render_template('login.html', title="Please Login")

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
        return render_template('subscription.html', title='Re-subscribe to PolicyEdge')
    else:
        return redirect(url_for("login"))

# =============================================================================
# STRIPE PAYMENT ROUTES
# =============================================================================

@app.route('/create-checkout-session', methods=['POST'])
def route_create_checkout_session():
    username = request.form["username"]
    email = request.form["email"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    # ✅ Validate registration using the imported function
    errors = validate_registration(username, email, password1, password2)

    if errors:
        for error in errors:
            flash(error)
        return render_template('register.html')

    hashed = bcrypt.hashpw(password2.encode('utf-8'), bcrypt.gensalt())
    mongo.db.User.insert_one({
        'username': username,
        'email': email,
        'password': hashed,
        'stripe_customer_id': None,
        'stripe_subscription_id': None,
        'subscriptionActive': False,
        'issues': [],
        'agendaUnique_id': []
    })

    session.update({'username': username, 'email': email})
    return create_checkout_session(email, your_domain=app.your_domain)

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
    
    form = monitorListform2()
    user = session["username"]
    
    if request.method == 'GET':
        # Get user's saved issues
        user_data = mongo.db.User.find_one(
            {'username': user}, 
            {'_id': 0, 'issues': 1}
        )
        issues_placeholder = user_data.get('issues', []) if user_data else []
        
        # Get matching agendas
        agendas = get_user_saved_agendas(user)
        
        return render_template(
            'savedIssues.html', 
            issues_placeholders=issues_placeholder, 
            form=form, 
            agendaas=agendas,
            title='Subscription List'
        )
    
    elif request.method == 'POST':
        # Handle add/delete operations for saved issues
        operation = request.form.get('action')
        handle_issue_operation(user, request.form, operation)
        
        # Refresh the page with updated data
        user_data = mongo.db.User.find_one(
            {'username': user}, 
            {'_id': 0, 'issues': 1}
        )
        issues_placeholder = user_data.get('issues', []) if user_data else []
        agendas = get_user_saved_agendas(user)
        
        return render_template(
            'savedIssues.html',
            issues_placeholders=issues_placeholder,
            form=form,
            agendaas=agendas,
            title='Subscription List'
        )

# =============================================================================
# TOPIC AND CITY DETAIL ROUTES
# =============================================================================

@app.route('/topic')
def topic():
    """Legacy topic route - now handled by background job"""
    return redirect(url_for('index'))

@app.route("/topicLink/<path:topic>", methods=['GET'])
def topic_details(topic):
    """Show agendas for a specific topic"""
    topic = unquote(topic)
    form = searchForm2()
    date_threshold = get_date_threshold(weeks=-2)
    city = request.args.get('city')

    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'Topics': {'$regex': topic, '$options': 'i'}},
            {"Description": {"$ne": ""}},
        ]
    }
    if city:
        query['$and'].append({"City": city})

    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))

    if not agendas:
        return "No agendas found for this topic.", 404

    return render_template(
        'share.html', 
        topic=topic, 
        form=form, 
        city=city, 
        agendas=agendas
    )

@app.route('/cityLink/<city>', methods=['GET'])
def city_details(city):
    """Show agendas for a specific city"""
    form = searchForm2()
    date_threshold = get_date_threshold(weeks=-2)
    topic = request.args.get('topic')

    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {"Description": {"$ne": ""}},
            {'City': {'$regex': city, '$options': 'i'}},
        ]
    }
    
    if topic:
        query['$and'].append({'Topics': {'$regex': topic, '$options': 'i'}})

    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))

    city_issue_counts = Counter([agenda.get('City', 'Unknown').strip() for agenda in agendas])
    unique_city_count = len(city_issue_counts)

    return render_template(
        'share.html',
        topic=topic,
        city=city,
        agendas=agendas,
        form=form,
        unique_city_count=unique_city_count,
        city_issue_counts=city_issue_counts,
    )

# -------------------------------
# COUNTY ROUTES CONFIGURATION
# -------------------------------
COUNTY_ROUTES = {
    "losangeles": {
        "name": "LA County",
        "template": "county.html",
        "title": "PolicyEdge agenda tracking monitoring Los Angeles County Search Results"
    },
    "orange": {
        "name": "Orange County",
        "template": "county.html",
        "title": "PolicyEdge agenda tracking monitoring all of Orange County"
    },
    "riverside": {
        "name": "Riverside County",
        "template": "county.html",
        "title": "PolicyEdge agenda tracking monitoring all of Riverside County"
    },
    "sanbernandino": {
        "name": "San Bernandino County",
        "template": "county.html",
        "title": "PolicyEdge agenda tracking monitoring all of San Bernardino County"
    },
    "sandiego": {
        "name": "San Diego County",
        "template": "county.html",
        "title": "PolicyEdge agenda tracking monitoring all of San Diego County"
    },
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
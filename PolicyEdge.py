from flask_pymongo import PyMongo
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, send_from_directory
from forms import searchForm, monitorListform, chartForm, monitorListform2, searchForm2
import bcrypt
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from flask_mail import Mail, Message
import stripe
import os
import re
from apscheduler.schedulers.background import BackgroundScheduler
from collections import Counter
import logging
from werkzeug.exceptions import BadRequest
import atexit
import folium
from folium.features import DivIcon
from urllib.parse import unquote

# =============================================================================
# INITIALIZATION AND CONFIGURATION
# =============================================================================

app = Flask(__name__)

# Configuration - Using environment variables for security
app.config['MONGO_URI'] = os.environ.get("MONGO_URI")
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.secret_key = os.environ.get("SESS_KEY")

# Initialize extensions
mongo = PyMongo(app)
mail = Mail(app)

# Constants
YOUR_DOMAIN = 'https://www.policyedge.net/'
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

# Topic mappings for automatic categorization of agenda items
TOPIC_MAPPINGS = {
    "agreement": "Awarded Agreement",
    "appointment": "Appointment",
    "accept": "Approvals", "approve": "Approvals", "approval": "Approvals",
    "award": "Award",
    "bids": "Bids",
    "budget": "Budget",
    "closed session": "Closed Session", "conference with": "Closed Session", 
    "conferencewith": "Closed Session",
    "consultant": "Consultant",
    "contract": "Contract",
    "discuss": "Discussion", "discussion": "Discussion",
    "election": "Election",
    "emergency": "Emergency",
    "event": "Event", "events": "Event",
    "fire": "Fire",
    "housing": "Housing",
    "introduce": "Introductions", "introduction": "Introductions",
    "lease": "Lease",
    "license": "License",
    'memorandum': "Memorandum",
    "moratorium": "Moratorium",
    "notice": "Notice",
    "nuisance": "Nuisance",
    "ordinance": "Ordinance",
    "police": "Police",
    "presentation": "Presentation", "recognition": "Presentation", 
    "recogniz": "Presentation",
    "proclaim": "Proclamation", "proclamation": "Proclamation",
    "professional": "Professional Service Agreements",
    "program": "Program",
    "propose": "Proposal", "proposal": "Proposal",
    "public hearing": "Public Hearing",
    "purchase": "Purchase",
    "reject": "Reject",
    "report": "Report",
    "request": "Request",
    "resolution": "Resolution",
    "rescind": "Rescind",
    "retail": "Retail",
    "rfp": "Request for Proposal",
    "treasurer": "Treasurer",
    "study": "Study",
    "update": "Update"
}

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
# HELPER FUNCTIONS
# =============================================================================

def get_date_threshold(weeks=-2):
    """Get date threshold in YYYYMMDD format for database queries"""
    return int((date.today() + relativedelta(weeks=weeks)).strftime('%Y%m%d'))

def fetch_geo_info(city_issue_counts):
    """Fetch geo-location data from MongoDB for map generation"""
    geo_info = []
    for city, count in city_issue_counts.items():
        location_data = mongo.db.geoLoc.find_one({'city': city}, {'_id': 0})
        if location_data:
            geo_info.append((
                location_data['city'], 
                location_data['state_id'], 
                location_data['county_name'],
                location_data['lat'], 
                location_data['lng'], 
                str(count), 
                location_data['webAdress']
            ))
    return geo_info

def create_folium_map(geo_info):
    """Create a Folium map with circles and markers for agenda visualization"""
    folium_map = folium.Map(
        location=(34, -118), 
        zoom_start=9, 
        tiles="cartodbpositron", 
        width=1000, 
        height=475
    )
    
    for city, state_id, county_name, lat, lon, issue_count, web_address in geo_info:
        # Add circle marker proportional to issue count
        folium.Circle(
            location=[lat, lon],
            popup=f"<a href='{web_address}' target='_blank'>{city} Agenda Link</a>",
            radius=float(issue_count) * 50,
            color='#5e7cff',
            fill=True,
            fill_color='#5e7cff'
        ).add_to(folium_map)
        
        # Add text marker with count
        folium.Marker(
            location=[lat, lon],
            icon=DivIcon(
                icon_size=(10, 10),
                icon_anchor=(15, 15),
                html=f'<div style="font-size: 10pt">{issue_count} {city}</div>'
            )
        ).add_to(folium_map)
    
    return folium_map

def validate_registration(username, email, password1, password2):
    """Validate registration form data and return list of errors"""
    errors = []
    
    if mongo.db.User.find_one({"username": username}):
        errors.append('There already is a user by that name')
    if mongo.db.User.find_one({"email": email}):
        errors.append('This email already exists in our user database')
    if mongo.db.stripe_user.find_one({"email": email}):
        errors.append('This email already exists in our Stripe database')
    if ' ' in username:
        errors.append('Please no whitespaces in username')
    if not re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
        errors.append('Please use a valid email address')
    if password1 != password2:
        errors.append('Passwords should match!')
    if len(password1) < 8:
        errors.append('Please make sure password is longer than 8 characters')
    
    return errors

def create_stripe_checkout_session(email, existing_customer_id=None):
    """Create Stripe checkout session for subscription payments"""
    try:
        if existing_customer_id:
            customer = existing_customer_id
        else:
            # Create new Stripe customer
            customer_obj = stripe.Customer.create(
                description="PolicyEdge subscriber",
                email=email
            )
            customer = customer_obj.id
            
            # Store customer ID in database
            mongo.db.User.update_one(
                {'email': email},
                {'$push': {'stripe_id': customer}}
            )
            mongo.db.stripe_user.update_one(
                {'email': email},
                {'$push': {'stripeCustomerId': customer}}
            )

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': os.environ.get("STRIPE_MONTH_PRICE_ID"),
                'quantity': 1
            }],
            mode='subscription',
            customer=customer,
            success_url=YOUR_DOMAIN + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + 'cancel',
        )
        
        return redirect(checkout_session.url, code=303)
        
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        flash('Error creating checkout session. Please try again.')
        return redirect(url_for('register'))

def get_user_stripe_customer(email):
    """Retrieve existing Stripe customer ID for a user"""
    user = mongo.db.User.find_one(
        {'email': email, 'stripe_id': {'$exists': True, '$ne': []}}
    )
    if user and user.get('stripe_id'):
        return user['stripe_id'][0]  # Return first stripe_id
    return None

def handle_issue_operation(user, form_data, operation):
    """Handle adding or removing issues from user's saved list"""
    primeKey = form_data.get('primary_search', '').strip()
    county = form_data.get('select', '')
    city_field_map = {
        'LA County': 'selectLA', 'Orange County': 'selectOC', 
        'Riverside County': 'selectRS', 'San Bernardino County': 'selectSB',
        'San Diego County': 'selectSD'
    }
    
    city = form_data.get(city_field_map.get(county, ''), '')
    committee = form_data.get('selectLACM', '') or form_data.get('selectLBCM', '')
    
    # Handle LA/Long Beach committees specially
    if county in ['LA Committees', 'Long Beach Committees']:
        county = 'LA County'
        city = 'Los Angeles' if 'LA Committees' in form_data else 'Long Beach'
        committee = form_data.get('selectLACM', '') or form_data.get('selectLBCM', '')

    issue_data = {
        "searchWord": primeKey,
        "City": city,
        "Committee": committee,
        "County": county,
    }
    
    # Use $push for Add, $pull for Delete
    operation = '$push' if operation == 'Add' else '$pull'
    mongo.db.User.update_one(
        {'username': user},
        {operation: {'issues': issue_data}}
    )

def get_user_saved_agendas(user, days_back=60, days_forward=30):
    """Get agendas matching user's saved issues"""
    today = int(date.today().strftime('%Y%m%d'))
    start_date = int((date.today() + relativedelta(days=-days_back)).strftime('%Y%m%d'))
    end_date = int((date.today() + relativedelta(days=days_forward)).strftime('%Y%m%d'))
    
    # Get user's saved issues
    user_data = mongo.db.User.find_one(
        {'username': user}, 
        {'_id': 0, 'issues': 1}
    )
    
    if not user_data or not user_data.get('issues'):
        return []
    
    agendas = []
    for issue in user_data['issues']:
        query = {
            '$and': [
                {"MeetingType": {'$regex': issue.get('Committee', ''), '$options': 'i'}},
                {"City": {'$regex': issue.get('City', ''), '$options': 'i'}},
                {"County": {'$regex': issue.get('County', ''), '$options': 'i'}},
                {'Description': {"$regex": issue.get('searchWord', ''), '$options': 'i'}},
                {'Date': {'$lte': end_date, '$gte': start_date}}
            ]
        }
        matching_agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))
        agendas.extend(matching_agendas)
    
    return agendas

# =============================================================================
# BACKGROUND JOBS (SCHEDULED TASKS)
# =============================================================================

def check4Issues2email():
    """Background job to check for issues and send email notifications to users"""
    with app.app_context():
        today = int(date.today().strftime('%Y%m%d'))
        
        # Get all subscribed users with emails
        users = list(mongo.db.User.find({
            'email': {'$exists': True, '$ne': ''},
            'subscriptionActive': True
        }))
        
        logger.info(f"Processing {len(users)} users for email notifications")
        
        for user in users:
            try:
                process_user_email_notifications(user, today)
            except Exception as e:
                logger.error(f"Error processing user {user.get('username')}: {e}")

def process_user_email_notifications(user, today):
    """Process and send email notifications for a single user"""
    username = user.get('username')
    email = user.get('email')

    if not email or not user.get('subscriptionActive'):
        return

    # Clean old agenda IDs (older than today)
    mongo.db.User.update_one(
        {'username': username},
        {'$pull': {'agendaUnique_id': {'Date': {'$lt': today}}}}
    )

    # Get user's saved issues and previously seen agenda IDs
    user_data = mongo.db.User.find_one(
        {'username': username},
        {'issues': 1, 'agendaUnique_id': 1, '_id': 0}
    )

    if not user_data or not user_data.get('issues'):
        return

    issues = user_data['issues']
    seen_agenda_ids = {agenda['_id'] for agenda in user_data.get('agendaUnique_id', [])}

    # Dictionary to store agendas grouped by search term
    agendas_by_search_term = {}
    
    for issue in issues:
        search_term = issue.get('searchWord', '')
        if not search_term:
            continue
            
        query = {
            '$and': [
                {"MeetingType": {'$regex': issue.get('Committee', ''), '$options': 'i'}},
                {"City": {'$regex': issue.get('City', ''), '$options': 'i'}},
                {"County": {'$regex': issue.get('County', ''), '$options': 'i'}},
                {'Description': {"$regex": search_term, '$options': 'i'}},
                {'Date': {'$gte': today}}
            ]
        }
        matching_agendas = list(mongo.db.Agenda.find(query))

        for agenda in matching_agendas:
            if agenda['_id'] not in seen_agenda_ids:
                # Create a copy with the search term included
                agenda_data = dict(agenda)
                agenda_data['searchWord'] = search_term
                agenda_data['matchedSearchTerm'] = search_term
                
                # Group by search term
                if search_term not in agendas_by_search_term:
                    agendas_by_search_term[search_term] = []
                agendas_by_search_term[search_term].append(agenda_data)
                
                # Mark as seen
                mongo.db.User.update_one(
                    {'username': username},
                    {'$addToSet': {'agendaUnique_id': {
                        '_id': agenda['_id'],
                        'Date': agenda['Date']
                    }}}
                )

    # Send email if there are new agendas
    if agendas_by_search_term:
        send_agenda_email(username, email, agendas_by_search_term)

def highlight_corners(text, search_term):
    if not text or not search_term:
        return text
    # Wrap search_term matches in <mark> tags
    import re
    pattern = re.escape(search_term)
    return re.sub(pattern, lambda m: f"<mark>{m.group(0)}</mark>", text, flags=re.IGNORECASE)

# Register the filter
app.jinja_env.filters['highlight_corners'] = highlight_corners

def send_agenda_email(username, email, agendas_by_search_term):
    """Send email notification about new matching agendas grouped by search term"""
    try:
        # Calculate total agendas
        total_agendas = sum(len(agendas) for agendas in agendas_by_search_term.values())
        
        subject = f'You have {total_agendas} new agenda items from Policy Edge'
        msg = Message(
            subject,
            sender='AgendaPreciado@gmail.com',
            recipients=[email]
        )

        # Log what we're about to send
        logger.info(f"Sending email to {username}")
        logger.info(f"Search terms found: {list(agendas_by_search_term.keys())}")
        logger.info(f"Total items: {total_agendas}")

        # Render the template with grouped data
        msg.html = render_template('schedEmail.html',
                                username=username,
                                agendas_by_search_term=agendas_by_search_term,
                                total_agendas=total_agendas)
        
        # Attach logo
        with app.open_resource('/app/static/logo.png') as fp:
            msg.attach(
                filename="logo.png",
                content_type="image/png",
                data=fp.read(),
                disposition="inline",
                headers={"Content-ID": "<logo_png>"}
            )

        # Send the email
        mail.send(msg)
        logger.info(f"✓ Email successfully sent to {username} at {email}")

    except Exception as e:
        logger.error(f"✗ Failed to send email to {username} ({email}): {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        

def process_topics():
    """Background job to automatically categorize agenda items by topic"""
    with app.app_context():
        date_threshold = get_date_threshold(weeks=-2)
        
        # Get recent agenda items
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {"MeetingType": "City Council"},
                {'Date': {'$gte': date_threshold}}
            ]
        })

        processed_count = 0
        for agenda in agenda_items:
            matching_topics = []
            
            # Check description and item type for topic keywords
            description = agenda.get('Description', '').lower()
            item_type = agenda.get('ItemType', '').lower()
            
            for keyword, topic in TOPIC_MAPPINGS.items():
                if keyword in description or keyword in item_type:
                    if topic not in matching_topics:
                        matching_topics.append(topic)

            # Default to "No Match" if no topics found
            if not matching_topics:
                matching_topics.append("No Match")

            # Update agenda with identified topics
            try:
                mongo.db.Agenda.update_one(
                    {'_id': agenda['_id']},
                    {'$set': {'Topics': matching_topics}},
                    upsert=True
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"Error updating agenda {agenda['_id']}: {e}")

        logger.info(f"Processed topics for {processed_count} agenda items")

# =============================================================================
# SCHEDULER CONFIGURATION
# =============================================================================

# Initialize a single scheduler instance
scheduler = BackgroundScheduler(timezone='UTC')

# Add both background jobs to the same scheduler
scheduler.add_job(
    check4Issues2email, 
    'interval', 
    seconds=15,  # Run every hour
    id='email_check',
    max_instances=1
)

scheduler.add_job(
    process_topics, 
    'interval', 
    seconds=3600,  # Run every hour
    id='topic_processing',
    max_instances=1
)

def shutdown_scheduler():
    """Gracefully shutdown the scheduler when application stops"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully")

# Start the scheduler
scheduler.start()
logger.info("Background scheduler started with 2 jobs")

# Register shutdown function to run when application exits
atexit.register(shutdown_scheduler)

# =============================================================================
# TEMPLATE FILTERS
# =============================================================================

@app.template_filter('aTime')
def int2date(agDate: int) -> str:
    """Convert integer date (YYYYMMDD) to formatted string (Month Day, Year)"""
    try:
        dt = datetime.strptime(str(agDate), '%Y%m%d')
        return dt.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return "Invalid Date"

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
    """Main index page with agenda search and visualization"""
    form = chartForm()
    date_threshold = get_date_threshold(weeks=-2)
    
    if request.method == 'GET':
        # Default search for 'water' related agendas
        chosen = 'water'
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {"MeetingType": {'$regex': "City Council", '$options': 'i'}},
                {'Date': {'$gte': date_threshold}},
                {
                    '$and': [
                        {"Description": {'$not': {'$regex': "minute", '$options': 'i'}}},
                        {"Description": {'$not': {'$regex': "warrant", '$options': 'i'}}},
                        {"Description": {"$ne": ""}}
                    ]
                }
            ]
        }).sort('Date', -1)

        # Organize agendas by city
        cities_matched = []
        city_agendas = {city: {"agendas": [], "topic_counts": Counter()} for city in ALL_CITIES}

        for agenda in agenda_items:
            agenda_city = agenda.get('City', '')
            if chosen in agenda.get('Description', ''):
                cities_matched.append(agenda_city)
            
            topics = agenda.get('Topics', [])
            if agenda_city in city_agendas:
                city_agendas[agenda_city]["agendas"].append(agenda)
                if isinstance(topics, list):
                    city_agendas[agenda_city]["topic_counts"].update(topics)
                else:
                    city_agendas[agenda_city]["topic_counts"].update([topics])

        # Create map visualization
        city_issue_counts = Counter(cities_matched)
        geo_info = fetch_geo_info(city_issue_counts)
        folium_map = create_folium_map(geo_info)

        return render_template(
            'index.html', 
            folium_map=folium_map._repr_html_(),
            chosen=chosen, 
            form=form,
            city_agendas=city_agendas, 
            title="Policy Edge Tracking Agendas"
        )

    elif request.method == 'POST' and request.form.get('chartSearch'):
        # Handle search form submission
        try:
            search_term = request.form['chartSearch']
            chosen = f'"{search_term}"'
            
            # Log search for analytics
            mongo.db.User.find_one_and_update(
                {'username': 'Esther'},  # Analytics user
                {'$push': {'searches': chosen}},
                upsert=True
            )

            # Search for matching agendas
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'$text': {"$search": chosen}},
                    {"MeetingType": {'$regex': "^ City Council $", '$options': 'i'}},
                    {'Date': {'$gte': date_threshold}}
                ]
            }).sort('Date', -1)

            # Organize results by city
            city_agendas = {city: [] for city in ALL_CITIES}
            cities_matched = []

            for agenda in agenda_items:
                city = agenda.get('City', '')
                cities_matched.append(city)
                if city in city_agendas:
                    city_agendas[city].append(agenda)

            # Create map visualization
            city_issue_counts = Counter(cities_matched)
            geo_info = fetch_geo_info(city_issue_counts)
            folium_map = create_folium_map(geo_info)

            return render_template(
                'descriptionLink.html',
                folium_map=folium_map._repr_html_(),
                form=form, 
                chosen=chosen,
                city_agendas=city_agendas,
                title="Policy Edge Tracking Agendas"
            )
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            flash("Sorry. No matches found.")
            return redirect(url_for('index'))

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
def create_checkout_session():
    """Handle new user registration and subscription payment"""
    stripe.api_key = stripe_keys['secret_key']
    
    username = request.form["username"]
    email = request.form["email"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]
    
    # Validate registration data
    errors = validate_registration(username, email, password1, password2)
    if errors:
        for error in errors:
            flash(error)
        return render_template('register.html')
    
    # Create user account
    hashed = bcrypt.hashpw(password2.encode('utf-8'), bcrypt.gensalt())
    user_data = {
        'username': username, 
        'email': email, 
        'password': hashed, 
        'stripe_id': [],
        'issues': [], 
        'agendaUnique_id': [], 
        'subscriptionActive': False
    }
    mongo.db.User.insert_one(user_data)
    mongo.db.stripe_user.insert_one({
        'username': username, 
        'email': email, 
        'stripeCustomerId': [], 
        'stripeSubscriptionId': []
    })
    
    # Set session and create Stripe checkout
    session.update({'username': username, 'email': email})
    return create_stripe_checkout_session(email)

@app.route('/create-checkout-session2', methods=['POST'])
def create_checkout_session2():
    """Handle subscription for existing users"""
    stripe.api_key = stripe_keys['secret_key']

    if "username" not in session:
        return redirect(url_for("login"))

    email = session["email"]
    existing_customer_id = get_user_stripe_customer(email)
    
    return create_stripe_checkout_session(email, existing_customer_id)

@app.route('/create-portal-session', methods=['POST'])
def customer_portal():
    """Create Stripe customer portal session for subscription management"""
    stripe.api_key = stripe_keys['secret_key']

    checkout_session_id = request.form.get('session_id')
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    portalSession = stripe.billing_portal.Session.create(
        customer=checkout_session.customer,
        return_url=YOUR_DOMAIN,
    )
    return redirect(portalSession.url, code=303)

@app.route('/webhook', methods=['POST'])
def webhook_received():
    """Handle Stripe webhook events for subscription updates"""
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    request_data = json.loads(request.data)
    
    if webhook_secret:
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, 
                sig_header=signature, 
                secret=webhook_secret
            )
            data = event['data']
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return jsonify({'status': 'error'}), 400

        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']

    # Handle different Stripe event types
    if event_type == 'checkout.session.completed':
        logger.info("Payment succeeded!")
        
    elif event_type == 'customer.created':
        customer_id = data.object.id
        customer_email = data.object.email
        mongo.db.User.update_one(
            {'email': customer_email},
            {'$push': {'stripe_id': customer_id}}
        )
        mongo.db.stripe_user.update_one(
            {'email': customer_email},
            {'$push': {'stripeCustomerId': customer_id}}
        )
        logger.info(f"New Stripe customer created: {customer_email}")
        
    elif event_type == 'customer.subscription.created':
        subscription_id = data.object.id
        customer_id = data.object.customer
        mongo.db.stripe_user.update_one(
            {'stripeCustomerId': customer_id},
            {'$push': {'stripeSubscriptionId': subscription_id}}
        )
        mongo.db.User.update_one(
            {'stripe_id': customer_id},
            {'$set': {'subscriptionActive': True}}
        )
        logger.info(f"New subscription created for customer: {customer_id}")
        
    elif event_type == 'customer.subscription.updated':
        subscription = data.object
        customer_id = subscription.customer
        status = subscription.status
        
        # Update subscription status based on Stripe events
        status_mapping = {
            'active': True,
            'trialing': True,
            'past_due': False,
            'canceled': False,
            'unpaid': False,
            'incomplete': False
        }
        
        if status in status_mapping:
            mongo.db.User.update_one(
                {'stripe_id': customer_id},
                {'$set': {'subscriptionActive': status_mapping[status]}}
            )
            logger.info(f"Subscription updated for {customer_id}: {status}")
            
    elif event_type == 'customer.subscription.deleted':
        customer_id = data.object.customer
        mongo.db.User.update_one(
            {'stripe_id': customer_id},
            {'$set': {'subscriptionActive': False}}
        )
        logger.info(f"Subscription canceled for customer: {customer_id}")

    return jsonify({'status': 'success'})

# =============================================================================
# SEARCH AND AGENDA ROUTES
# =============================================================================

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
        
        # Organize results by city
        city_agendas = {city: {"agendas": [], "issue_counts": Counter()} for city in ALL_CITIES}
        cities_matched = []

        for agenda in agenda_list:
            city = agenda.get('City', '').strip()
            if primeKey in agenda.get('Description', ''):
                cities_matched.append(city)
                
            if city in city_agendas:
                city_agendas[city]["agendas"].append(agenda)
                topics = agenda.get('Topics', [])
                if isinstance(topics, list):
                    city_agendas[city]["issue_counts"].update(topics)
                else:
                    city_agendas[city]["issue_counts"].update([topics])

        # Create map visualization
        city_issue_counts = Counter(cities_matched)
        geo_info = fetch_geo_info(city_issue_counts)
        folium_map = create_folium_map(geo_info)
        
        return render_template(
            'search.html',
            folium_map=folium_map._repr_html_(),
            primeKey=primeKey,
            city_issue_counts=city_issue_counts,
            city_agendas=city_agendas,
            form=form,
            agendas=agenda_list,
            title="PolicyEdge Search Results"
        )

    return render_template('search.html', form=form, title="PolicyEdge Search")

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

@app.route('/descriptionLink/<keyword>', methods=['GET'])
def description_details(keyword):
    """Show agendas matching a specific keyword in description"""
    form = searchForm2()
    date_threshold = get_date_threshold(weeks=-2)

    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'$text': {"$search": keyword}},
            {"Description": {"$ne": ""}},
        ]
    }

    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))
    city_issue_counts = Counter(agenda.get('City', '').strip() for agenda in agendas)

    geo_info = fetch_geo_info(city_issue_counts)
    folium_map = create_folium_map(geo_info)

    return render_template(
        'share.html',
        keyword=keyword,
        form=form,
        agendas=agendas,
        folium_map=folium_map._repr_html_(),
        city_issue_counts=city_issue_counts,
    )

@app.route('/share/<topic>', methods=['GET'])
def agenda_details(topic):
    """Shareable page for a specific topic with filtering"""
    date_threshold = get_date_threshold(weeks=-2)

    # Filter out common administrative agenda items
    exclude_patterns = [
        "minute", "warrant", "public", "flag salute", "invocation", 
        "call to order", "pledge of allegiance", "roll call", "check register"
    ]

    query_conditions = [
        {'Date': {'$gte': date_threshold}},
        {'Topics': {'$regex': topic, '$options': 'i'}},
        {"Description": {"$ne": ""}},
    ]
    
    # Add exclusion conditions
    for pattern in exclude_patterns:
        query_conditions.append({"Description": {'$not': {'$regex': pattern, '$options': 'i'}}})

    agendas = list(mongo.db.Agenda.find({'$and': query_conditions}).sort('Date', -1))

    if not agendas:
        return "Agenda not found", 404

    city_issue_counts = Counter(agenda.get('City', '').strip() for agenda in agendas)
    geo_info = fetch_geo_info(city_issue_counts)
    folium_map = create_folium_map(geo_info)

    return render_template(
        'share.html',
        folium_map=folium_map._repr_html_(),
        topic=topic,
        agendas=agendas,
        unique_city_count=len(city_issue_counts),
        agenda_count=len(agendas),
        city_issue_counts=city_issue_counts
    )

# =============================================================================
# STATIC PAGES AND COUNTY-SPECIFIC ROUTES
# =============================================================================

@app.route('/success')
def success():
    """Subscription success page"""
    return render_template("success.html", title='PolicyEdge subscription successful')

@app.route('/cancel')
def cancelled():
    """Subscription cancellation page"""
    return render_template("cancel.html", title='Cancel PolicyEdge subscription')

@app.route('/noSubscription')
def noSubscription():
    """No active subscription page"""
    return render_template("noSubscription.html", title='PolicyEdge subscription not active')

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html', title="About Policy Edge creator Sergio Preciado")

@app.route('/termsofservice')
def termsofservice():
    """Terms of service page"""
    return render_template('termsofservice.html', title='Terms of Service')

@app.route('/privacypolicy')
def privacypolicy():
    """Privacy policy page"""
    return render_template('privacypolicy.html', title='Privacy Policy')

def get_county_agendas(county_name, weeks_back=16):
    """Helper function to get agendas for a specific county"""
    date_threshold = int((date.today() + relativedelta(weeks=-weeks_back)).strftime('%Y%m%d'))
    
    try:
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {'Date': {'$gte': date_threshold}},
                {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                {'County': {'$regex': county_name, '$options': 'i'}},
                {"$expr": { "$gt": [ { "$strLenCP": "$Description" }, 5 ] }},
                {
                    '$and': [
                        { "Description": { '$not': { '$regex': "minute" } } },
                        { "Description": { '$not': { '$regex': "warrant" } } }
                    ]
                }
            ]
        }).sort('Date', -1)
        return list(agenda_items)
    except Exception as e:
        logger.error(f"Error querying {county_name} agendas: {e}")
        return []

@app.route('/losangeles')
def losangeles():
    """Los Angeles County agendas page"""
    agenda_items = get_county_agendas('LA County')
    city_agendas = {city: [] for city in CITIES['LA']}
    
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city in city_agendas:
            city_agendas[city].append(agenda)
    
    return render_template(
        'losangeles.html',
        city_agendas=city_agendas,
        title="PolicyEdge agenda tracking monitoring Los Angeles County Search Results"
    )

@app.route('/orange')
def orange():
    """Orange County agendas page"""
    agenda_items = get_county_agendas('Orange County')
    city_agendas = {city: [] for city in CITIES['OC']}
    
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city in city_agendas:
            city_agendas[city].append(agenda)
    
    return render_template(
        'orange.html',
        city_agendas=city_agendas,
        title="PolicyEdge agenda tracking monitoring all of Orange County"
    )

@app.route('/riverside')
def riverside():
    """Riverside County agendas page"""
    agenda_items = get_county_agendas('Riverside County')
    city_agendas = {city: [] for city in CITIES['RS']}
    
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city in city_agendas:
            city_agendas[city].append(agenda)
    
    return render_template(
        'riverside.html',
        city_agendas=city_agendas,
        title="PolicyEdge agenda tracking monitoring all of Riverside County"
    )

@app.route('/sanbernardino')
def sanbernardino():
    """San Bernardino County agendas page"""
    agenda_items = get_county_agendas('San Bernardino County')
    city_agendas = {city: [] for city in CITIES['SB']}
    
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city in city_agendas:
            city_agendas[city].append(agenda)
    
    return render_template(
        'sanbernardino.html',
        city_agendas=city_agendas,
        title="PolicyEdge agenda tracking monitoring all of San Bernardino County"
    )

@app.route('/sandiego')
def sandiego():
    """San Diego County agendas page"""
    agenda_items = get_county_agendas('San Diego County')
    city_agendas = {city: [] for city in CITIES['SD']}
    
    for agenda in agenda_items:
        city = agenda.get('City', '')
        if city in city_agendas:
            city_agendas[city].append(agenda)
    
    return render_template(
        'sandiego.html',
        city_agendas=city_agendas,
        title="PolicyEdge agenda tracking monitoring all of San Diego County"
    )

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def page_not_found(e):
    """404 error handler"""
    return render_template('404.html', title="404"), 404

@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"Internal server error: {error}")
    return render_template('500.html', title="500"), 500

# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    # Production configuration - disable debug mode
    app.run(debug=False, host='0.0.0.0', port=5000)











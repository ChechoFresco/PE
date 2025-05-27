from flask_pymongo import PyMongo
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, json, g, Blueprint, send_from_directory
from forms import searchForm, monitorListform, chartForm, monitorListform2, searchForm2
import bcrypt
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from flask_mail import Mail, Message
import stripe
import os
import re
from apscheduler.schedulers.background import BackgroundScheduler
import random
import time
from collections import Counter
import pandas as pd
import string
import matplotlib.pyplot as plt
#from flask_debugtoolbar import DebugToolbarExtension
import json
from urllib.request import urlopen
import numpy as np
import geopandas as gpd
import folium
from folium.features import DivIcon
import pgeocode
import logging
from werkzeug.exceptions import BadRequest


app = Flask(__name__,)

app.config['MONGO_URI'] = os.environ.get("MONGO_URI")
app.config['MAIL_SERVER']='smtp.gmail.com'#Email
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.secret_key = os.environ.get("SESS_KEY")

mongo = PyMongo(app)
mail = Mail(app)

YOUR_DOMAIN = 'https://www.policyedge.net/'

stripe_keys = {
    'secret_key': os.environ['SECRET_KEY'],
    'publishable_key': os.environ['PUBLISHABLE_KEY']
}
stripe.api_key = stripe_keys['secret_key']

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.static_folder, 'robots.txt')

def check4Issues2email():
    with app.app_context():
    ##########Date###############
        a = date.today()
        today= int(a.strftime('%Y%m%d'))

    ##########User roundup###############
        all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1, 'agendaUnique_id':1, 'email':1, 'subscriptionActive':1, 'issues':1})#Creates list af all emails and usernames for sequence

        for x in all_users: #For each instance of a user
            email=x['email']#Grabs email for new schedEmail.html
            if x['subscriptionActive'] == true: #Checks to see if user is subscribed
    ##################Deletes old id for issues###############
                check=mongo.db.User.find({'username':x['username']},{'_id':0 , 'agendaUnique_id': 1})
                for q in check:
                    for qq in q['agendaUnique_id']:
                        if qq['Date'] < today:
                            stuff = {
                                "_id": qq['_id'] ,
                                "Date": qq['Date'] ,
                            }
                            mongo.db.User.find_one_and_update({'username':x['username']}, {'$pull': {'agendaUnique_id': stuff}}, upsert = True)

    ##########Item roundup###############
                storedIssues= mongo.db.User.find({'username':x['username']}, {'_id': 0, 'issues.searchWord':1, 'issues.County':1, 'issues.City':1, 'issues.Committee':1, 'agendaUnique_id':1, 'email':1})#Bring forth the following data


                issues_placeholder= []#List of user subscribed issues
                userStoredAgendaId=[]#List of user previous topics

                for y in storedIssues:
                    issues_placeholder.append(y['issues'])#subscribed issues
                    for yy in y['agendaUnique_id']:
                        userStoredAgendaId.append(yy['_id'])#previous topics

                agenda=[]
                agenda2=[]

                for z in range(len(issues_placeholder[0])): #For every item in issues_placeholder, breaks down into individual parts in order for Multiquery to function
                    issue_Search= (issues_placeholder[0][z]['searchWord'])#Grabs Issue
                    county_Search= (issues_placeholder[0][z]['County'])
                    city_Search= (issues_placeholder[0][z]['City'])#Grabs City
                    committee_Search= (issues_placeholder[0][z]['Committee'])

    ##################Multiquery uses each _Search to run individual db.finds to create multiquery
                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$gte':int(today)}}]})

                    for query in Multiquery:#Places individualised results in agenda from Multiquery
                        agenda.append(query)
                        agenda2.append(issue_Search)

                description=[]###Information is grabbed from loop done below
                issue=[]
                city=[]
                Date=[]
                County=[]
                meeting_type=[]
                item_type=[]
                agendaLink=[]

                email_body=[]
                itemCount=0

                for zz in agenda2:
                    issue.append(zz)

                for i in agenda: #returned criteria
                    if i['_id'] not in userStoredAgendaId:
                        itemCount+=1
                        mongo.db.User.find_one_and_update({'username':x['username']}, {'$addToSet': {'agendaUnique_id':{'_id':i['_id'],'Date':i['Date']}}})# updates database with topics uniqueid
                        description.append(i['Description'])
                        city.append(i['City'])
                        County.append(i['County'])
                        intDate= (str(i['Date']))
                        start_year = str(intDate[0:4])
                        start_month = str(intDate[4:6])
                        start_day = str(intDate[6:8])
                        links=mongo.db.doc.find_one({"City":{'$regex': i['City'], '$options': 'i'}},{'_id': 0,'webAdress': 1} )
                        links2= str(links).replace("{'webAdress': '","").replace("'}","")
                        agendaLink.append(links2)
                        Date.append(start_month+'/'+start_day+'/'+start_year)
                        meeting_type.append(i['MeetingType'])
                        item_type.append(i['ItemType'])

                for y in range(len(city)):#range(len)city is used because it gives accurate count of topics being sent
                    email_body.append("<p style ='font-weight: bold;' >The following issue '{}' will be brought before the {} {} in {} on {}.</p>  {} <br></br> <br></br> Provided is a link to the agendas {}. <br></br><br></br><br></br>".format(issue[y],city[y],meeting_type[y],County[y],Date[y],description[y], agendaLink[y]))

                if len(email_body)==0:
                    pass
                else:
                    subject = 'You have {} items today from Policy Edge'.format(itemCount)
                    sender = 'AgendaPreciado@gmail.com'
                    msg = Message(subject, sender=sender, recipients=[x['email']])
                    msg.html = render_template('schedEmail.html', email=email, packed=zip(issue, city, meeting_type, County, Date, description, agendaLink ))
                    with app.open_resource('/app/static/logo.png') as fp:
                        msg.attach(
                            filename="logo.png",
                            content_type="image/png",
                            data=fp.read(),
                            disposition="inline",
                            headers={"Content-ID": "<voucher_png>"}
                        )
                    mail.send(msg)
            else:
                pass

sched = BackgroundScheduler(timezone='UTC')
sched.add_job(check4Issues2email, 'interval', seconds=30)
sched.start()

@app.route('/topic')
def topic():
    with app.app_context():
        date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))
        topic_mappings = {
            "agreement": "Awarded Agreement",
            "appointment": "Appointment",
            "accept": "Approvals",
            "approve": "Approvals",
            "approval": "Approvals",
            "award": "Award",
            "bids ": "Bids",
            "budget": "Budget",
            "closed session": "Closed Session",
            "conference with": "Closed Session",
            "conferencewith": "Closed Session",
            "consultant": "Consultant",
            "contract": "Contract",
            "discuss": "Discussion",
            "discussion": "Discussion",
            "election": "Election",
            "emergency": "Emergency",
            "event ": "Event",
            "events ": "Event",
            "fire": "Fire",
            "housing": "Housing",
            "introduce":"Introductions",
            "introduction":"Introductions",
            "lease ": "Lease",
            "license": "License",
            'memorandum': "Memorandum",
            "moratorium": "Moratorium",
            "notice": "Notice",
            "nuisance": "Nuisance",
            "ordinance": "Ordinance",
            "police": "Police",
            "presentation": "Presentation",
            "proclaim": "Proclamation",
            "proclamation": "Proclamation",
            "professional": "Professional Service Agreements",
            "program": "Program",
            "propose": "Proposal",
            "proposal": "Proposal",
            "presentation": "Presentation",
            "public hearing": "Public Hearing",
            "purchase": "Purchase",
            "recognition": "Presentation",
            "recogniz": "Presentation",
            "reject": "Reject",
            "report": "Report",
            "request ": "Request ",
            "resolution": "Resolution",
            "rescind": "Rescind",
            "retail": "Retail",
            "rfp": "Request for Proposal",
            "treasurer": "Treasurer",
            "study": "Study",
            "update": "Update"
        }

        count = 0

        # Fetch agenda data from MongoDB
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {"MeetingType": " City Council "},
                {'Date': {'$gte': date_threshold}}
            ]
        }).sort('Date', -1)

        for x in agenda_items:
            count += 1
            matching_topics = []

            # Check if the description or item type contains any of the topic keywords
            for keyword, topic in topic_mappings.items():
                if (
                    keyword in x.get('Description', '').lower()
                    or keyword in x.get('ItemType', '').lower()
                ):
                    if topic not in matching_topics:  # Avoid duplicates
                        matching_topics.append(topic)

            # If no matches were found, add "No Match"
            if not matching_topics:
                matching_topics.append("No Match")

            # Update the topic collection in MongoDB
            try:
                mongo.db.Agenda.update_one(
                    {'_id': x['_id']},  # Filter document (match by unique ID)
                    {
                        '$set': {  # Update or set fields in the document
                            "City": x.get('City'),
                            "County": x.get('County'),
                            "Date": x.get('Date'),
                            "Num": x.get('Num'),
                            "MeetingType": x.get('MeetingType'),
                            "ItemType": x.get('ItemType'),
                            "Description": x.get('Description'),
                            "Topics": matching_topics  # Store the list of matching topics
                        }
                    },
                    upsert=True  # Option for upsert
                )
            except Exception as e:
                print(f"Error updating document ID {x['_id']}: {e}")
sched = BackgroundScheduler(timezone='UTC')
sched.add_job(topic, 'interval', seconds=3600)
sched.start()

@app.route('/topicLink/<topic>', methods=['GET'])
def topic_details(topic):
    from bson.objectid import ObjectId  # Import for MongoDB object ID
    form = searchForm2()
    date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))

    # Retrieve the city from the query parameters
    city = request.args.get('city')
    city =' '+city+' '
    # Query agendas related to the given topic and city
    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'Topics': {'$regex': topic, '$options': 'i'}},  # Match topic (case-insensitive)
            {"City": city},  # Match city if provided
            {"Description": {"$ne": ""}},  # Ensure it's not an empty string
        ]
    }

    # If no city is provided, remove the city filter
    if not city:
        query['$and'] = [condition for condition in query['$and'] if "City" not in condition]

    # Fetch matching agendas
    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))

    # If no agendas are found, return a 404 error
    if not agendas:
        return "No agendas found for this topic and city.", 404

    # Render the template with the agendas
    return render_template('share.html', topic=topic, form=form, city=city, agendas=agendas)

@app.route('/cityLink/<city>', methods=['GET'])
def city_details(city):
    form = searchForm2()
    date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))

    # Retrieve the topic from the query parameters
    topic = request.args.get('topic')
    city = ' '+city+' '
    print(topic)
    print(city)
    # Query agendas related to the given topic and city
    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'Topics': {'$regex': topic, '$options': 'i'}},  # Match topic (case-insensitive)
            {"Description": {"$ne": ""}},  # Ensure it's not an empty string
            {'City': {'$regex': city, '$options': 'i'}},  # Match topic (case-insensitive)
        ]
    }

    # Fetch matching agendas
    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))

    # Count unique cities from the agenda items
    city_issue_counts = Counter([agenda.get('City', 'Unknown').strip() for agenda in agendas])
    unique_city_count = len(city_issue_counts)  # Total number of unique cities

    # Render the template with the results
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
    form = searchForm2()
    # Just print the value to verify that it comes through
    print(f"keyword value: {keyword}")  # Debug line

    date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))

    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'$text': {"$search": keyword}},
            {"Description": {"$ne": ""}},
        ]
    }

    # Fetch matching agendas
    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))

    # Count unique cities from the agenda items
    city_issue_counts = Counter(agenda.get('City', '').strip() for agenda in agendas)

    # Fetch geo information & create map
    geo_info = fetch_geo_info(city_issue_counts)
    folium_map = create_folium_map(geo_info)

    keyword = str(keyword) if topic else ''
    # Render the template with the results
    return render_template(
        'share.html',
        keyword=keyword,
        form=form,
        agendas=agendas,
        folium_map=folium_map._repr_html_(),
        city_issue_counts=city_issue_counts,
    )

@app.route('/descriptionCityLink/<keyword>', methods=['GET'])
def descriptionCity_details(keyword):
    form = searchForm2()
    # Just print the value to verify that it comes through
    print(f"keyword value: {keyword}")  # Debug line
    city = request.args.get('city')
    date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))

    query = {
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'$text': {"$search": keyword}},
            {"Description": {"$ne": ""}},  # Ensure it's not an empty string

        ]
    }

    # Fetch matching agendas
    agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))

    # Count unique cities from the agenda items
    city_issue_counts = Counter(agenda.get('City', '').strip() for agenda in agendas)

    # Fetch geo information & create map
    geo_info = fetch_geo_info(city_issue_counts)
    folium_map = create_folium_map(geo_info)

    keyword = str(keyword) if topic else ''
    # Render the template with the results
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
    from bson.objectid import ObjectId  # Import for MongoDB object ID
    date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))

    # Fetch agendas from MongoDB
    agendas = list(mongo.db.Agenda.find({
        '$and': [
            {'Date': {'$gte': date_threshold}},
            {'Topics': {'$regex': topic, '$options': 'i'}},  # Match topic (case-insensitive)
            {"Description": {'$not': {'$regex': "minute", '$options': 'i'}}},
            {"Description": {"$ne": ""}},  # Ensure it's not an empty string
            {"Description": {'$not': {'$regex': "public", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "warrant", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "flag salute", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "invocation", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "call to order", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "pledge of allegiance", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "roll call", '$options': 'i'}}},
            {"Description": {'$not': {'$regex': "check register", '$options': 'i'}}}
        ]
    }).sort('Date', -1))  # Sort by date in descending order

    if not agendas:
        return "Agenda not found", 404

    # Extract city matches & count occurrences
    city_issue_counts = Counter(agenda.get('City', '').strip() for agenda in agendas)

    # Fetch geo information & create map
    geo_info = fetch_geo_info(city_issue_counts)
    folium_map = create_folium_map(geo_info)
    # Save Folium map once, reuse filename


    return render_template(
        'share.html',
        folium_map=folium_map._repr_html_(),
        topic=topic,
        agendas=agendas,
        unique_city_count=len(city_issue_counts),  # Unique cities
        agenda_count=len(agendas),  # Total agenda items
        city_issue_counts=city_issue_counts
    )

@app.route('/', methods=['GET', 'POST'])
def httpsroute():
    return redirect("https://www.policyedge.net/index", code = 301)

def fetch_geo_info(city_issue_counts):
    """
    Fetch geo-location data from MongoDB and match it with city issue counts.
    """
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
    """
    Create a Folium map with circles and markers for each city.
    """
    folium_map = folium.Map(location=(34, -118), zoom_start=9, tiles="cartodbpositron", width=1000, height=475)

    for info in geo_info:
        city, state_id, county_name, lat, lon, issue_count, web_address = info

        # Add circle to the map
        folium.Circle(
            location=[lat, lon],
            popup=f"<a href='{web_address}' target='_blank'>{city} Agenda Link</a>",
            radius=float(issue_count) * 50,
            color='#5e7cff',
            fill=True,
            fill_color='#5e7cff'
        ).add_to(folium_map)

        # Add marker with city name and issue count
        folium.Marker(
            location=[lat, lon],
            icon=DivIcon(
                icon_size=(10, 10),
                icon_anchor=(15, 15),
                html=f'<div style="font-size: 10pt">{issue_count} {city}</div>'
            )
        ).add_to(folium_map)

    return folium_map

@app.route('/index', methods=['GET', 'POST'])
def index():
    form = chartForm()
    # Get the date three months before today
    date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))
    if request.method == 'GET':
        chosen='Fire'
    # Fetch agenda data from MongoDB
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {"MeetingType": {'$regex': "^ City Council $", '$options': 'i'}},  # Case-insensitive match
                {'Date': {'$gte': date_threshold}},
                {
                    '$and': [
                        {"Description": {'$not': {'$regex': "minute", '$options': 'i'}}},  # Exclude 'minute'
                        {"Description": {'$not': {'$regex': "warrant", '$options': 'i'}}}, # Exclude 'warrant'
                        {"Description": {"$ne": ""}},  # Ensure it's not an empty string
                    ]
                }
            ]
        }).sort('Date', -1)

        cities = [
            # Los Angeles County (LA)
            '', 'Agoura Hills', 'Alhambra', 'Arcadia', 'Artesia', 'Azusa', 'Baldwin Park', 'Bell',
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
            'Rolling Hills', 'Rolling Hills Estate', 'Rosemead', 'S Pasadena',
            'San Dimas', 'San Fernando', 'San Gabriel', 'San Marino', 'Santa Clarita',
            'Santa Fe Springs', 'Santa Monica', 'Sierra Madre', 'Signal Hill', 'South El Monte',
            'South Gate', 'Temple City', 'Torrance', 'Vernon', 'Walnut', 'West Covina',
            'West Hollywood', 'Westlake Village', 'Whittier',

            # Orange County (OC)
            'Aliso Viejo', 'Anaheim', 'Brea', 'Buena Park', 'Costa Mesa', 'Cypress', 'Dana Point',
            'Fountain Valley', 'Fullerton', 'Garden Grove', 'Huntington Beach', 'Irvine', 'La Habra', 'La Palma',
            'Laguna Beach', 'Laguna Hills', 'Laguna Niguel', 'Laguna Woods', 'Lake Forest',
            'Los Alamitos', 'Mission Viejo', 'Newport Beach', 'Orange', 'Placentia',
            'Rancho Santa Margarita', 'San Clemente', 'San Juan Capistrano', 'Santa Ana',
            'Seal Beach', 'Stanton', 'Tustin', 'Villa Park', 'Westminister', 'Yorba Linda',

            # Riverside County (RS)
            'Banning', 'Beaumont', 'Blythe', 'Calimesa', 'Canyon Lake', 'Cathedral City', 'Coachella',
            'Corona', 'Desert Hot Springs', 'Eastvale', 'Hemet', 'Indian Wells', 'Indio',
            'Jurupa Valley', 'Lake Elsinore', 'La Quinta', 'Menifee', 'Moreno Valley', 'Murrieta',
            'Norco', 'Palm Desert', 'Palm Springs', 'Perris', 'Rancho Mirage', 'Riverside',
            'San Jacinto', 'Temecula', 'Wildomar',

            # San Bernardino County (SB)
            'Adelanto', 'Apple Valley', 'Barstow', 'Big Bear Lake', 'Chino', 'Chino Hills',
            'Colton', 'Fontana', 'Grand Terrace', 'Hesperia', 'Highland', 'Loma Linda',
            'Montclair', 'Needles', 'Ontario', 'Rancho Cucamonga', 'Redlands', 'Rialto',
            'San Bernardino', 'Twentynine Palms', 'Upland', 'Victorville', 'Yucaipa', 'Yucca Valley',

            # San Diego County (SD)
            'Carlsbad', 'Chula Vista', 'Coronado', 'Del Mar', 'El Cajon', 'Encinitas', 'Escondido',
            'Imperial Beach', 'La Mesa', 'Lemon Grove', 'National City', 'Oceanside', 'Poway',
            'San Diego', 'San Marcos', 'Santee', 'Solana Beach', 'Vista'
        ]

        cities_matched = []

        # Initialize a dictionary to store city-specific agendas
        city_agendas = {city: {"agendas": [], "topic_counts": Counter()} for city in cities}

        for agenda in agenda_items:

            if chosen in agenda['Description']:
                city = agenda.get('City', '').strip()  # Remove extra spaces
                cities_matched.append(city)
            topics = agenda.get('Topics', [])

            if city in city_agendas:
                # Add agenda to the city's list
                city_agendas[city]["agendas"].append(agenda)

                # Count topics for this city
                if isinstance(topics, list):  # Check if topics is a list
                    city_agendas[city]["topic_counts"].update(topics)
                else:
                    city_agendas[city]["topic_counts"].update([topics])  # Handle single topic as a string
            else:
                print(f"City not found in the predefined list: {city}")

        city_issue_counts = Counter(cities_matched)
        geo_info = fetch_geo_info(city_issue_counts)
        folium_map = create_folium_map(geo_info)

        return render_template('index.html', folium_map=folium_map._repr_html_(), chosen=chosen, form=form, city_agendas=city_agendas, title="Policy Edge Tracking Agendas")
    elif request.method == 'POST' and request.form.get('chartSearch'):
        try:
            chose = request.form['chartSearch']
            chosen= "\""+chose+"\"" # Allows for exact phrases
            mongo.db.User.find_one_and_update({'username':'Esther'}, {'$push': {'searches':chosen}}, upsert = True)

        # Fetch agenda data from MongoDB
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'$text': {"$search": chosen}},
                    {"MeetingType": " City Council "},
                    {'Date': {'$gte': date_threshold}}
                ]
            }).sort('Date', -1)

            cities = [
                # Los Angeles County (LA)
                '', 'Agoura Hills', 'Alhambra', 'Arcadia', 'Artesia', 'Azusa', 'Baldwin Park', 'Bell',
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
                'West Hollywood', 'Westlake Village', 'Whittier',

                # Orange County (OC)
                'Aliso Viejo', 'Anaheim', 'Brea', 'Buena Park', 'Costa Mesa', 'Cypress', 'Dana Point',
                'Fountain Valley', 'Fullerton', 'Huntington Beach', 'Irvine', 'La Habra', 'La Palma',
                'Laguna Beach', 'Laguna Hills', 'Laguna Niguel', 'Laguna Woods', 'Lake Forest',
                'Los Alamitos', 'Mission Viejo', 'Newport Beach', 'Orange', 'Placentia',
                'Rancho Santa Margarita', 'San Clemente', 'San Juan Capistrano', 'Santa Ana',
                'Seal Beach', 'Stanton', 'Tustin', 'Villa Park', 'Westminster', 'Yorba Linda',

                # Riverside County (RS)
                'Banning', 'Beaumont', 'Blythe', 'Calimesa', 'Canyon Lake', 'Cathedral City', 'Coachella',
                'Corona', 'Desert Hot Springs', 'Eastvale', 'Hemet', 'Indian Wells', 'Indio',
                'Jurupa Valley', 'Lake Elsinore', 'La Quinta', 'Menifee', 'Moreno Valley', 'Murrieta',
                'Norco', 'Palm Desert', 'Palm Springs', 'Perris', 'Rancho Mirage', 'Riverside',
                'San Jacinto', 'Temecula', 'Wildomar',

                # San Bernardino County (SB)
                'Adelanto', 'Apple Valley', 'Barstow', 'Big Bear Lake', 'Chino', 'Chino Hills',
                'Colton', 'Fontana', 'Grand Terrace', 'Hesperia', 'Highland', 'Loma Linda',
                'Montclair', 'Needles', 'Ontario', 'Rancho Cucamonga', 'Redlands', 'Rialto',
                'San Bernardino', 'Twentynine Palms', 'Upland', 'Victorville', 'Yucaipa', 'Yucca Valley',

                # San Diego County (SD)
                'Carlsbad', 'Chula Vista', 'Coronado', 'Del Mar', 'El Cajon', 'Encinitas', 'Escondido',
                'Imperial Beach', 'La Mesa', 'Lemon Grove', 'National City', 'Oceanside', 'Poway',
                'San Diego', 'San Marcos', 'Santee', 'Solana Beach', 'Vista'
            ]

            # Initialize a dictionary to store city-specific agendas
            city_agendas = {city: [] for city in cities}
            cities_matched = []

            for agenda in agenda_items:
                city = agenda.get('City', '').strip()  # Remove extra spaces
                cities_matched.append(city)
                if city in city_agendas:
                    city_agendas[city].append(agenda)

        # Create frequency dictionary per city for folium map
            city_issue_counts = Counter(cities_matched)
            geo_info = fetch_geo_info(city_issue_counts)
            folium_map = create_folium_map(geo_info)
        except:
            flash('Sorry. No matches found')
    return render_template('descriptionLink.html', folium_map=folium_map._repr_html_(), form=form,chosen=chosen, city_agendas=city_agendas, title="Policy Edge Tracking Agendas")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if "username" in session:
        flash(session["username"])
        return redirect(url_for("index"))
    return render_template("register.html", title="Register for PolicyEdge")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if "username" in session:
        return redirect(url_for('index'))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        ##Check to see if user exist####
        username_found = mongo.db.User.find_one({"username": username })

        if username_found:
            username_check = username_found["username"]
            passwordcheck = username_found["password"]
            email= username_found["email"]
            subscription_check = username_found["subscriptionActive"]

            if bcrypt.checkpw(password.encode('utf-8'), passwordcheck):
                session['username'] = username_check
                session['subscribed'] = False
                session['email'] = email

                if subscription_check == True:
                    session['subscribed'] = True
                    return redirect(url_for('index'))
                else:
                    session['subscribed'] = False
                    return redirect(url_for('index'))
            else:
                if "username" in session:
                    return redirect(url_for("index"))
                flash('Wrong password')
                return render_template('login.html')
        else:
            flash('Username not found')
            return render_template('login.html')
    return render_template('login.html', title="Please Login")

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    for key in list(session.keys()):
        session.pop(key) #logs user out
    return redirect(url_for("index"))

@app.route('/subscription', methods=['GET'])# Subscription page is needed so existing users can re-subscribe.
def get_index():
    if "username" in session:
        return render_template('subscription.html', title='Re-subscribe to PolicyEdge')
    else:
        return redirect(url_for("login"))

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():#register link to this page to create both profile for User and Stripe User db
    stripe.api_key = stripe_keys['secret_key']

    username = request.form["username"]
    email = request.form["email"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    username_found = mongo.db.User.find_one({"username": username})#Checks if username exist
    email_found = mongo.db.User.find_one({"email": email})#Check if email exist
    stripe_email_found = mongo.db.stripe_user.find_one({"email": email})
    match = re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email)

    if username_found:
        flash('There already is a user by that name')
        return render_template('register.html')
    if email_found:
        flash('This email already exists in our user database')
        return render_template('register.html')
    if (' ' in username):
        flash('Please no whitespaces in username')
        return render_template('register.html')
    if (' ' in email):
        flash('Please no whitespaces in email address')
        return render_template('register.html')
    if match == None:
        flash('Please use a valid email address')
        return render_template('register.html')
    if stripe_email_found:
        flash('This email already exists in our Stripe database')
        return render_template('register.html')
    if password1 != password2:
        flash('Passwords should match!')
        return render_template('register.html')
    if len(password1) < 8:
        flash('Please make sure password is longer than 8 characters')
        return render_template('register.html')
    else:
        hashed = bcrypt.hashpw(password2.encode('utf-8'), bcrypt.gensalt())
        policy_user_input = {'username': username, 'email': email, 'password': hashed, 'stripe_id': [],'issues': [], 'agendaUnique_id': [], 'subscriptionActive': False}#Creates db Model including Subscription check
        stripe_user_input = {'username': username, 'email': email, 'stripeCustomerId' : [], 'stripeSubscriptionId':[]}
        mongo.db.User.insert_one(policy_user_input)
        mongo.db.stripe_user.insert_one(stripe_user_input)
        session['username'] = username
        session['email'] = email

    ############Checks if user has account with Stripe########
    noStripeId = mongo.db.User.find_one({'$and':[ {"email": session['email'] }, {"stripe_id" : {"$exists" : True, '$eq': [] }}]}) 

     ########The user was found not to have account with Stripe yet#####
    if noStripeId:
        checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[
            {
                'price': os.environ.get("STRIPE_MONTH_PRICE_ID"),
                'quantity': 1}
        ],
        mode='subscription',
        success_url=YOUR_DOMAIN +
        'success?session_id={CHECKOUT_SESSION_ID}', #GOD DAMN!
        cancel_url=YOUR_DOMAIN+ 'cancel',
        customer= stripe.Customer.create(      # Creates customer on Stripe
            description="First time subscriber",
            email=session['email']
            )
        )
        return redirect(checkout_session.url, code=303)

    else: #User has a Stripe account on mongo record db
        have_stripe_id = mongo.db.User.find_one({'$and':[ {"email": email }, {"stripe_id" : {"$exists" : True, '$type': 'array', '$size': 1} }]}) #Checks if user has account with Stripe
        placeholder=[]

        for x in have_stripe_id['stripe_id']:
            placeholder.append(x)
            j= str(placeholder)

        stripe_customer= j.replace("'",'').replace("[","").replace("]","").replace(",", "")

        checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[
            {
                'price': os.environ.get("STRIPE_MONTH_PRICE_ID"),
                'quantity': 1}
        ],
        mode='subscription',
        customer= stripe_customer, #places existing User Stripe_id to create checkout session
        success_url=YOUR_DOMAIN  +
        'success?session_id={CHECKOUT_SESSION_ID}', #GOD DAMN!
        cancel_url=YOUR_DOMAIN + 'cancel',
        )
        return redirect(checkout_session.url, code=303)

@app.route('/create-checkout-session2', methods=['POST'])
def create_checkout_session2(): # Second checkout is for existing users who want to re-subscribe
    stripe.api_key = stripe_keys['secret_key']

    if "username" in session:
        email = session["email"]

        noStripeId = mongo.db.User.find_one({'$and':[ {"email": email }, {"stripe_id" : {"$exists" : True, '$eq': [] }}]}) #Checks if user has account with Stripe

        if noStripeId:
            checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': os.environ.get("STRIPE_MONTH_PRICE_ID"),
                    'quantity': 1}
            ],
            mode='subscription',
            success_url=YOUR_DOMAIN +
            'success?session_id={CHECKOUT_SESSION_ID}', #GOD DAMN!
            cancel_url=YOUR_DOMAIN+ 'cancel',
            customer=stripe.Customer.create(
                description="First time Stripe User",
                email= email,
            )
            )
            return redirect(checkout_session.url, code=303)

        else:
            have_stripe_id = mongo.db.User.find_one({'$and':[ {"email": email }, {"stripe_id" : {"$exists" : True, '$type': 'array', '$size': 1} }]}) #Checks if user has account with Stripe
            placeholder=[]

            for x in have_stripe_id['stripe_id']:
                placeholder.append(x)
                j= str(placeholder)

            stripe_customer= j.replace("'",'').replace("[","").replace("]","").replace(",", "")

            checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price': os.environ.get("STRIPE_MONTH_PRICE_ID"),
                    'quantity': 1}
            ],
            mode='subscription',
            customer= stripe_customer, #places existing user_id to create proper checkout session
            success_url=YOUR_DOMAIN  +
            'success?session_id={CHECKOUT_SESSION_ID}', #GOD DAMN!
            cancel_url=YOUR_DOMAIN + 'cancel',
            )
            return redirect(checkout_session.url, code=303)
    else:
        return redirect(url_for("login"))


@app.route('/create-portal-session', methods=['POST'])
def customer_portal():
    stripe.api_key = stripe_keys['secret_key']

    checkout_session_id = request.form.get('session_id')
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    return_url = YOUR_DOMAIN

    portalSession = stripe.billing_portal.Session.create(
        customer=checkout_session.customer,
        return_url=return_url,
    )
    return redirect(portalSession.url, code=303)

@app.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    request_data = json.loads(request.data)
    if webhook_secret:
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
            payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e

        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']

    if event_type == 'checkout.session.completed':
        print("🔔 Payment succeeded!")

    elif event_type == 'customer.created':
        print('Customer created %s', event.id)
        print(data.object)
        mongo.db.User.find_one_and_update({'email':{ "$regex" :data.object.email , "$options" : "i" }}, {'$push': {'stripe_id':data.object.id}}) #Regex is used to ignore lower case uppercase letters
        mongo.db.stripe_user.find_one_and_update({'email':{ "$regex" :data.object.email , "$options" : "i" }}, {'$push': {'stripeCustomerId':data.object.id}})

    elif event_type == 'customer.subscription.created':
        print('Subscription created %s', event.id)
        print(data.object)
        mongo.db.stripe_user.find_one_and_update({'stripeCustomerId': data.object.customer}, {'$push': {'stripeSubscriptionId':data.object.id}})
        mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': True}})

    elif event_type == 'customer.subscription.updated':
        print('Subscription updated %s', event.id)
        print(data.object)
        if data.object.status == 'cancelled':
            mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': False}})
        elif data.object.status == 'past_due':
            mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': False}})
        elif data.object.status == 'unpaid':
            mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': False}})
        elif data.object.status == 'active':
            mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': True}})
        elif data.object.status == 'trialing':
            mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': True}})
        elif data.object.status == 'incomplete':
            pass

    elif event_type == 'customer.subscription.deleted':
        print('Subscription canceled: %s', event.id)
        print(data.object)
        mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': False}})

    return jsonify({'status': 'success'})

@app.route('/search')
def search():
    form = searchForm2()
    return render_template('search.html',form=form,title='Search')

@app.route('/results', methods=['GET', 'POST'])
def results():
    form = searchForm2(request.form)
    if request.method == 'POST':  # Handle form submission
        primeKey = form.primary_search.data.strip()
        start_date = form.startdate_field.data
        end_date = form.enddate_field.data

        today = date.today()  # Ensure today is a date object
        date_threshold = int((date.today() + relativedelta(weeks=-2)).strftime('%Y%m%d'))

        start = int(start_date.strftime('%Y%m%d')) if start_date else int((date.today() + relativedelta(weeks=-52)).strftime('%Y%m%d')) #if no date goes back one year
        end = int(end_date.strftime('%Y%m%d')) if end_date else int(today.strftime('%Y%m%d'))
        criteria = form.select.data
        filters = []

        criteria_nicknames = {
            'LA County': "LA",
            'Orange County': "OC",
            'Riverside County': "RS",
            'San Diego County': "SD",
            'San Bernardino County': "SB",
            'LA Committees': "LACM",
            'Long Beach Committees': "LBCM"
        }

        # Build filters based on selected criteria
        if criteria == 'Issue':
            filters.append({'$text': {"$search": primeKey}})
        elif criteria in criteria_nicknames:
            filters.append({'$text': {"$search": primeKey}})  # Ensure keyword is used
            # Exception handling for LACM and LBCM
            if criteria in ['LA Committees', 'Long Beach Committees']:
                #criteria=' '+criteria+' '
                county = ' LA County '
                filters.append({'County': {'$regex': county, '$options': 'i'}})  # Default to LA County
                selected_city_field = f"select{criteria_nicknames[criteria].replace(' ', '')}"  # Dynamic form field match
                selected_city = getattr(form, selected_city_field).data  # Get data from form
                selected_city = ' '+selected_city+' '
                if selected_city:  # If a city is selected, add it to the filter
                    filters.append({'MeetingType': {'$regex': selected_city, '$options': 'i'}})
            else:
                filters.append({'County': {'$regex': criteria, '$options': 'i'}})  # Location-based filtering
                selected_city_field = f"select{criteria_nicknames[criteria].replace(' ', '')}"  # Dynamic form field match
                selected_city = getattr(form, selected_city_field).data  # Get data from form
                if selected_city:  # If a city is selected, add it to the filter
                    filters.append({'City': {'$regex': selected_city, '$options': 'i'}})

        # Add date range filters
        if start and end:
            filters.append({'Date': {'$gte': start, '$lte': end}})
        elif start:
            filters.append({'Date': {'$gte': start}})
        elif end:
            filters.append({'Date': {'$lte': end}})

        # Query the database once
        agenda_list = list(mongo.db.Agenda.find({'$and': filters}).sort('Date', -1).limit(300))
        # Process the agenda data and create city matches
        cities_matched = []
        cities = [
            # Los Angeles County (LA)
            '', 'Agoura Hills', 'Alhambra', 'Arcadia', 'Artesia', 'Azusa', 'Baldwin Park', 'Bell',
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
            'Rolling Hills', 'Rolling Hills Estate', 'Rosemead', 'S Pasadena',
            'San Dimas', 'San Fernando', 'San Gabriel', 'San Marino', 'Santa Clarita',
            'Santa Fe Springs', 'Santa Monica', 'Sierra Madre', 'Signal Hill', 'South El Monte',
            'South Gate', 'Temple City', 'Torrance', 'Vernon', 'Walnut', 'West Covina',
            'West Hollywood', 'Westlake Village', 'Whittier',

            # Orange County (OC)
            'Aliso Viejo', 'Anaheim', 'Brea', 'Buena Park', 'Costa Mesa', 'Cypress', 'Dana Point',
            'Fountain Valley', 'Fullerton', 'Garden Grove', 'Huntington Beach', 'Irvine', 'La Habra', 'La Palma',
            'Laguna Beach', 'Laguna Hills', 'Laguna Niguel', 'Laguna Woods', 'Lake Forest',
            'Los Alamitos', 'Mission Viejo', 'Newport Beach', 'Orange', 'Placentia',
            'Rancho Santa Margarita', 'San Clemente', 'San Juan Capistrano', 'Santa Ana',
            'Seal Beach', 'Stanton', 'Tustin', 'Villa Park', 'Westminister', 'Yorba Linda',

            # Riverside County (RS)
            'Banning', 'Beaumont', 'Blythe', 'Calimesa', 'Canyon Lake', 'Cathedral City', 'Coachella',
            'Corona', 'Desert Hot Springs', 'Eastvale', 'Hemet', 'Indian Wells', 'Indio',
            'Jurupa Valley', 'Lake Elsinore', 'La Quinta', 'Menifee', 'Moreno Valley', 'Murrieta',
            'Norco', 'Palm Desert', 'Palm Springs', 'Perris', 'Rancho Mirage', 'Riverside',
            'San Jacinto', 'Temecula', 'Wildomar',

            # San Bernardino County (SB)
            'Adelanto', 'Apple Valley', 'Barstow', 'Big Bear Lake', 'Chino', 'Chino Hills',
            'Colton', 'Fontana', 'Grand Terrace', 'Hesperia', 'Highland', 'Loma Linda',
            'Montclair', 'Needles', 'Ontario', 'Rancho Cucamonga', 'Redlands', 'Rialto',
            'San Bernandino', 'Twentynine Palms', 'Upland', 'Victorville', 'Yucaipa', 'Yucca Valley',

            # San Diego County (SD)
            'Carlsbad', 'Chula Vista', 'Coronado', 'Del Mar', 'El Cajon', 'Encinitas', 'Escondido',
            'Imperial Beach', 'La Mesa', 'Lemon Grove', 'National City', 'Oceanside', 'Poway',
            'San Diego', 'San Marcos', 'Santee', 'Solana Beach', 'Vista'
        ]

        city_agendas = {city: {"agendas": [], "issue_counts": Counter()} for city in cities}
        for agenda in agenda_list:
            if primeKey in agenda.get('Description', ''):
                city = agenda.get('City', '').strip()
                cities_matched.append(city)
            city = agenda.get('City', '').strip()  # Remove extra spaces

            if city in city_agendas:
                # Add agenda to the city's list
                city_agendas[city]["agendas"].append(agenda)

                # Count topics for this city
                if isinstance(city, list):  # Check if topics is a list
                    city_agendas[city]["issue_counts"].update(city)
                else:
                    city_agendas[city]["issue_counts"].update([city])  # Handle single topic as a string
            else:
                print(f"City not found in the predefined list: {city}")

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

@app.template_filter('aTime')
def int2date(agDate: int) -> date:
    agDate=(str(agDate))
    dt = datetime.strptime(agDate, '%Y%m%d')
    return (dt.strftime('%B %d, %Y'))

@app.route('/savedIssues', methods=['GET', 'POST'])
def savedIssues():
    if "username" in session:
        if mongo.db.User.find_one({'$and':[ {'username': session['username']} ,{'subscriptionActive': True}]}):
            #####Prerequisites########
            a = date.today()+ relativedelta(days=30)
            today=int(a.strftime('%Y%m%d')) #add 30 so new agendas will be caught
            c = date.today() + relativedelta(days=-60) #################CHANGE BACK TO -7##################
            today_1month= int(c.strftime('%Y%m%d'))

            form = monitorListform2()
            user = session["username"]
        
            if request.method == 'GET':

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agendaa.append(z)

                return render_template('savedIssues.html', issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription List')
        
            elif request.method == 'POST' and request.form['select'] == 'Issue' and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": '',
                    "Committee": '',
                    "County": '',
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)

                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form['select'] == 'Issue' and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": '',
                    "Committee": '',
                    "County": '',
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectLA') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectLA')
                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectLA') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectLA')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectOC') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectOC')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder


                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectOC') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectOC')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectRS') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectRS')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectRS') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectRS')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectSB') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectSB')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectSB') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectSB')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectSD') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectSD')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectSD') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= request.form.get('select')
                city= request.form.get('selectSD')

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": '',
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectLACM') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= 'LA County'
                city= 'Los Angeles'
                committee = request.form['selectLACM']
                #####Adds key to Issues########

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": committee,
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)
                ######Returns user saved issues#####
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder


                ######Returns matching agendas from for loop below#####
                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectLACM') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= 'LA County'
                city= 'Los Angeles'
                committee = request.form['selectLACM']

                #####Adds key to Issues########

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": committee,
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)
                ######Returns user saved issues#####
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder


                ######Returns matching agendas from for loop below#####
                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectLBCM') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Add':
                primeKey = request.form['primary_search']
                county= 'LA County'
                city= 'Long Beach'
                committee = request.form['selectLBCM']
                #####Adds key to Issues########

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": committee,
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)
                ######Returns user saved issues#####
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder


                ######Returns matching agendas from for loop below#####
                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        
            elif request.method == 'POST' and request.form.get('selectLBCM') and request.form['primary_search'] and request.form.get('select') and request.form['action'] == 'Delete':
                primeKey = request.form['primary_search']
                county= 'LA County'
                city= 'Long Beach'
                committee = request.form['selectLBCM']

                #####Adds key to Issues########

                CompleteIssue = {
                    "searchWord": primeKey,
                    "City": city,
                    "Committee": committee,
                    "County": county,
                }
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)
                ######Returns user saved issues#####
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.Committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder

                ######Returns matching agendas from for loop below#####
                agendaa=[]
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date',-1)

                    for z in Multiquery:
                        agendaa.append(z)
                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Subscription Add List')
        else:
            return render_template('noSubscription.html')
    else:
        return redirect(url_for("login"))

@app.route('/success')
def success():
    return render_template("success.html", title='PolicyEdge subscription successful')

@app.route('/cancel')
def cancelled():
    return render_template("cancel.html", title='Cancel PolicyEdge subscription')

@app.route('/noSubscription')
def noSubscription():
    return render_template("noSubscription.html",title='PolicyEdge subscription not active')

@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about.html', title="About Policy Edge creator Sergio Preciado" )

@app.route('/termsofservice', methods=['GET', 'POST'])
def termsofservice():
    return render_template('termsofservice.html', title='Terms of Service')

@app.route('/privacypolicy', methods=['GET', 'POST'])
def privacypolicy():
    return render_template('privacypolicy.html', title='Privacy Policy')

@app.route('/losangeles', methods=['GET'])
def losangeles():
    if request.method == 'GET':
        # Get the date from one week ago
        one_week_ago = date.today() + relativedelta(weeks=-16)
        one_week_ago_str = one_week_ago.strftime('%Y%m%d')
        one_week_ago_int = int(one_week_ago_str)
        print(one_week_ago_int)

        # MongoDB query to get agendas from the last week, filtered by "City Council" and "LA County"
        try:
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'Date': {'$gte': one_week_ago_int}},
                    {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                    {'County': {'$regex': 'LA County', '$options': 'i'}},
                    {"$expr": { "$gt": [ { "$strLenCP": "$Description" }, 5 ] }},
                    {
                        '$and': [
                            { "Description": { '$not': { '$regex': "minute" } } },
                            { "Description": { '$not': { '$regex': "warrant" } } }
                        ]
                    }                ]
            }).sort('Date', -1)
        except Exception as e:
            return f"Error querying database: {e}", 500

        # Define the list of cities
        cities = [
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
        ]

        # Initialize a dictionary to store city-specific agendas
        city_agendas = {city: [] for city in cities}

        # Populate the city agendas by iterating over the agenda items
        for agenda in agenda_items:
            city = agenda.get('City', '').strip()  # Remove extra spaces
            if city in city_agendas:
                city_agendas[city].append(agenda)

        print(city_agendas)
        # Rendering the template and passing the data dynamically using **city_agendas
        return render_template('losangeles.html',city_agendas=city_agendas,title="PolicyEdge agenda tracking monitoring Los Angeles County Search Results")



@app.route('/orange', methods=['GET', 'POST'])
def orange():
    if request.method == 'GET':
        # Get the date from one week ago
        one_week_ago = date.today() + relativedelta(weeks=-16)
        one_week_ago_str = one_week_ago.strftime('%Y%m%d')
        one_week_ago_int = int(one_week_ago_str)
        print(one_week_ago_int)

        # MongoDB query to get agendas from the last week, filtered by "City Council" and "LA County"
        try:
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'Date': {'$gte': one_week_ago_int}},
                    {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                    {'County': {'$regex': 'Orange County', '$options': 'i'}},
                    {"$expr": { "$gt": [ { "$strLenCP": "$Description" }, 5 ] }},
                    {
                        '$and': [
                            { "Description": { '$not': { '$regex': "minute" } } },
                            { "Description": { '$not': { '$regex': "warrant" } } }
                        ]
                    }                ]
            }).sort('Date', -1)
        except Exception as e:
            return f"Error querying database: {e}", 500

        # Define the list of cities
        cities = [
            'Anaheim', 'Brea', 'Buena Park', 'Coasta Mesa', 'Cypress', 'Dana Point',
            'Fountain Valley', 'Fullerton', 'Huntington Beach', 'Irvine', 'La Habra',
            'La Palma', 'Laguna Beach', 'Laguna Hills', 'Laguna Niguel', 'Laguna Woods',
            'Lake Forest', 'Los Alamitos', 'Mission Viejo', 'Newport Beach', 'Orange',
            'Placentia', 'Rancho Santa Margarita', 'San Clemente', 'San Juan Capistrano',
            'Santa Ana', 'Seal Beach', 'Stanton', 'Tustin', 'Villa Park', 'Westminister',
            'Yorba Linda'
        ]

        # Initialize a dictionary to store city-specific agendas
        city_agendas = {city: [] for city in cities}

        # Populate the city agendas by iterating over the agenda items
        for agenda in agenda_items:
            city = agenda.get('City', '').strip()  # Remove extra spaces
            if city in city_agendas:
                city_agendas[city].append(agenda)

        # Rendering the template and passing the data dynamically using **city_agendas
        return render_template('orange.html',city_agendas=city_agendas,title="PolicyEdge agenda tracking monitoring all of Orange County")



@app.route('/riverside', methods=['GET', 'POST'])
def riverside():
    if request.method == 'GET':
        # Get the date from one week ago
        one_week_ago = date.today() + relativedelta(weeks=-16)
        one_week_ago_str = one_week_ago.strftime('%Y%m%d')
        one_week_ago_int = int(one_week_ago_str)
        print(one_week_ago_int)

        # MongoDB query to get agendas from the last week, filtered by "City Council" and "LA County"
        try:
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'Date': {'$gte': one_week_ago_int}},
                    {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                    {'County': {'$regex': 'Riverside County', '$options': 'i'}},
                    {"$expr": { "$gt": [ { "$strLenCP": "$Description" }, 5 ] }},
                    {
                        '$and': [
                            { "Description": { '$not': { '$regex': "minute" } } },
                            { "Description": { '$not': { '$regex': "warrant" } } }
                        ]
                    }                ]
            }).sort('Date', -1)
        except Exception as e:
            return f"Error querying database: {e}", 500

        # Define the list of cities
        cities = [
            'Banning', 'Beaumont', 'Blythe', 'Calimesa', 'Canyon Lake', 'Cathedral City',
            'Coachella', 'Corona', 'Desert Hot Springs', 'Eastvale', 'Hemet', 'Indian Wells',
            'Indio', 'Jurupa Valley', 'Lake Elsinore', 'La Quinta', 'Menifee', 'Moreno Valley',
            'Murrieta', 'Norco', 'Palm Desert', 'Palm Springs', 'Perris', 'Rancho Mirage',
            'Riverside', 'San Jacinto', 'Temecula', 'Wildomar'
        ]

        # Initialize a dictionary to store city-specific agendas
        city_agendas = {city: [] for city in cities}

        # Populate the city agendas by iterating over the agenda items
        for agenda in agenda_items:
            city = agenda.get('City', '').strip()  # Remove extra spaces
            if city in city_agendas:
                city_agendas[city].append(agenda)

        print(city_agendas)
        # Rendering the template and passing the data dynamically using **city_agendas
        return render_template('riverside.html',city_agendas=city_agendas,title="PolicyEdge agenda tracking monitoring all of Riverside County")

@app.route('/sanbernandino', methods=['GET', 'POST'])
def sanbernandino():
    if request.method == 'GET':
        # Get the date from one week ago
        one_week_ago = date.today() + relativedelta(weeks=-16)
        one_week_ago_str = one_week_ago.strftime('%Y%m%d')
        one_week_ago_int = int(one_week_ago_str)
        print(one_week_ago_int)

        # MongoDB query to get agendas from the last week, filtered by "City Council" and "LA County"
        try:
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'Date': {'$gte': one_week_ago_int}},
                    {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                    {'County': {'$regex': 'San Bernandino County', '$options': 'i'}},
                    {"$expr": { "$gt": [ { "$strLenCP": "$Description" }, 5 ] }},
                    {
                        '$and': [
                            { "Description": { '$not': { '$regex': "minute" } } },
                            { "Description": { '$not': { '$regex': "warrant" } } }
                        ]
                    }                ]
            }).sort('Date', -1)
        except Exception as e:
            return f"Error querying database: {e}", 500

        # Define the list of cities
        cities = [
            'Adelanto', 'Apple Valley', 'Barstow', 'Big Bear Lake', 'Chino', 'Chino Hills',
            'Colton', 'Fontana', 'Grand Terrace', 'Hesperia', 'Highland', 'Loma Linda',
            'Montclair', 'Needles', 'Ontario', 'Rancho Cucamonga', 'Redlands', 'Rialto',
            'San Bernandino', 'Twnentynine Palms', 'Upland', 'Victorville', 'Yucaipa',
            'Yucca Valley'
        ]

        # Initialize a dictionary to store city-specific agendas
        city_agendas = {city: [] for city in cities}

        # Populate the city agendas by iterating over the agenda items
        for agenda in agenda_items:
            city = agenda.get('City', '').strip()  # Remove extra spaces
            if city in city_agendas:
                city_agendas[city].append(agenda)

        print(city_agendas)
        # Rendering the template and passing the data dynamically using **city_agendas
        return render_template('sanbernandino.html',city_agendas=city_agendas,title="PolicyEdge agenda tracking monitoring all of San Bernandino County")

@app.route('/sandiego', methods=['GET', 'POST'])
def sandiego():
    if request.method == 'GET':
        # Get the date from one week ago
        one_week_ago = date.today() + relativedelta(weeks=-16)
        one_week_ago_str = one_week_ago.strftime('%Y%m%d')
        one_week_ago_int = int(one_week_ago_str)
        print(one_week_ago_int)

        # MongoDB query to get agendas from the last week, filtered by "City Council" and "LA County"
        try:
            agenda_items = mongo.db.Agenda.find({
                '$and': [
                    {'Date': {'$gte': one_week_ago_int}},
                    {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                    {'County': {'$regex': 'San Diego County', '$options': 'i'}},
                    {"$expr": { "$gt": [ { "$strLenCP": "$Description" }, 5 ] }},
                    {
                        '$and': [
                            { "Description": { '$not': { '$regex': "minute" } } },
                            { "Description": { '$not': { '$regex': "warrant" } } }
                        ]
                    }                ]
            }).sort('Date', -1)
        except Exception as e:
            return f"Error querying database: {e}", 500

        # Define the list of cities
        cities = [
            'Carlsbad', 'Chula Vista', 'Coronado', 'Del Mar', 'El Cajon', 'Encinitas',
            'Escondido', 'Imprial Beach', 'La Mesa', 'Lemon Grove', 'National City',
            'Oceanside', 'Poway', 'San Diego', 'San Marcos', 'Santee', 'Solana Beach', 'Vista'
        ]

        # Initialize a dictionary to store city-specific agendas
        city_agendas = {city: [] for city in cities}

        # Populate the city agendas by iterating over the agenda items
        for agenda in agenda_items:
            city = agenda.get('City', '').strip()  # Remove extra spaces
            if city in city_agendas:
                city_agendas[city].append(agenda)

        print(city_agendas)
        # Rendering the template and passing the data dynamically using **city_agendas
        return render_template('sandiego.html',city_agendas=city_agendas,title="PolicyEdge agenda tracking monitoring all of San Bernandino County")

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html', title="404"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html', title="500"), 500
    
if __name__ == '__main__':
    app.run(debug = False)













from flask_pymongo import PyMongo
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, json, g
from forms import searchForm, monitorListform, chartForm
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
import folium
from folium.features import DivIcon

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

def check4Issues2email():
    with app.app_context():
    ##########Date###############
        a = date.today()
        today= int(a.strftime('%Y%m%d'))

    ##########User roundup###############
        all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1, 'agendaUnique_id':1, 'email':1, 'subscriptionActive':1, 'issues':1})#Creates list af all emails and usernames for sequence

        for x in all_users: #For each instance of a user
            email=x['username']#Grabs email for new schedEmail.html
            if x['subscriptionActive'] == True: #Checks to see if user is subscribed

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
                        msg.attach(filename="logo.png", content_type="image/png", data=fp.read(),
                                    disposition="inline", headers=[['Content-ID', '<voucher_png>']])
                    mail.send(msg)
            else:
                pass

sched = BackgroundScheduler(timezone='UTC')
sched.add_job(check4Issues2email, 'interval', seconds=3600)
sched.start()

@app.route('/', methods=['GET', 'POST'])
def httpsroute():
    return redirect("https://www.policyedge.net/index", code = 301)

@app.route('/index', methods=['GET', 'POST'])
def index():
    form = chartForm()
    ##Three months before#####
    c = date.today() + relativedelta(weeks=-4)
    threemonthBefore=int(c.strftime('%Y%m%d'))

    #######TOPIC SELECTION##########
    chosen = "Cannabis"
    target='City Count'

    treMonthMtch=[]
    issueText=[]
    agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen }}, {"MeetingType":" City Council "}, { 'Date':{'$gte':threemonthBefore}}]}).sort('Date',-1)
    for x in agendaa:
        sp=x['City'].strip() #Gets rid of spacing issue with some cities
        treMonthMtch.append(sp)
        y=str(x["Description"])
        issueText.append(x)

    issuePerCity= Counter(treMonthMtch)# Creates key:value pair per city to part w/ issuePerCity.keys()
    geo=[]
    for i,v in issuePerCity.items():
        check=mongo.db.geoLoc.find({'city':i}, {'_id': 0})
        for y in check:
            if y['city'] in i:
                geo.append('"'+y['city']+'"'+','+'"'+y['state_id']+'"'+','+'"'+y['county_name']+'"'+','+'"'+str(y['lat'])+'"'+','+'"'+str(y['lng'])+'"'+','+'"'+str(v)+'"'+','+'"'+y['webAdress']+'"')

    #######Box 1##########
    geo=(str(geo).replace("',","),").replace("'","(").replace("(]",")])").replace("[(","([("))
    df = pd.DataFrame(eval(geo), columns=['city', 'state_id', 'county_name', 'lat', 'lon','ISSUECONT','webAdress'], dtype=str)
    folium_map = folium.Map(location=(34, -118), zoom_start=9, tiles="cartodbpositron",width=800, height=475)

    for i in range(len(issuePerCity)-1):#use -1 otherwise database has issue with one extra value
        folium.Circle(
            location=[df['lat'][i], df['lon'][i]],
            popup= "<a href=%s target='_blank'>%s Agenda Link</a>" % (df['webAdress'][i],df['city'][i]),
            radius=float(df['ISSUECONT'][i])*50,
            color='#5e7cff',
            fill=False,
            fill_color='#5e7cff'
        ).add_to(folium_map)

        folium.map.Marker([df['lat'][i], df['lon'][i]],
                            icon=DivIcon(
                                icon_size=(10 ,10),
                                icon_anchor=(15,15),
                                html=f'<div style="font-size: 10pt">%s %s</div>' % (df['ISSUECONT'][i],df['city'][i]),
                            )
                            ).add_to(folium_map)
    if request.method == 'GET':
        return render_template('index.html', folium_map=folium_map._repr_html_(), form=form,target=target ,chosen=chosen, issueTexts=issueText, title="Policy Edge Tracking Agendas")
    elif request.method == 'POST' and request.form.get('chartSearch'):
        try:
            chose = request.form['chartSearch']
            target='City Count'
            chosen= "\""+chose+"\"" # Allows for exact phrases
            mongo.db.User.find_one_and_update({'username':'Esther'}, {'$push': {'searches':chosen}}, upsert = True)
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, {"MeetingType": " City Council "}, { 'Date':{'$gte':threemonthBefore}}]}).sort('Date',-1)
            ####Words taken out for NLTK#######
            issueText=[]
            treMonthMtch=[]
            ####### TABLE 1##########
            for x in agendaa:
                sp=x['City'].strip()
                treMonthMtch.append(sp)
                issueText.append(x)

            issuePerCity= Counter(treMonthMtch)# Creates key:value pair per city to part w/ issuePerCity.keys()
            Cities=[]
            Cnt=[]
            geo=[]
            for i,v in issuePerCity.items():
                Cities.append(i)# split used because of city gap before after name
                Cnt.append(v)
                check=mongo.db.geoLoc.find({'city':i}, {'_id': 0, "population": 0})
                for y in check:
                    if y['city'] in i:
                        geo.append('"'+y['city']+'"'+','+'"'+y['state_id']+'"'+','+'"'+y['county_name']+'"'+','+'"'+str(y['lat'])+'"'+','+'"'+str(y['lng'])+'"'+','+'"'+str(v)+'"'+','+'"'+y['webAdress']+'"')

            #######Box 1##########
            geo=(str(geo).replace("',","),").replace("'","(").replace("(]",")])").replace("[(","([("))
            df = pd.DataFrame(eval(geo), columns=['city', 'state_id', 'county_name', 'lat', 'lon','ISSUECONT','webAdress'], dtype=str)
            folium_map = folium.Map(location=(34, -118), zoom_start=9, tiles="cartodbpositron",width=800, height=475)

            for i in range(len(issuePerCity)-1):#use -1 otherwise database has issue with one extra value
                folium.Circle(
                    location=[df['lat'][i], df['lon'][i]],
                    popup= "<a href=%s target='_blank'>%s Agenda Link</a>" % (df['webAdress'][i],df['city'][i]),
                    radius=float(df['ISSUECONT'][i])*50,
                    color='#5e7cff',
                    fill=False,
                    fill_color='#5e7cff'
                ).add_to(folium_map)

                folium.map.Marker([df['lat'][i], df['lon'][i]],
                                    icon=DivIcon(
                                        icon_size=(10 ,10),
                                        icon_anchor=(15,15),
                                        html=f'<div style="font-size: 10pt">%s %s</div>' % (df['ISSUECONT'][i],df['city'][i]),
                                    )
                                    ).add_to(folium_map)
        except:
            flash('Sorry. No matches found')
            return redirect(url_for("index"))
        return render_template('index.html', form=form, folium_map=folium_map._repr_html_(),chosen=chosen, issueTexts=issueText, title="Policy Edge Tracking Agendas Map search")



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
    match = re.match('^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email)

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
    form = searchForm()
    return render_template('search.html',form=form,title='Search')

@app.route('/results', methods=['GET', 'POST'])
def results():
    if request.method == 'POST':
        form = searchForm()
        primeKey = request.form['primary_search']
        start_date = request.form['startdate_field']
        end_date = request.form['enddate_field']

        a = date.today()
        today=int(a.strftime('%Y%m%d'))
        start_year = str(start_date[0:4])
        start_month = str(start_date[5:7])
        start_day = str(start_date[8:10])
        end_year = str(end_date[0:4])
        end_month = str(end_date[5:7])
        end_day = str(end_date[8:10])
        start = (start_year+start_month+start_day)
        end = (end_year+end_month+end_day)

    ##Issue onlys###
        if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']:
            agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": primeKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('City').sort('Date',-1)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']=="":# Allows user to not input End date ==today
            agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": primeKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date',-1)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        if request.form['select'] == 'Issue' and request.form['startdate_field']=="" and request.form['enddate_field']:# Allows user to not input End date ==today
            agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": primeKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date',-1)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        if request.form['select'] == 'Issue' and request.form['startdate_field'] =="" and request.form['enddate_field']=="":# Allows user to not input date
            agenda = mongo.db.Agenda.find({ '$text': { "$search": primeKey}}).sort('Date',-1)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")

        ##Committee+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLA')=="" and request.form.get('selectOC')=="" and request.form.get('selectRS')=="" and request.form.get('selectSB')=="" and request.form.get('selectSD')=="" and request.form.get('selectLACM')=="" and request.form.get('selectLBCM')=="":
            county= request.form.get('select')
            city= request.form.get('selectLA')
            if county =='LA Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            if county =='Long Beach Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ '$text': { "$search": primeKey}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLA')=="" and request.form.get('selectOC')=="" and request.form.get('selectRS')=="" and request.form.get('selectSB')=="" and request.form.get('selectSD')=="" and request.form.get('selectLACM')=="" and request.form.get('selectLBCM')=="":
            county= request.form.get('select')
            city= request.form.get('selectLA')
            if county =='LA Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{ 'Date':{'$lte':today, '$gte':int(start)}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            if county =='Long Beach Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{ 'Date':{'$lte':today, '$gte':int(start)}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLA')=="" and request.form.get('selectOC')=="" and request.form.get('selectRS')=="" and request.form.get('selectSB')=="" and request.form.get('selectSD')=="" and request.form.get('selectLACM')=="" and request.form.get('selectLBCM')=="":
            county= request.form.get('select')
            city= request.form.get('selectLA')
            if county =='LA Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{ 'Date':{'$lte':today, '$gte':int(end)}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            if county =='Long Beach Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{ 'Date':{'$lte':today, '$gte':int(end)}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLA')=="" and request.form.get('selectOC')=="" and request.form.get('selectRS')=="" and request.form.get('selectSB')=="" and request.form.get('selectSD')=="" and request.form.get('selectLACM')=="" and request.form.get('selectLBCM')=="":
            county= request.form.get('select')
            city= request.form.get('selectLA')
            if county =='LA Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            if county =='Long Beach Committees':
                county='LA County'
                city='Los Angeles'
                agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}},{ '$text': { "$search": primeKey}},  {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
                return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##LACounty+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLA'):
            county= request.form.get('select')
            city= request.form.get('selectLA')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLA'):
            county= request.form.get('select')
            city= request.form.get('selectLA')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLA'):
            county= request.form.get('select')
            city= request.form.get('selectLA')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLA'):
            county= request.form.get('select')
            city= request.form.get('selectLA')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##OrangeCounty+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectOC'):
            county= request.form.get('select')
            city= request.form.get('selectOC')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectOC'):
            county= request.form.get('select')
            city= request.form.get('selectOC')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectOC'):
            county= request.form.get('select')
            city= request.form.get('selectOC')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectOC'):
            county= request.form.get('select')
            city= request.form.get('selectOC')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##RiversidCounty+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectRS'):
            county= request.form.get('select')
            city= request.form.get('selectRS')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectRS'):
            county= request.form.get('select')
            city= request.form.get('selectRS')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectRS'):
            county= request.form.get('select')
            city= request.form.get('selectRS')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectRS'):
            county= request.form.get('select')
            city= request.form.get('selectRS')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##San BernandinoCounty+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectSB'):
            county= request.form.get('select')
            city= request.form.get('selectSB')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectSB'):
            county= request.form.get('select')
            city= request.form.get('selectSB')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectSB'):
            county= request.form.get('select')
            city= request.form.get('selectSB')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectSB'):
            county= request.form.get('select')
            city= request.form.get('selectSB')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##San DiegoCounty+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectSD'):
            county= request.form.get('select')
            city= request.form.get('selectSD')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectSD'):
            county= request.form.get('select')
            city= request.form.get('selectSD')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectSD'):
            county= request.form.get('select')
            city= request.form.get('selectSD')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectSD'):
            county= request.form.get('select')
            city= request.form.get('selectSD')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##LACommittee+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLACM'):
            county= request.form.get('select')
            city= request.form.get('selectLACM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': city }}, {'County': {'$regex': county, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLACM'):
            county= request.form.get('select')
            city= request.form.get('selectLACM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLACM'):
            county= request.form.get('select')
            city= request.form.get('selectLACM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLACM'):
            county= request.form.get('select')
            city= request.form.get('selectLACM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        
        ##LBCommittee+primeKey ###
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLBCM'):
            county= request.form.get('select')
            city= request.form.get('selectLBCM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form.get('selectLBCM'):
            county= request.form.get('select')
            city= request.form.get('selectLBCM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLBCM'):
            county= request.form.get('select')
            city= request.form.get('selectLBCM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }},{ 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")
        
        if request.form.get('select') and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form.get('selectLBCM'):
            county= request.form.get('select')
            city= request.form.get('selectLBCM')
            agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$regex': "City Council" }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': county, '$options': 'i' }},{'City': {'$regex': city, '$options': 'i' }}]}).sort('Date',-1).limit(10)
            return render_template('search.html',primeKey=primeKey, form=form, agendas=agenda, title = "PolicyEdge Search Results")

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

@app.route('/losangeles', methods=['GET', 'POST'])
def losangeles():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-4)
        d= str(c).replace("-","")
        twoweeksAgo=int(d)

        agenda = mongo.db.Agenda.find({'$and':[ { 'Date':{'$lte':int(today), '$gte':int(twoweeksAgo)}},{"MeetingType":{'$regex': "City Council" }}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')

        agouraHills=[]
        alhambra=[]
        arcadia=[]
        artesia=[]
        azusa=[]
        baldwinPark=[]
        bell=[]
        bellflower=[]
        bellGardens=[]
        beverlyHills=[]
        bradbury=[]
        burbank=[]
        calabasas=[]
        carson=[]
        cerritos=[]
        cityIndustry=[]
        claremont=[]
        commerce=[]
        compton=[]
        covina=[]
        cudahy=[]
        culverCity=[]
        diamondBar=[]
        downey=[]
        duarte=[]
        elMonte=[]
        elSegundo=[]
        gardena=[]
        glendale=[]
        glendora=[]
        hawaiianGardens=[]
        hawthorne=[]
        hermosaBeach=[]
        hiddenHills=[]
        huntingtonPark=[]
        inglewood=[]
        irwindale=[]
        lacanadaFlintridge=[]
        lahabraHeights=[]
        laMirada=[]
        laPuente=[]
        laVerne=[]
        lakewood=[]
        lancaster=[]
        lawndale=[]
        lomita=[]
        longBeach=[]
        losAngeles=[]
        lynwood=[]
        malibu=[]
        manhattanBeach=[]
        maywood=[]
        monrovia=[]
        montebello=[]
        montereyPark=[]
        norwalk=[]
        palmdale=[]
        palosverdesEstates=[]
        paramount=[]
        pasadena=[]
        picoRivera=[]
        pomona=[]
        ranchopalosVerdes=[]
        redondoBeach=[]
        rollingHills=[]
        rollinghillsEstate=[]
        rosemead=[]
        sPasadena=[]
        sanDimas=[]
        sanFernando=[]
        sanGabriel=[]
        sanMarino=[]
        santaClarita=[]
        santafeSprings=[]
        santaMonica=[]
        sierraMadre=[]
        signalHill=[]
        southelMonte=[]
        southGate=[]
        templeCity=[]
        torrance=[]
        vernon=[]
        walnut=[]
        westCovina=[]
        westHollywood=[]
        westlakeVillage=[]
        whittier=[]
        for x in agenda:
            if x["City"] ==' Agoura Hills ':
                agouraHills.append(x)
            if x["City"] ==' Alhambra ':
                alhambra.append(x)
            if x["City"] ==' Arcadia ':
                arcadia.append(x)
            if x["City"] ==' Artesia ':
                artesia.append(x)
            if x["City"] ==' Azusa ':
                azusa.append(x)
            if x["City"] ==' Baldwin Park ':
                baldwinPark.append(x)
            if x["City"] ==' Bell ':
                bell.append(x)
            if x["City"] ==' Bell Gardens ':
                bellGardens.append(x)
            if x["City"] ==' Bellflower ':
                bellflower.append(x)
            if x["City"] ==' Beverly Hills ':
                beverlyHills.append(x)
            if x["City"] ==' Bardbury ':
                bradbury.append(x)
            if x["City"] ==' Burbank ':
                burbank.append(x)
            if x["City"] ==' Calabasas ':
                calabasas.append(x)
            if x["City"] ==' Carson ':
                carson.append(x)
            if x["City"] ==' Cerritos ':
                cerritos.append(x)
            if x["City"] ==' City of Industry ':
                cityIndustry.append(x)
            if x["City"] ==' Claremont ':
                claremont.append(x)
            if x["City"] ==' Commerce ':
                commerce.append(x)
            if x["City"] ==' Compton ':
                compton.append(x)
            if x["City"] ==' Covina ':
                covina.append(x)
            if x["City"] ==' Cudahy ':
                cudahy.append(x)
            if x["City"] ==' Culver City ':
                culverCity.append(x)
            if x["City"] ==' Diamond Bar ':
                diamondBar.append(x)
            if x["City"] ==' Downey ':
                downey.append(x)
            if x["City"] ==' Duarte ':
                duarte.append(x)
            if x["City"] ==' El Monte ':
                elMonte.append(x)
            if x["City"] ==' El Segundo ':
                elSegundo.append(x)
            if x["City"] ==' Gardena ':
                gardena.append(x)
            if x["City"] ==' Glendale ':
                glendale.append(x)
            if x["City"] ==' Glendora ':
                glendora.append(x)
            if x["City"] ==' Hawaiian Gardens ':
                hawaiianGardens.append(x)
            if x["City"] ==' Hawthorne ':
                hawthorne.append(x)
            if x["City"] ==' Hermosa Beach ':
                hermosaBeach.append(x)
            if x["City"] ==' Hidden Hills ':
                hiddenHills.append(x)
            if x["City"] ==' Huntington Park ':
                huntingtonPark.append(x)
            if x["City"] ==' Inglewood ':
                inglewood.append(x)
            if x["City"] ==' Irwindale ':
                irwindale.append(x)
            if x["City"] ==' La Canada Flintridge ':
                lacanadaFlintridge.append(x)
            if x["City"] ==' La Habra Heights ':
                lahabraHeights.append(x)
            if x["City"] ==' La Mirada ':
                laMirada.append(x)
            if x["City"] ==' La Puente ':
                laPuente.append(x)
            if x["City"] ==' La Verne ':
                laVerne.append(x)
            if x["City"] ==' Lakewood ':
                lakewood.append(x)
            if x["City"] ==' Lancaster ':
                lancaster.append(x)
            if x["City"] ==' Lawndale ':
                lawndale.append(x)
            if x["City"] ==' Lomita ':
                lomita.append(x)
            if x["City"] ==' Long Beach ':
                longBeach.append(x)
            if x["City"] ==' Los Angeles ':
                losAngeles.append(x)
            if x["City"] ==' Lynwood ':
                lynwood.append(x)
            if x["City"] ==' Malibu ':
                malibu.append(x)
            if x["City"] ==' Manhattan Beach ':
                manhattanBeach.append(x)
            if x["City"] ==' Maywood ':
                maywood.append(x)
            if x["City"] ==' Monrovia ':
                monrovia.append(x)
            if x["City"] ==' Montebello ':
                montebello.append(x)
            if x["City"] ==' Monterey Park ':
                montereyPark.append(x)
            if x["City"] ==' Norwalk ':
                norwalk.append(x)
            if x["City"] ==' Palmdale ':
                palmdale.append(x)
            if x["City"] ==' Palos Verdes Estates ':
                palosverdesEstates.append(x)
            if x["City"] ==' Paramount ':
                paramount.append(x)
            if x["City"] ==' Pasadena ':
                pasadena.append(x)
            if x["City"] ==' Pico Rivera ':
                picoRivera.append(x)
            if x["City"] ==' Pomona ':
                pomona.append(x)
            if x["City"] ==' Rancho Palos Verdes ':
                ranchopalosVerdes.append(x)
            if x["City"] ==' Redondo Beach ':
                redondoBeach.append(x)
            if x["City"] ==' Rolling Hills ':
                rollingHills.append(x)
            if x["City"] ==' Rolling Hills Estate ':
                rollinghillsEstate.append(x)
            if x["City"] ==' Rosemead ':
                rosemead.append(x)
            if x["City"] ==' S Pasadena ':
                sPasadena.append(x)
            if x["City"] ==' San Dimas ':
                sanDimas.append(x)
            if x["City"] ==' San Fernando ':
                sanFernando.append(x)
            if x["City"] ==' San Gabriel ':
                sanGabriel.append(x)
            if x["City"] ==' San Marino ':
                sanMarino.append(x)
            if x["City"] ==' Santa Clarita ':
                santaClarita.append(x)
            if x["City"] ==' Santa Fe Springs ':
                santafeSprings.append(x)
            if x["City"] ==' Santa Monica ':
                santaMonica.append(x)
            if x["City"] ==' Sierra Madre ':
                sierraMadre.append(x)
            if x["City"] ==' Signal Hill ':
                signalHill.append(x)
            if x["City"] ==' South El Monte ':
                southelMonte.append(x)
            if x["City"] ==' South Gate ':
                southGate.append(x)
            if x["City"] ==' Temple City ':
                templeCity.append(x)
            if x["City"] ==' Torrance ':
                torrance.append(x)
            if x["City"] ==' Vernon ':
                vernon.append(x)
            if x["City"] ==' Walnut ':
                walnut.append(x)
            if x["City"] ==' West Covina ':
                westCovina.append(x)
            if x["City"] ==' West Hollywood ':
                westHollywood.append(x)
            if x["City"] ==' Westlake Village ':
                westlakeVillage.append(x)
            if x["City"] ==' Whittier ':
                whittier.append(x)
        return render_template('losangeles.html',whittiers=whittier,westlakeVillages=westlakeVillage,westHollywoods=westHollywood,westCovinas=westCovina,walnuts=walnut,vernons=vernon,torrances=torrance,templeCitys=templeCity,southGates=southGate,southelMontes=southelMonte,signalHills=signalHill,sierraMadres=sierraMadre,santaMonicas=santaMonica,santafeSpringss=santafeSprings,santaClaritas=santaClarita,sanMarinos=sanMarino,sanGabriels=sanGabriel,sanFernandos=sanFernando,sanDimass=sanDimas,sPasadenas=sPasadena,rosemeads=rosemead,rollinghillsEstates=rollinghillsEstate,rollingHillss=rollingHills,redondoBeachs=redondoBeach,ranchopalosVerdess=ranchopalosVerdes,pomonas=pomona,picoRiveras=picoRivera,pasadenas=pasadena,paramounts=paramount,palosverdesEstates=palosverdesEstates,palmdales=palmdale,norwalks=norwalk,montereyParks=montereyPark,montebellos=montebello,monrovias=monrovia,maywoods=maywood,manhattanBeachs=manhattanBeach,malibus=malibu,lynwoods=lynwood,losAngeless=losAngeles,longBeachs=longBeach,lomitas=lomita,lawndales=lawndale,lancasters=lancaster,lakewoods=lakewood,laVernes=laVerne,laPuentes=laPuente,laMiradas=laMirada,lahabraHeightss=lahabraHeights,lacanadaFlintridges=lacanadaFlintridge,irwindales=irwindale,inglewoods=inglewood,huntingtonParks=huntingtonPark,hiddenHillss=hiddenHills,hermosaBeachs=hermosaBeach,hawthornes=hawthorne,hawaiianGardenss=hawaiianGardens,glendoras=glendora,glendales=glendale,gardenas=gardena,elSegundos=elSegundo,elMontes=elMonte,duartes=duarte,downeys=downey,diamondBars=diamondBar,culverCitys=culverCity, cudahys=cudahy,covinas=covina,commerces=commerce,claremonts=claremont,cityIndustrys=cityIndustry,cerritoss=cerritos,carsons=carson,calabasass=calabasas,agouraHillss=agouraHills,alhambras=alhambra,arcadias=arcadia,artesias=artesia,azusas=azusa,baldwinParks=baldwinPark,bells=bell,bellflowers=bellflower, beverlyHillss=beverlyHills,comptons=compton, bradburys=bradbury, burbanks=burbank,title = "PolicyEdge agenda tracking monitoring service Los Angeles County Agendas")


@app.route('/orange', methods=['GET', 'POST'])
def orange():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ { 'Date':{'$lte':int(today), '$gte':int(lMonth)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('orange.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring service Orange County Agendas")

@app.route('/riverside', methods=['GET', 'POST'])
def riverside():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ { 'Date':{'$lte':int(today), '$gte':int(lMonth)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('riverside.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring service Riverside County Agendas")

@app.route('/sanbernandino', methods=['GET', 'POST'])
def sanbernandino():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ { 'Date':{'$lte':int(today), '$gte':int(lMonth)}}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('sanbernandino.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring service San Bernandino County Agendas")

@app.route('/sandiego', methods=['GET', 'POST'])
def sandiego():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ { 'Date':{'$lte':int(today), '$gte':int(lMonth)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('sandiego.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring service San Diego County Agnedas")

@app.route('/favicon.ico')
def favicon():
    return url_for('static', filename='static/favicon.ico')
    
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html', title="404"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html', title="500"), 500
    
if __name__ == '__main__':
    app.run(debug = False)













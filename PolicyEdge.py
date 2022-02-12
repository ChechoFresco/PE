from flask_pymongo import PyMongo
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, json
from forms import searchForm, monitorListform, notificationForm
import bcrypt
from datetime import date
from dateutil.relativedelta import relativedelta
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
import stripe
import os
from os import environ
from dotenv import load_dotenv

load_dotenv()
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

YOUR_DOMAIN = 'http://policyedge.net/' #need to update to https

stripe_keys = {
  'secret_key': os.environ['SECRET_KEY'],
  'publishable_key': os.environ['PUBLISHABLE_KEY']
}

stripe.api_key = stripe_keys['secret_key']

def check4Issues2email():
    with app.app_context():
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-2) #Change month to 3
        d= str(c).replace("-","")
        today_3= int(d)

        all_email=[]    #List of all email from storedUsers

        all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1})#Creates list af all emails and usernames for sequence
        for x in all_users: #For each instance of a user
            storedIssues= mongo.db.User.find({'username':x['username']}, {'_id': 0,'issues':1, 'agendaUnique_id':1, 'email':1})#Bring forth the following data
            if x['subscriptionActive'] == True: #Checks to see if user is subscripbed
                all_email.append(x['email'])#Users who are subscribe get added to email list
            else:
                pass

            issues_placeholder= []#List of user subscribed issues
            userStoredAgendaId=[]#List of user previous items

            for y in storedIssues:#Access users previous items and looks up subscribed issues
                userStoredAgendaId.extend(y['agendaUnique_id'])#previous items
                issues_placeholder.extend(y['issues'])#subscribed issues

            issueToString= str(issues_placeholder)
            finished_issues= issueToString.replace("'",'').replace("["," ").replace("]"," ").replace("issues:", " ")#Makes subscribed issues work in mongo query. Might have to get rid of commas!!!

            agenda=mongo.db.Agenda.aggregate([
            {'$match' : { '$text': { '$search': finished_issues}}}, # searches for subscribed issues.
            {'$match' : { 'Date': {'$lte':int(today), '$gte':int(today_3)}}},
            {'$match': {'_id': { '$nin': userStoredAgendaId }}} #Checks if item has been sent before
            ])

            description=[]
            city=[]
            Date=[]
            meeting_type=[]
            item_type=[]

            for i in agenda: #returned criteria
                #mongo.db.User.find_one_and_update({'username':x['username']}, {'$push': {'agendaUnique_id':i['_id']}}, upsert = True)
                description.append(i['Description'])
                city.append(i['City'])
                intDate= (str(i['Date']))
                start_year = str(intDate[0:4])
                start_month = str(intDate[4:6])
                start_day = str(intDate[6:8])
                Date.append(start_month+'/'+start_day+'/'+start_year)
                meeting_type.append(i['MeetingType'])
                item_type.append(i['ItemType'])

            for z in range(len(city)):
                subject = 'Test Email'
                sender = 'AgendaPreciado@gmail.com'
                msg = Message(subject, sender=sender, recipients=[y['email']])
                html_body = "<html> <body> <p> Hello {}, </p>  <p>The following item will be brought before the {} City Council on {}.</p> <br> {} </br> <p> Thanks for your continued support,<br> <br>  Policy Edge</p> </body> </html>".format(x['username'],city[z],Date[z],description[z])
                msg.html=html_body
                mail.send(msg)

sched = BackgroundScheduler(timezone='UTC')
sched.add_job(check4Issues2email, 'interval', seconds=43200)
sched.start()

@app.route('/', methods=['GET', 'POST'])
def index():
    if "username" in session:
        return redirect(url_for("loggedIn"))

    return render_template('index.html',title="Welcome to my site")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if "username" in session:
        flash(session["username"])
        return redirect(url_for("loggedIn"))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if "username" in session:
        return render_template('loggedIn.html', username = session['username'])

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

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
                    return redirect(url_for('loggedIn'))
                else:
                    session['subscribed'] = False
                    return redirect(url_for('loggedIn'))
            else:
                if "username" in session:
                    return redirect(url_for("loggedIn"))
                flash('Wrong password')
                return render_template('login.html')
        else:
            flash('Username not found')
            return render_template('login.html')
    return render_template('login.html', title="Please Login")

@app.route('/loggedIn', methods=['GET', 'POST'])
def loggedIn():
    if "username" in session:
        username = session["username"]
        return render_template('loggedIn.html', username = username, title = "Welcome back!")
    else:
        return redirect(url_for("login"))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    for key in list(session.keys()):
        session.pop(key) #logs user out
    return render_template('index.html', title='Signed Out')

@app.route('/subscription', methods=['GET'])# Subscription page is needed so existing users can re-subscribe.
def get_index():
    if "username" in session:
        return render_template('subscription.html')
    else:
        return redirect(url_for("login"))

@app.route('/create-checkout-session2', methods=['POST'])
def create_checkout_session2(): # Second checkout is for existing users who want to re-subscribe
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

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():# first section creates user on Mongo and Stripe db at the same time but with subscription set to False
    username = request.form["username"]
    email = request.form["email"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    username_found = mongo.db.User.find_one({"username": username})#Checks if username exist
    email_found = mongo.db.User.find_one({"email": email})#Check if email exist
    stripe_email_found = mongo.db.stripe_user.find_one({"email": email})
    if username_found:
        flash('There already is a user by that name')
        return render_template('register.html')
    if email_found:
        flash('This email already exists in our user database')
        return render_template('register.html')
    if stripe_email_found:
        flash('This email already exists in our Stripe database')
        return render_template('register.html')
    if password1 != password2:
        flash('Passwords should match!')
        return render_template('register.html')
    else:
        hashed = bcrypt.hashpw(password2.encode('utf-8'), bcrypt.gensalt())
        policy_user_input = {'username': username, 'email': email, 'password': hashed, 'stripe_id': [],'issues': [], 'agendaUnique_id': [], 'subscriptionActive': False}
        stripe_user_input = {'username': username, 'email': email, 'stripeCustomerId' : [], 'stripeSubscriptionId':[]}
        mongo.db.User.insert_one(policy_user_input)
        mongo.db.stripe_user.insert_one(stripe_user_input)
        session['username'] = username
        session['email'] = email

    noStripeId = mongo.db.User.find_one({'$and':[ {"email": session['email'] }, {"stripe_id" : {"$exists" : True, '$eq': [] }}]}) #Checks if user has account with Stripe

    if noStripeId: #The user was found not to have account with Stripe yet
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

@app.route('/create-portal-session', methods=['POST'])
def customer_portal():

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
        elif data.object.status == 'incomplete':
            pass

    elif event_type == 'customer.subscription.deleted':
        print('Subscription canceled: %s', event.id)
        print(data.object)
        mongo.db.User.find_one_and_update({'stripe_id':data.object.customer}, {'$set': {'subscriptionActive': False}})

    return jsonify({'status': 'success'})

@app.route('/search', methods=['GET', 'POST'])
def search():
    form = searchForm()
    #if "username" in session:
    #    if mongo.db.User.find_one({'$and':[ {'username': session['username']} ,{'subscriptionActive': True}]}):
    if request.method == 'POST':
        return redirect(url_for('results'), code=307)#Doesn't work without 307?
        #else:
            #flash('Please Subscribe first.')
            #return render_template('noSubscription.html')#
    #else:
        #return redirect(url_for("login"))###
    return render_template('search.html', form=form, title='Search')

@app.route('/results', methods=['GET', 'POST'])
def results():
    searchKey = request.form['primary_search']
    start_date = request.form['startdate_field']
    end_date = request.form['enddate_field']
    start_year = str(start_date[0:4])
    start_month = str(start_date[5:7])
    start_day = str(start_date[8:10])
    end_year = str(end_date[0:4])
    end_month = str(end_date[5:7])
    end_day = str(end_date[8:10])
    start = (start_year+start_month+start_day)
    end = (end_year+end_month+end_day)
    if request.form['select'] == 'City' and request.form['startdate_field']:
        agenda = mongo.db.Agenda.find({'$and':[ { 'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$regex': "City Council", '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "Search Results")
    if request.form['select'] == 'City' and request.form['startdate_field']== "":# Allows user to not input date
        agenda = mongo.db.Agenda.find({ '$and':[ {'City': {'$regex': searchKey, '$options': 'i' }}, {"MeetingType":{'$regex': "City Council"}} ]})
        return render_template('results.html', agendas=agenda,  title = "Search Results")
    if request.form['select'] == 'Issue' and request.form['startdate_field']:
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda,  title = "Search Results")
    if request.form['select'] == 'Issue' and request.form['startdate_field'] =="":# Allows user to not input date
        agenda = mongo.db.Agenda.find({ '$text': { "$search": searchKey}})
        return render_template('results.html', agendas=agenda, title = "Search Results")
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "Search Results")
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="":
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }},{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]})
        return render_template('results.html', agendas=agenda,  title = "Search Results")
    if request.form['select'] == 'LB Committees' and request.form['startdate_field']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}},{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "Search Results")
    if request.form['select'] == 'LB Committees' and request.form['startdate_field']=="":
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }},{'City': {'$regex': 'Long Beach', '$options': 'i' }}]})
        return render_template('results.html', agendas=agenda,  title = "Search Results")

@app.route('/cannabis', methods=['GET', 'POST'])
def cannabis():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'cannabis'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('cannabis.html', agendas=agenda,  title = "Search Results")

@app.route('/waste', methods=['GET', 'POST'])
def waste():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'waste'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('waste.html', agendas=agenda,  title = "Search Results")

@app.route('/medical', methods=['GET', 'POST'])
def medical():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'medical'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('medical.html', agendas=agenda,  title = "Search Results")

@app.route('/telecommunication', methods=['GET', 'POST'])
def telecommunication():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'telecommunication'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('telecommunication.html', agendas=agenda,  title = "Search Results")

@app.route('/transportation', methods=['GET', 'POST'])
def transportation():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'transportation'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('transportation.html', agendas=agenda,  title = "Search Results")

@app.route('/technology', methods=['GET', 'POST'])
def technology():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'technology'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('technology.html', agendas=agenda,  title = "Search Results")

@app.route('/financial', methods=['GET', 'POST'])
def financial():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=-1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'financial'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('financial.html', agendas=agenda,  title = "Search Results")

@app.route('/utility', methods=['GET', 'POST'])
def utility():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(months=1) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'utility'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('utility.html', agendas=agenda,  title = "Search Results")

@app.route('/savedIssues', methods=['GET', 'POST'])
def savedIssues():
    if "username" in session:
        if mongo.db.User.find_one({'$and':[ {'username': session['username']} ,{'subscriptionActive': True}]}):
            if request.method == 'GET':
                form = monitorListform()
                user = session["username"]
                a = date.today()
                b= str(a).replace("-","")
                today=int(b)
                c = date.today() + relativedelta(months=-3)
                d= str(c).replace("-","")
                today_3= int(d)# Converts date - 3 months
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues':1})
                for x in user_issues:
                    issues_placeholder.append(x['issues'])
                    j= str(issues_placeholder)
                    finished_issues= j.replace("'",'').replace("["," ").replace("]"," ").replace(",", " ")
                    agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": finished_issues}}, { 'Date':{'$lte':int(today), '$gte':int(today_3)}}]}).sort('Date').sort('City')
                    flash(finished_issues)
                    return render_template('savedIssues.html', form=form, agendas=agenda,  title='Monitor List')
            elif request.method == 'POST' and request.form['action'] == 'Add':
                form = monitorListform()
                user = session["username"]
                a = date.today()
                b= str(a).replace("-","")
                today=int(b)
                c = date.today() + relativedelta(months=-8)
                d= str(c).replace("-","")
                today_3= int(d)
                issue = request.form['monitor_search']
                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':issue}}, upsert = True)
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues':1})
                for x in user_issues:
                    issues_placeholder.append(x['issues'])
                    j= str(issues_placeholder)
                    finished_issues= j.replace("'",'').replace("["," ").replace("]"," ").replace(",", " ")
                    agenda= mongo.db.Agenda.find({'$and':[ {'$text': { "$search": finished_issues}}, { 'Date':{'$lte':int(today), '$gte':int(today_3)}}]}).sort('Date').sort('City')
                    flash(finished_issues)
                    return render_template('savedIssues.html', form=form, agendas=agenda,  title='Monitor List')
            elif request.method == 'POST' and request.form['action']  == 'Delete':
                form = monitorListform()
                user = session["username"]
                a = date.today()
                b= str(a).replace("-","")
                today=int(b)
                c = date.today() + relativedelta(months=-8)
                d= str(c).replace("-","")
                today_3= int(d)
                issue = request.form['monitor_search']
                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':issue}})
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues':1})#"'_id': 0" BLOCKS FROM SHOWING FLASH
                for x in user_issues:
                    issues_placeholder.append(x['issues'])
                    j= str(issues_placeholder)
                    finished_issues= j.replace("'",'').replace("["," ").replace("]"," ").replace(",", " ")
                    agenda= mongo.db.Agenda.find({'$and':[ {'$text': { "$search": finished_issues}}, { 'Date':{'$lte':int(today), '$gte':int(today-600)}}]}).sort('Date').sort('City')
                    flash(finished_issues)
                    return render_template('savedIssues.html', form=form, agendas=agenda,  title='Monitor List')
        else:
            return render_template('noSubscription.html')
    else:
        return redirect(url_for("login"))

@app.route('/success')
def success():
    return render_template("success.html")

@app.route('/cancel')
def cancelled():
    return render_template("cancel.html")

@app.route('/noSubscription')
def noSubscription():
    return render_template("noSubscription.html")

@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template('about.html', title='about')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    return render_template('contact.html', title='Contact')

@app.route('/termsofservice', methods=['GET', 'POST'])
def termsofservice():
    return render_template('termsofservice.html', title='Terms of Service')

@app.route('/privacypolicy', methods=['GET', 'POST'])
def privacypolicy():
    return render_template('privacypolicy.html', title='Privacy Policy')










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

YOUR_DOMAIN = 'https://www.policyedge.net/' 

stripe_keys = {
  'secret_key': os.environ['SECRET_KEY'],
  'publishable_key': os.environ['PUBLISHABLE_KEY']
}

stripe.api_key = stripe_keys['secret_key']

def check4Issues2email():
    with app.app_context():
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)+7 #+7 days to see future agendas
        c = date.today() + relativedelta(days=-7) #Change days to 3
        d= str(c).replace("-","")
        today_3= int(d)

        all_email=[]    #List of all email from storedUsers

        all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1, "subscriptionActive":1})#Creates list af all emails and usernames for sequence
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

            agenda=[]

            for z in range(len(issues_placeholder[0])):
                city_Search= (issues_placeholder[0][z]['City'])
                issue_Search= (issues_placeholder[0][z]['searchWord'])
                committee_Search= (issues_placeholder[0][z]['committee'])

                Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i' }} ,{'$text': { "$search": issue_Search}}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}, {'_id': { '$nin': userStoredAgendaId }}]})

                for zz in Multiquery:
                    agenda.append(zz)

            if not agenda: #If query returns empty skip
                pass
            else:
                description=[]
                city=[]
                Date=[]
                meeting_type=[]
                item_type=[]

            for i in agenda: #returned criteria
                mongo.db.User.find_one_and_update({'username':x['username']}, {'$push': {'agendaUnique_id':i['_id']}},upsert=True)# updates database with iems uniqueid
                description.append(i['Description'])
                city.append(i['City'])
                intDate= (str(i['Date']))
                start_year = str(intDate[0:4])
                start_month = str(intDate[4:6])
                start_day = str(intDate[6:8])
                Date.append(start_month+'/'+start_day+'/'+start_year)
                meeting_type.append(i['MeetingType'])
                item_type.append(i['ItemType'])

                subject = 'New Issue Alerts'
                sender = 'AgendaPreciado@gmail.com'
                msg = Message(subject, sender=sender, recipients=[y['email']])
                email_body=[]
                for z in range(len(city)):#range(len)city is used because it gives accurate count of items being sent
                    email_body.append("<html> <body> <p>The following item will be brought before the {} City Council on {}.</p>  {}  </body><br></br><br></br><br></br><br></br>".format(city[z],Date[z],description[z]))
                    html_body= "\n".join(email_body)
                    msg.html= "Hello {},".format(x['username']) +html_body + "<p> Thanks for your continued support,<br> <br>  Policy Edge</p> </html>"

            mail.send(msg)

sched = BackgroundScheduler(timezone='UTC')
sched.add_job(check4Issues2email, 'interval', seconds=3600)
sched.start()

@app.route('/', methods=['GET', 'POST'])
def httpsroute():
    return redirect("https://www.policyedge.net", code = 301)

@app.route('/index', methods=['GET', 'POST'])
def index():
      if "username" in session:
        return redirect(url_for("loggedIn"))
      
      return render_template('index.html',title="PolicyEdge agenda monitoring tracking service")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if "username" in session:
        flash(session["username"])
        return redirect(url_for("loggedIn"))
    return render_template("register.html", title="Become a member of PolicyEdge's agenda monitoring services")

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
    return render_template('login.html', title="Please Log into PolicyEdge for agenda tracking services")

@app.route('/loggedIn', methods=['GET', 'POST'])
def loggedIn():
    if "username" in session:
        username = session["username"]
        return render_template('loggedIn.html', username = username, title = "You are now logged into PolicyEdge. Government at a glance.")
    else:
        return redirect(url_for("/"))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    for key in list(session.keys()):
        session.pop(key) #logs user out
    return render_template('index.html', title='PolicyEdge has signed you out of your account')

@app.route('/subscription', methods=['GET'])# Subscription page is needed so existing users can re-subscribe.
def get_index():
    if "username" in session:
        return render_template('subscription.html', title='Please re-subscribe to PolicyEdge at any time. Los Angeles agenda monitoring service')
    else:
        return redirect(url_for("login"))

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

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():# first section creates user on Mongo and Stripe db at the same time but with subscription set to False
    stripe.api_key = stripe_keys['secret_key']

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
    return render_template('search.html', form=form, title='Search PolicyEdge agendas monitoring tracking service in Los Angeels County')

@app.route('/results', methods=['GET', 'POST'])
def results():
    searchKey = request.form['primary_search']
    deepKey = request.form['secondary_search']
    start_date = request.form['startdate_field']
    end_date = request.form['enddate_field']
    a = date.today()
    b= str(a).replace("-","")
    today=int(b)
    start_year = str(start_date[0:4])
    start_month = str(start_date[5:7])
    start_day = str(start_date[8:10])
    end_year = str(end_date[0:4])
    end_month = str(end_date[5:7])
    end_day = str(end_date[8:10])
    start = (start_year+start_month+start_day)
    end = (end_year+end_month+end_day)
    if request.form['select'] == 'City' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'City' and request.form['startdate_field']== "" and request.form['enddate_field']=="" and request.form['secondary_search']=="":# Allows user to not input date
        agenda = mongo.db.Agenda.find({'$and':[{'$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'City': {'$regex': searchKey, '$options': 'i' }}]})
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'City' and request.form['startdate_field'] and request.form['enddate_field'] == "" and request.form['secondary_search']=="":# Allows user to not input End date ==today
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$regex': "City Council", '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")

    if request.form['select'] == 'City' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['secondary_search'] and request.form['primary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, {"MeetingType":{'$regex': "City Council"}}, { 'Date':{'$lte':int(end), '$gte':int(start)}} ]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'City' and request.form['startdate_field'] and request.form['enddate_field'] == "" and request.form['secondary_search'] and request.form['primary_search'] :# Allows user to not input End date ==today
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, {"MeetingType":{'$regex': "City Council"}}, { 'Date':{'$lte':today, '$gte':int(start)}} ]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'City' and request.form['startdate_field']== ""  and request.form['enddate_field'] == "" and request.form['secondary_search'] and request.form['primary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": deepKey}},{'City': {'$regex': searchKey, '$options': 'i' }}, {"MeetingType":{'$regex': "City Council"}}]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")

    if request.form['select'] == 'Issue' and request.form['startdate_field'] =="" and request.form['enddate_field']=="" and request.form['primary_search']:# Allows user to not input date
        agenda = mongo.db.Agenda.find({ '$text': { "$search": searchKey}})
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']==""  and request.form['primary_search']:# Allows user to not input date
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}},{ 'Date':{'$lte':int(today), '$gte':int(start)}} ]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']:# Allows user to not input date
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}},{ 'Date':{'$lte':int(end), '$gte':int(start)}} ]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge agendas monitoring tracking Search Results")           

    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }},{"MeetingType":{'$regex': searchKey, '$options': 'i' }} ]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }},{"MeetingType":{'$regex': searchKey, '$options': 'i' }},{ 'Date':{'$lte':today, '$gte':int(start)}} ]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }},{"MeetingType":{'$regex': searchKey, '$options': 'i' }},{ 'Date':{'$lte':int(end), '$gte':int(start)}} ]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")

    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }},{"MeetingType":{'$regex':searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}} ]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }},{"MeetingType":{'$regex': searchKey, '$options': 'i' }},{ 'Date':{'$lte':today, '$gte':int(start)}}, {'$text': { "$search": deepKey}} ]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[{"MeetingType":{'$not':{'$regex': "City Council"}}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }},{"MeetingType":{'$regex': searchKey, '$options': 'i' }},{ 'Date':{'$lte':int(end), '$gte':int(start)}}, {'$text': { "$search": deepKey}} ]})
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge agendas monitoring tracking Search Results")
      

@app.template_filter('aTime')
def int2date(agDate: int) -> date:
    """
    If you have date as an integer, use this method to obtain a datetime.date object.

    Parameters
    ----------
    value : int
    Date as a regular integer value (example: 20160618)

    Returns
    -------
    dateandtime.date
    A date object which corresponds to the given value `agDate`.
    """
    year = int(agDate / 10000)
    month = int((agDate % 10000) / 100)
    day = int(agDate % 100)
    
    return date(year,month,day)

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
        return render_template('cannabis.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring Cannabis Search Results")

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
        return render_template('waste.html', agendas=agenda,  title = "PolicyEdge agenda Waste Search Results")

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
        return render_template('medical.html', agendas=agenda,  title = "PolicyEdge agenda Medical Search Results")

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
        return render_template('telecommunication.html', agendas=agenda,  title = "PolicyEdge agenda Telecommunication Search Results")

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
        return render_template('transportation.html', agendas=agenda,  title = "PolicyEdge agenda Transportation Search Results")

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
        return render_template('technology.html', agendas=agenda,  title = "PolicyEdge agenda Technology Search Results")

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
        return render_template('financial.html', agendas=agenda,  title = "PolicyEdge agenda Financial Search Results")

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
        return render_template('utility.html', agendas=agenda,  title = "PolicyEdge agenda Utility Search Results")

@app.route('/savedIssues', methods=['GET', 'POST'])
def savedIssues():
    if "username" in session:
        if mongo.db.User.find_one({'$and':[ {'username': session['username']} ,{'subscriptionActive': True}]}):
            if request.method == 'GET':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()
                b= str(a).replace("-","")
                today=int(b)+7 #add 7 so new agendas will be caught
                c = date.today() + relativedelta(days=-30) #Change day to 7 otherwise too many emails.
                d= str(c).replace("-","")
                today_1month= int(d)

                all_email=[]    #List of all email from storedUsers

                all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1, 'agendaUnique_id':1, 'email':1, 'subscriptionActive':1})#Creates list af all emails and usernames for sequence
                for x in all_users: #For each instance of a user
                    storedIssues= mongo.db.User.find({'username':x['username']}, {'_id': 0,'issues.searchWord':1,'issues.committee':1,'issues.City':1, 'agendaUnique_id':1, 'email':1,'subscriptionActive':1})#Bring forth the following data
                    if x['subscriptionActive'] == True: #Checks to see if user is subscripbed
                        all_email.append(x['email'])#Users who are subscribe get added to email list
                    else:
                        pass

                    issues_placeholder= []#List of user subscribed issues
                    userStoredAgendaId=[]#List of user previous items
                    agenda=[]

                    for y in storedIssues:#Access users previous items and looks up subscribed issues
                        userStoredAgendaId.extend(y['agendaUnique_id'])#previous items
                        issues_placeholder.append(y['issues'])#subscribed issues

                    for z in range(len(issues_placeholder[0])):
                        city_Search= (issues_placeholder[0][z]['City'])
                        issue_Search= (issues_placeholder[0][z]['searchWord'])
                        committee_Search= (issues_placeholder[0][z]['committee'])

                        Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i' }} ,{'$text': { "$search": issue_Search}}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                        for zz in Multiquery:
                            agenda.append(zz)

                        description=[]
                        city=[]
                        Date=[]
                        meeting_type=[]
                        item_type=[]

                        for i in agenda: #returned criteria
                            #mongo.db.User.find_one_and_update({'username':x['username']}, {'$push': {'agendaUnique_id':i['_id']}},upsert=True)# updates database with iems uniqueid
                            description.append(i['Description'])
                            city.append(i['City'])
                            intDate= (str(i['Date']))
                            start_year = str(intDate[0:4])
                            start_month = str(intDate[4:6])
                            start_day = str(intDate[6:8])
                            Date.append(start_month+'/'+start_day+'/'+start_year)
                            meeting_type.append(i['MeetingType'])
                            item_type.append(i['ItemType'])
                        flash(issues_placeholder[0][z]['City']['searchWord'])
                return render_template('savedIssues.html', form=form, agendas=agenda,  title='Monitor List')

            elif request.method == 'POST' and request.form['action'] == 'Add':
                form = monitorListform()
                user = session["username"]


                #####Creates dates########
                a = date.today()
                b= str(a).replace("-","")
                today=int(b)
                c = date.today() + relativedelta(months=-1)
                d= str(c).replace("-","")
                today_1month= int(d)

                #####Adds key to Issues########
                issue = request.form['monitor_search']
                cityKey = request.form['city_search']
                committeeKey = request.form['committee_search']
                CompleteIssue = {
                    "searchWord": issue,
                    "City": cityKey,
                    "committee": committeeKey,
                }

                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                ######Returns user saved issues#####
                issues_placeholder= []

                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.searchWord':1, 'issues.City':1, 'issues.committee':1}) #projects sub-documents to run in search
                for x in user_issues:
                    issues_placeholder.append(x['issues']) #Sends sub-document issues to issue_placeholder


                ######Returns matching agendas from for loop below#####
                agenda=[]
                ####returns exact amount of items to loop through####
                for y in range(len(issues_placeholder[0])):
                    city_Search= (issues_placeholder[0][y]['City'])
                    issue_Search= (issues_placeholder[0][y]['searchWord'])
                    committee_Search= (issues_placeholder[0][y]['committee'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i' }} ,{'$text': { "$search": issue_Search}}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agenda.append(z)

                    flash(issue_Search)
                return render_template('savedIssues.html', form=form, agendas=agenda,  title='Monitor List')



            elif request.method == 'POST' and request.form['action']  == 'Delete':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()
                b= str(a).replace("-","")
                today=int(b)
                c = date.today() + relativedelta(months=-1)
                d= str(c).replace("-","")
                today_1month= int(d)

                #####Adds key to Issues########
                issue = request.form['monitor_search']
                cityKey = request.form['city_search']
                committeeKey = request.form['committee_search']
                CompleteIssue = {
                    "searchWord": issue,
                    "City": cityKey,
                    "committee": committeeKey,
                }

                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                issues_placeholder= []

                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues':1})#"'_id': 0" BLOCKS FROM SHOWING FLASH

                for x in user_issues:
                    issues_placeholder.append(x['issues'])
                    j= str(issues_placeholder)
                    finished_issues= j.replace("'",'').replace("["," ").replace("]"," ").replace(",", " ")
                    agenda= mongo.db.Agenda.find({'$and':[ {'$text': { "$search": finished_issues}}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]}).sort('Date').sort('City')
                    flash(CompleteIssue)
                    return render_template('savedIssues.html', form=form, agendas=agenda,  title='Monitor List')
        else:
            return render_template('noSubscription.html')
    else:
        return redirect(url_for("login"))

@app.route('/success')
def success():
    return render_template("success.html", title='PolicyEdge subscription succesful')

@app.route('/cancel')
def cancelled():
    return render_template("cancel.html", title='Cancel your PolicyEdge subscription?')

@app.route('/noSubscription')
def noSubscription():
    return render_template("noSubscription.html",title='You do not currently have a PolicyEdge subscription')

@app.route('/about', methods=['GET', 'POST'])
def about():
    return render_template("about.html", title="Learn about PolicyEdge's creator Sergio Preciado")

@app.route('/termsofservice', methods=['GET', 'POST'])
def termsofservice():
    return render_template('termsofservice.html', title='PolicyEdge agenda tracking monitoring Terms of Service')

@app.route('/privacypolicy', methods=['GET', 'POST'])
def privacypolicy():
    return render_template('privacypolicy.html', title='PolicyEdge agenda tracking monitoring Privacy Policy')










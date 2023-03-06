from flask_pymongo import PyMongo
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, json
from forms import searchForm, monitorListform, newIssue, newTrend
import bcrypt
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from flask_mail import Mail, Message
import stripe
import os
import re
from os import environ
from apscheduler.schedulers.background import BackgroundScheduler
import nltk
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist
from nltk.corpus import stopwords
import string
import csv
import random


app = Flask(__name__,)

app.config['MONGO_URI'] = os.environ.get("MONGO_URI")
app.config['MAIL_SERVER']='smtp.gmail.com'#Email
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.secret_key = os.environ.get("SESS_KEY")

nltk.download('popular')


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
        a = date.today()+ relativedelta(days=14)
        b= str(a).replace("-","")
        today=int(b) #+7 days to see future agendas
        c = date.today() + relativedelta(days=-7) #Change days to 7 before date just in case
        d= str(c).replace("-","")
        today_3= int(d)# #Change days to 7 finished product

        all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1, 'agendaUnique_id':1, 'email':1, 'subscriptionActive':1, 'issues':1})#Creates list af all emails and usernames for sequence

        for x in all_users: #For each instance of a user
            if x['subscriptionActive'] == True: #Checks to see if user is subscribed
                storedIssues= mongo.db.User.find({'username':x['username']}, {'_id': 0, 'issues.Issue':1, 'issues.County':1, 'issues.City':1, 'issues.committee':1, 'agendaUnique_id':1, 'email':1})#Bring forth the following data

                issues_placeholder= []#List of user subscribed issues
                userStoredAgendaId=[]#List of user previous items

                for y in storedIssues:
                    userStoredAgendaId.extend(y['agendaUnique_id'])#previous items
                    issues_placeholder.append(y['issues'])#subscribed issues

                agenda=[]
                agenda2=[]

                for z in range(len(issues_placeholder[0])): #For every item in issues_placeholder, breaks down into individual parts in order for Multiquery to function
                    city_Search= (issues_placeholder[0][z]['City'])#Grabs City
                    issue_Search= (issues_placeholder[0][z]['Issue'])#Grabs Issue
                    committee_Search= (issues_placeholder[0][z]['committee'])#Grabs Committee
                    county_Search= (issues_placeholder[0][z]['County'])

        ##################Multiquery uses each _Search to run individual db.finds to create multiquery

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_3)}}]})


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
                text=[]

                email_body=[]

                for zz in agenda2:
                    issue.append(zz)
 
                for i in agenda: #returned criteria
                    if i['_id'] not in userStoredAgendaId:
                        mongo.db.User.find_one_and_update({'username':x['username']}, {'$addToSet': {'agendaUnique_id':i['_id']}})# updates database with items uniqueid
                        description.append(i['Description'])
                        city.append(i['City'])
                        County.append(i['County'])
                        intDate= (str(i['Date']))
                        start_year = str(intDate[0:4])
                        start_month = str(intDate[4:6])
                        start_day = str(intDate[6:8])
                        links=mongo.db.doc.find_one({"City":{'$regex': i['City'][1:-1], '$options': 'i'}},{'_id': 0,'webAdress': 1} )
                        links2= str(links).replace("{'webAdress': '","").replace("'}","")
                        text.append(links2)
                        Date.append(start_month+'/'+start_day+'/'+start_year)
                        meeting_type.append(i['MeetingType'])
                        item_type.append(i['ItemType'])

                for y in range(len(city)):#range(len)city is used because it gives accurate count of items being sent
                    email_body.append("<html> <body> <p>The following issue '{}' will be brought before the {} {} in {} on {}.</p>  {} <br></br> <br></br> Provided is a link to the agendas {} </body><br></br><br></br><br></br>".format(issue[y],city[y],meeting_type[y],County[y],Date[y],description[y], text[y]))

                if len(email_body)==0:
                    pass
                else:
                    subject = 'New Issue Alerts'
                    sender = 'AgendaPreciado@gmail.com'
                    msg = Message(subject, sender=sender, recipients=[x['email']])
                    html_body= "\n".join(email_body)
                    msg.html= "Hello {},".format(x['username']) +html_body + "<p> Thanks for your continued support,<br> <br><span style= 'color:#3e00ff; text-shadow: 1px 1px black'>Policy</span><span style= 'color:#5e7cff; text-shadow: 1px 1px black'>Edge</span></p> </html>"
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
    if "username" in session:
        return redirect(url_for("loggedIn"))
    else:
        ##Trend Pre-Load#####
        form = newIssue()
        form2 = newTrend()

        ##Main Issue three month#####

        a = date.today()+ relativedelta(weeks=2)
        b= str(a).replace("-","")
        twoweekAhead=int(b)
        c = date.today() + relativedelta(weeks=-16)
        d= str(c).replace("-","")
        lMonth=int(d)

        ##One week Trend#####

        e = date.today()+ relativedelta(weeks=1)
        f= str(e).replace("-","")
        weekAhead=int(f)
        g = date.today() + relativedelta(weeks=-2)
        h= str(g).replace("-","")
        weekBefore=int(h)

        ##One month Trend#####

        i = date.today()
        j= str(i).replace("-","")
        today=int(j)
        k = date.today() + relativedelta(weeks=-4)
        l= str(k).replace("-","")
        monthBefore=int(l)

        ##Three month Trend#####

        o = date.today() + relativedelta(weeks=-16)
        p= str(o).replace("-","")
        threeBefore=int(p)

        countyList = [" San Bernandino County ", " Riverside County ", " Orange County ", " San Diego County ", " LA County "]
        chosen3= countyList.pop(random.randrange(len(countyList)))
        words = set(nltk.corpus.words.words())
        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord=('comment limited''comment recieved''comment received 6''construction construction''budget budget''park park''declare said''conflict interest''source associated''activity defined''defined therefore''activity indirect''posted supplemental''supplemental contain''contain start''start official''official record''annexation annexation''click posted''number geographic''organizational activity''afternoon begin''begin source''text text''interest source''task force'
        'permit attached''exhibit exhibit''investment investment''palm palm''palm desert''greater chamber''page page''appendices thereto''fact provided''oath newly''time address''governing must''prior must''upon service''group offset''special special''tabulation place''january''august''june''speak queue''share tweet''zoom call''vice chair''unless otherwise''claim claim''appear shall''continue conduct''professional professional''vacant formerly''appoint serve''lake forest''tweet load''appropriation adjustment''finance authority''fountain valley''implement administer''subdivision name''alternate vacant''request speak''wishing speak''give card''formerly alternate''appointment currently''plus contingency''period four''four optional''legislative analyst''selection process''negotiator negotiator''financial analysis''categorical exemption''chapter reference''negative declaration''set forth''mechanical residential''taking additional''neither legislative''analyst financial''matter jurisdiction''separate discussion''south gate''three additional''none limit'
        'ability safely''removed considered''warrant register''form acceptable''undertake finalize''site review''floor area''street street''new business''doe doe''resolve find''find director''director determined''effectuate intent''mitigation program''master application''riverside county''member ending''conference litigation''waive full''parcel map''western riverside''update presentation''tentative map''adoption building''building fire''conference conference''quarter ending''initiate zoning''full waive''tentative parcel''see see''position member''ending member''district affected''contact person''result direct''san san''charter taken''aken contact''mayor taken''mayor designee''oceanside oceanside''association oceanside''change contact''orange county''pacific avenue''avenue pacific''waive full''provide direction''notice completion''parcel map''edition building''make necessary''measure expenditure''way way''specific plan''edition edition''determine result''result physical''physical change''change directly''introduce first''building edition''mayor behalf''costa mesa''direction regarding''specific plan''waive full ''neighborhood neighborhood''avenue avenue''alternatively discuss''discuss take''housing element''memorandum understanding''superior court''negotiation price''improvement project''purchase order''court case''one motion''take related''agenda ocean''cost account''account cost''grant funds''commission commission''listed agenda''article class''board airport''last day''project project''attachment attachment''land use''long beach''general fund''closed session''office department''regular meeting''community development''award contract''consent calendar''legal counsel''report relative''ordinance ordinance''reading ordinance''administrative officer''item consideration''staff report''recommendation recommendation''committee report''police department''exempt pursuant''chief executive''subject approval''second reading''real property''amendment agreement''successor agency''town town''city council''city manager''impact statement''authorize city''adopt resolution''code section''government code''city attorney''municipal code''code title''action approve''council city''resolution city''quality act ''public hearing''fiscal year''city clerk''environmental quality''receive file''public works''amount exceed''council action''resolution resolution''council consider''manager execute')

        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen3}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen3}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen3}, { 'Date':{'$lte':today, '$gte':threeBefore}}, {'City': {'$not':{'$regex': " Los Angeles "}}}]}, {'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})

        box1=[]
        for x in agendaACounty:
            box1.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        tokens1=[]
        for w in box1:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord:
                    if w in words:
                        tokens1.append(w)
        grams1 = nltk.ngrams(tokens1, 2)

        fdist1 = nltk.FreqDist(grams1)

        box2=[]
        for x in agendaBCounty:
            box2.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        tokens2=[]
        for w in box2:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord:
                    if w in words:
                        tokens2.append(w)
        grams2 = nltk.ngrams(tokens2, 2)

        fdist2 = nltk.FreqDist(grams2)

        box3=[]
        for x in agendaCCounty:
            box3.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        tokens3=[]
        for w in box3:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord:
                    if w in words:
                        tokens3.append(w)
        grams3 = nltk.ngrams(tokens3, 2)

        fdist3 = nltk.FreqDist(grams3)

        topics = ["water", "cannabis", "EV", "homeless","climate", "oil","waste","gas","utility","retail","financial"]
        chosen = topics.pop(random.randrange(len(topics)))

        if request.method == 'GET':
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen,chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'cannabis':
            chosen= 'cannabis'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'water':
            chosen= 'water'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'EV':
            chosen= 'EV'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'homeless':
            chosen= 'homeless'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'climate':
            chosen= 'climate'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'oil':
            chosen= 'oil'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'waste':
            chosen= 'waste'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'gas':
            chosen= 'gas'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'utility':
            chosen= 'utility'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'retail':
            chosen= 'retail'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'Los Angeles County':
            chosen2= ' LA County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'Orange County':
            chosen2= ' Orange County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'Riverside County':
            chosen2= ' Riverside County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'San Bernandino County':
            chosen2= ' San Bernandino County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'San Diego County':
            chosen2= ' San Diego County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, chosen3=chosen3, form=form, form2=form2, title="Welcome to Policy Edge")

#@app.route('/', methods=['GET', 'POST'])
#def index():
#    if "username" in session:
#        return redirect(url_for("loggedIn"))

#    return render_template('index.html' ,title="PolicyEdge agenda monitoring tracking service")

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
        flash('Welcome back '+username)
        ##Trend Pre-Load#####
        form = newIssue()
        form2 = newTrend()

        ##Main Issue three month#####

        a = date.today()+ relativedelta(weeks=2)
        b= str(a).replace("-","")
        twoweekAhead=int(b)
        c = date.today() + relativedelta(weeks=-16)
        d= str(c).replace("-","")
        lMonth=int(d)

        ##One week Trend#####

        e = date.today()+ relativedelta(weeks=1)
        f= str(e).replace("-","")
        weekAhead=int(f)
        g = date.today() + relativedelta(weeks=-2)
        h= str(g).replace("-","")
        weekBefore=int(h)

        ##One month Trend#####

        i = date.today()
        j= str(i).replace("-","")
        today=int(j)
        k = date.today() + relativedelta(weeks=-4)
        l= str(k).replace("-","")
        monthBefore=int(l)

        ##Three month Trend#####

        o = date.today() + relativedelta(weeks=-16)
        p= str(o).replace("-","")
        threeBefore=int(p)

        countyList = [" San Bernandino County ", " Riverside County ", " Orange County ", " San Diego County ", " LA County "]
        chosen2= countyList.pop(random.randrange(len(countyList)))
        words = set(nltk.corpus.words.words())
        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord=('comment limited''comment recieved''comment received 6''construction construction''budget budget''park park''declare said''conflict interest''source associated''activity defined''defined therefore''activity indirect''posted supplemental''supplemental contain''contain start''start official''official record''annexation annexation''click posted''number geographic''organizational activity''afternoon begin''begin source''text text''interest source''task force'
        'permit attached''exhibit exhibit''investment investment''palm palm''palm desert''greater chamber''page page''appendices thereto''fact provided''oath newly''time address''governing must''prior must''upon service''group offset''special special''tabulation place''january''august''june''speak queue''share tweet''zoom call''vice chair''unless otherwise''claim claim''appear shall''continue conduct''professional professional''vacant formerly''appoint serve''lake forest''tweet load''appropriation adjustment''finance authority''fountain valley''implement administer''subdivision name''alternate vacant''request speak''wishing speak''give card''formerly alternate''appointment currently''plus contingency''period four''four optional''legislative analyst''selection process''negotiator negotiator''financial analysis''categorical exemption''chapter reference''negative declaration''set forth''mechanical residential''taking additional''neither legislative''analyst financial''matter jurisdiction''separate discussion''south gate''three additional''none limit'
        'ability safely''removed considered''warrant register''form acceptable''undertake finalize''site review''floor area''street street''new business''doe doe''resolve find''find director''director determined''effectuate intent''mitigation program''master application''riverside county''member ending''conference litigation''waive full''parcel map''western riverside''update presentation''tentative map''adoption building''building fire''conference conference''quarter ending''initiate zoning''full waive''tentative parcel''see see''position member''ending member''district affected''contact person''result direct''san san''charter taken''aken contact''mayor taken''mayor designee''oceanside oceanside''association oceanside''change contact''orange county''pacific avenue''avenue pacific''waive full''provide direction''notice completion''parcel map''edition building''make necessary''measure expenditure''way way''specific plan''edition edition''determine result''result physical''physical change''change directly''introduce first''building edition''mayor behalf''costa mesa''direction regarding''specific plan''waive full ''neighborhood neighborhood''avenue avenue''alternatively discuss''discuss take''housing element''memorandum understanding''superior court''negotiation price''improvement project''purchase order''court case''one motion''take related''agenda ocean''cost account''account cost''grant funds''commission commission''listed agenda''article class''board airport''last day''project project''attachment attachment''land use''long beach''general fund''closed session''office department''regular meeting''community development''award contract''consent calendar''legal counsel''report relative''ordinance ordinance''reading ordinance''administrative officer''item consideration''staff report''recommendation recommendation''committee report''police department''exempt pursuant''chief executive''subject approval''second reading''real property''amendment agreement''successor agency''town town''city council''city manager''impact statement''authorize city''adopt resolution''code section''government code''city attorney''municipal code''code title''action approve''council city''resolution city''quality act ''public hearing''fiscal year''city clerk''environmental quality''receive file''public works''amount exceed''council action''resolution resolution''council consider''manager execute')

        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}, {'City': {'$not':{'$regex': " Los Angeles "}}}]}, {'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})

        box1=[]
        for x in agendaACounty:
            box1.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        tokens1=[]
        for w in box1:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord:
                    if w in words:
                        tokens1.append(w)
        grams1 = nltk.ngrams(tokens1, 2)

        fdist1 = nltk.FreqDist(grams1)

        box2=[]
        for x in agendaBCounty:
            box2.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        tokens2=[]
        for w in box2:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord:
                    if w in words:
                        tokens2.append(w)
        grams2 = nltk.ngrams(tokens2, 2)

        fdist2 = nltk.FreqDist(grams2)

        box3=[]
        for x in agendaCCounty:
            box3.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        tokens3=[]
        for w in box3:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord:
                    if w in words:
                        tokens3.append(w)
        grams3 = nltk.ngrams(tokens3, 2)

        fdist3 = nltk.FreqDist(grams3)

        topics = ["water", "cannabis", "EV", "homeless","climate", "oil","waste","gas","utility","retail","financial"]
        chosen = topics.pop(random.randrange(len(topics)))

        if request.method == 'GET':
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggedIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen,chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'cannabis':
            chosen= 'cannabis'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'water':
            chosen= 'water'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'EV':
            chosen= 'EV'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'homeless':
            chosen= 'homeless'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'climate':
            chosen= 'climate'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'oil':
            chosen= 'oil'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'waste':
            chosen= 'waste'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'gas':
            chosen= 'gas'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'utility':
            chosen= 'utility'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'retail':
            chosen= 'retail'
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'Los Angeles County':
            chosen2= ' LA County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2,form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'Orange County':
            chosen2= ' Orange County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'Riverside County':
            chosen2= ' Riverside County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'San Bernandino County':
            chosen2= ' San Bernandino County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2, form=form, form2=form2, title="Welcome to Policy Edge")
        elif request.method == 'POST' and request.form['select'] == 'San Diego County':
            chosen2= ' San Diego County '
            agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosen2}, { 'Date':{'$lte':today, '$gte':threeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
            agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':lMonth}}]}).sort('Date').sort('City')
            return render_template('loggenIn.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosen2=chosen2,  form=form, form2=form2, title="Welcome to Policy Edge")
    else:
        return redirect(url_for("login"))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    for key in list(session.keys()):
        session.pop(key) #logs user out
    return redirect(url_for("index"))

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

    ##LA Only County no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Only County Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Only County End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Only County both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##LA County and City no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and City Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and City End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and City Both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##LA County and Issue no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue Both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##LA County and Issue and City no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue and City Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue and City End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue and City Both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

######################
    ##Orange County Only County no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County Only County Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County Only County End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County Only County both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Orange County and City no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and City Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and City End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and City Both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Orange County and Issue no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue Both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Orange County and Issue and City no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue and City Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue and City End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue and City Both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

######################
    ##San Diego County Only County no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County Only County Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County Only County End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County Only County both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##San Diego County and City no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and City Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and City End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and City Both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##San Diego County and Issue no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue Both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##San Diego County and Issue and City no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue and City Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue and City End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue and City Both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
######################

    if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']:
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge Search Results")

    if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']=="":# Allows user to not input End date ==today
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]})
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    if request.form['select'] == 'Issue' and request.form['startdate_field'] =="" and request.form['enddate_field']=="":# Allows user to not input date
        agenda = mongo.db.Agenda.find({ '$text': { "$search": searchKey}})
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

######################


    ##LA  No selection just Criteria no dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA No selection just Start Date###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA No selection just End Date###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA No selection just Both dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##LA ISSue search only no dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA ISSue search and Start Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA ISSue search and End Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA ISSue search and both dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##LA Committee Search only no dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} ,{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee search and Start Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee search and End Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee search and both dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##LA Committee and Issue No dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} ,{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee and Issue search and Start Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee and Issue search and End Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee and Issue search and both dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
######################
    ##Long Beach  No selection just Criteria no dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach No selection just Start Date###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach No selection just End Date###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach No selection just Both dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Long Beach ISSue search only no dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach ISSue search and Start Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach ISSue search and End Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach ISSue search and both dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Long Beach Committee Search only no dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} ,{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee search and Start Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee search and End Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee search and both dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Long Beach Committee and Issue No dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} ,{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee and Issue search and Start Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee and Issue search and End Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee and Issue search and both dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ######################
    ##Riverside County Only County no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County Only County Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County Only County End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County Only County both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Riverside County and City no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and City Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and City End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and City Both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Riverside County and Issue no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue Both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

    ##Riverside County and Issue and City no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue and City Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue and City End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue and City Both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda, title = "PolicyEdge Search Results")

@app.template_filter('aTime')
def int2date(agDate: int) -> date:#Chages format of dates in charts
    year = int(agDate / 10000)
    month = int((agDate % 10000) / 100)
    day = int(agDate % 100)

    return date(year,month,day)

@app.route('/savedIssues', methods=['GET', 'POST'])
def savedIssues():
    if "username" in session:
        if mongo.db.User.find_one({'$and':[ {'username': session['username']} ,{'subscriptionActive': True}]}):
            if request.method == 'GET':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()+ relativedelta(days=30)
                b= str(a).replace("-","")
                today=int(b) #add 30 so new agendas will be caught
                c = date.today() + relativedelta(days=-90) #Change day to 7 otherwise too many emails.
                d= str(c).replace("-","")
                today_1month= int(d)

                ######Returns user saved issues#####
                issues_placeholder= []
                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.Issue':1, 'issues.City':1, 'issues.committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder
                ######Returns matching agendas from for loop below#####
                agenda=[]
                ####returns exact amount of items to loop through####
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['Issue'])
                    committee_Search= (issues_placeholder[y]['committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agenda.append(z)
                return render_template('savedIssues.html', issues_placeholders=issues_placeholder, form=form, agendas=agenda,  title='Monitor List')

            elif request.method == 'POST' and request.form['action'] == 'Add':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()+ relativedelta(days=30)
                b= str(a).replace("-","")
                today=int(b) #add 30 so new agendas will be caught
                c = date.today() + relativedelta(days=-90) #Change day to 7 otherwise too many emails.
                d= str(c).replace("-","")
                today_1month= int(d)

                #####Adds key to Issues########
                issue = request.form['monitor_search']
                cityKey = request.form['city_search']
                committeeKey = request.form['committee_search']
                countyKey = request.form['county_search']

                CompleteIssue = {
                    "Issue": issue,
                    "City": cityKey,
                    "committee": committeeKey,
                    "County": countyKey,
                }

                mongo.db.User.find_one_and_update({'username':user}, {'$push': {'issues':CompleteIssue}}, upsert = True)

                ######Returns user saved issues#####
                issues_placeholder= []

                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.Issue':1, 'issues.City':1, 'issues.committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder


                ######Returns matching agendas from for loop below#####
                agenda=[]
                ####returns exact amount of items to loop through####
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['Issue'])
                    committee_Search= (issues_placeholder[y]['committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agenda.append(z)

                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendas=agenda,  title='Monitor List')


            elif request.method == 'POST' and request.form['action']  == 'Delete':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()+ relativedelta(days=30)
                b= str(a).replace("-","")
                today=int(b) #add 30 so new agendas will be caught
                c = date.today() + relativedelta(days=-90) #Change day to 7 otherwise too many emails.
                d= str(c).replace("-","")
                today_1month= int(d)

                #####Delete request#######
                issue = request.form['monitor_search']
                cityKey = request.form['city_search']
                committeeKey = request.form['committee_search']
                countyKey = request.form['county_search']
                CompleteIssue = {
                    "Issue": issue,
                    "City": cityKey,
                    "committee": committeeKey,
                    "County": countyKey,
                }

                mongo.db.User.find_one_and_update({'username':user}, {'$pull': {'issues':CompleteIssue}}, upsert = True)

                ######Returns user saved issues#####
                issues_placeholder= []

                user_issues= mongo.db.User.find({'username':user}, {'_id': 0, 'issues.Issue':1, 'issues.City':1, 'issues.committee':1, 'issues.County':1}) #projects sub-documents to run in search
                for x in user_issues:
                    for y in range(len(x['issues'])):
                        issues_placeholder.append(x['issues'][y]) #Sends sub-document issues to issue_placeholder


                ######Returns matching agendas from for loop below#####
                agenda=[]
                ####returns exact amount of items to loop through####
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['Issue'])
                    committee_Search= (issues_placeholder[y]['committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agenda.append(z)

                return render_template('savedIssues.html', form=form, issues_placeholders=issues_placeholder, agendas=agenda,  title='Monitor List')
        else:
            return render_template('noSubscription.html')
    else:
        return redirect(url_for("login"))

@app.route('/success')
def success():
    return render_template("success.html", title='PolicyEdge subscription successful')

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

@app.route('/losangeles', methods=['GET', 'POST'])
def losangeles():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ { 'Date':{'$lte':int(today), '$gte':int(lMonth)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('losangeles.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring Los Angeles County Search Results")

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
        return render_template('orange.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring Riverside County Search Results")

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
        return render_template('riverside.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring Orange County Search Results")

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
        return render_template('sanbernandino.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring San Bernandino County Search Results")

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
        return render_template('sandiego.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring San Diego County Search Results")
    
if __name__ == '__main__':
    app.run(debug = True)













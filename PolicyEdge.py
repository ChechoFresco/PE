from flask_pymongo import PyMongo
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, json
from forms import searchForm, monitorListform
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
        b= str(a).replace("-","")
        today=int(b)

        ##########User roundup###############
        all_users= mongo.db.User.find({}, {'_id': 0, "username" : 1, "email": 1, 'agendaUnique_id':1, 'email':1, 'subscriptionActive':1, 'issues':1})#Creates list af all emails and usernames for sequence

        for x in all_users: #For each instance of a user
            if x['subscriptionActive'] == True: #Checks to see if user is subscribed

        ##################Deletes old object_id for users###############
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

        ###########Multiquery uses each _Search to run individual db.finds to create multiquery#########
                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$gte':int(today)}}]})
                    for query in Multiquery:#Places individualised results in agenda from Multiquery
                        agenda.append(query)
                        agenda2.append(issue_Search)
                        
        ###Information is grabbed from loop done below#######
                description=[]
                issueTopics=[]
                city=[]
                date=[]
                county=[]
                meeting_type=[]
                item_type=[]
                issueLinks=[]

                email_body=[]
                itemCount=0

                for issueTopic in agenda2:
                    issueTopics.append(issueTopic)

                for i in agenda: #Items selected to be sent
                    if i['_id'] not in userStoredAgendaId:#Checks to see item wasn't sent before
                        itemCount+=1
                        mongo.db.User.find_one_and_update({'username':x['username']}, {'$addToSet': {'agendaUnique_id':{'_id':i['_id'],'Date':i['Date']}}})# updates database with topics uniqueid
                        description.append(i['Description'])
                        city.append(i['City'])
                        county.append(i['County'])
                        meeting_type.append(i['MeetingType'])
                        item_type.append(i['ItemType'])
                        ###Date object#######
                        intDate= (str(i['Date']))
                        start_year = str(intDate[0:4])
                        start_month = str(intDate[4:6])
                        start_day = str(intDate[6:8])
                        date.append(start_month+'/'+start_day+'/'+start_year)
                        ###Weblink object#######
                        links=mongo.db.doc.find_one({"City":{'$regex': i['City'][1:-1], '$options': 'i'}},{'_id': 0,'webAdress': 1} )
                        issueLink= str(links).replace("{'webAdress': '","").replace("'}","")
                        issueLinks.append(issueLink)
                        
                ###Loop to fill in all issues for email#######
                for y in range(len(city)):#range(len)city is used because it gives accurate count of topics being sent
                    email_body.append("<p>The following issue '{}' will be brought before the {} {} in {} on {}.</p>  {} <br></br> <br></br> Provided is a link to the agendas {}. <br></br><br></br><br></br>".format(issueTopics[y],city[y],meeting_type[y],county[y],date[y],description[y], issueLinks[y]))

                if len(email_body)==0:
                    pass
                else:
                    subject = 'New Issue Alerts'
                    sender = 'AgendaPreciado@gmail.com'
                    msg = Message(subject, sender=sender, recipients=[x['email']])
                    ###Combines all issues into one#######
                    html_body= "\n".join(email_body)
                    msg.html= "<html'>Hello {},".format(x['username'])+ "<p>You have {} items today.</p>".format(itemCount)+"<body style ='margin: auto; background-color: lightgray; border: 2px solid; padding: 3rem; border-radius:2ch;'>"+html_body+"</body>"+ "<p> Thanks for your continued support,<br> <br><span style= 'color:#5e7cff; text-shadow: 1px 1px black'>Policy</span><span style= 'color:#fab935; text-shadow: 1px 1px black'>Edge</span></p> </html>"
                    mail.send(msg)
            else:
                pass

sched = BackgroundScheduler(timezone='UTC')
sched.add_job(check4Issues2email, 'interval', seconds=86400)
sched.start()

@app.route('/', methods=['GET', 'POST'])
def httpsroute():
    return redirect("https://www.policyedge.net/index", code = 301)

@app.route('/index', methods=['GET', 'POST'])
def index():
    ###DATE SETUP#######
    ##Main Issue three month#####
    a = date.today()+ relativedelta(weeks=2)
    b= str(a).replace("-","")
    twoweekAhead=int(b)

    c = date.today() + relativedelta(weeks=-12)
    d= str(c).replace("-","")
    threemonthBefore=int(d)

    ##One week Trend#####

    e = date.today()+ relativedelta(weeks=1)
    f= str(e).replace("-","")
    weekAhead=int(f)

    g = date.today() + relativedelta(weeks=-1)
    h= str(g).replace("-","")
    weekBefore=int(h)

    ##One month Trend#####

    i = date.today()
    j= str(i).replace("-","")
    today=int(j)

    k = date.today() + relativedelta(weeks=-4)
    l= str(k).replace("-","")
    monthBefore=int(l)

    ##One year Trend#####

    c = date.today() + relativedelta(weeks=-52)
    d= str(c).replace("-","")
    oneyearBefore=int(d)
    ####TREND SET-UP#######
    countyList = [" San Bernandino County ", " Riverside County ", " Orange County ", " San Diego County ", " LA County "]
    chosencountyList= countyList.pop(random.randrange(len(countyList)))
    chosencountyList2= countyList.pop(random.randrange(len(countyList)))
    chosencountyList3= countyList.pop(random.randrange(len(countyList)))

    ####Naughty Words#######
    words = set(nltk.corpus.words.words())
    stop_words=set(stopwords.words("english") + list(string.punctuation))
    SingleWord=('virtually''during''such''you''then''any''further''was''will''been''only''included''known''which''these''this''that''from''conduit revenue''civic center''travel tourism''trade travel''publicly live''comprehensive comprehensive''parking culver''signal hill''peter attendance''found conditioned''could found''access distributed''labor bond''release labor''applicable release''days applicable''approximately percent''potential recess'
                'recess purpose''back subsequent''recess purpose''information back''back subsequent''approach podium''disruptive approach''profane disruptive''slanderous profane''personal slanderous''extended another''expense local' 'keep informed''acting length''message longer''clarification response''question clarification''terrace grand'
                'grand terrace''walnut inclusive''directed reflect''eft manual''manual wire''wire eft''accepted ensure''aggregate sierra''possible bellflower''titled bell''authorized mike''mike waterfront''authorized privilege''various vista''communication oral ''oral communication ''every regularly''joint delegate''tiled seal'
                'together certain''instruct appropriate''categorically maintenance''assistant jeff ''tweedy mile' 'remote telephonic''right rebuttal''excepting right''speaking excepting''restricted speaking''documentation conclude''supporting documentation''minute initiation''single vote''category single''participation category'
                'reserved participation''possibility sense''finding possibility''made exception''link web''web link''forward individual''discretion come''come forward''previously enter''added president''president steppe''classified responsible''opportunity docket''body however''completely body''briefly completely''proceed briefly''permission proceed''status codify'
                'significant paragraph''bulletin outside''posting bulletin''refrain making''respectively buffy''buffy payroll''routine without''pending fletcher''total respectively''designed require''priority transferred''desired phone''transfer councilman''transfer councilwoman''citizen input''roll mark''mark larry''aside audience''also include''future reconvene'
                'needs voice''hold virtual''support oppose''would like''like formal''verbal brief''readily available''allegiance announcement''finding open''assembly social''allow continued''continued brown''authorization receipt''testimony beginning' 'disclosure constituent''constituent correspondence''need assistance''pertaining established''replacement respect'
                'method appointment''five please''bear letter''please basket''invocation pledge''portion oppurtunity''waiver accordance''policy administration''based favorable''favorable civil''assigned liason''best best''determination common''advance disposla''month ended''whether except''emergency due''pleace complete''submit written''adisory advisory''speaker slip''advisory advisory''within today'
                'comment limited''comment recieved''comment received 6''declare said''conflict interest''source associated''activity defined''defined therefore''activity indirect''posted supplemental''supplemental contain''contain start''start official'
                'official record''click posted''number geographic''organizational activity''afternoon begin''begin source''interest source''task force''permit attached''palm desert''greater chamber''appendices thereto''fact provided''oath newly''time address''governing must''prior must''upon service''group offset''tabulation place'
                'january''august''june''speak queue''share tweet''zoom call''vice chair''unless otherwise''appear shall''continue conduct''vacant formerly''appoint serve''lake forest''tweet load''appropriation adjustment''finance authority''fountain valley''implement administer''subdivision name''alternate vacant''request speak''wishing speak''give card''formerly alternate''appointment currently''plus contingency'
                'period four''four optional''legislative analyst''selection process''financial analysis''categorical exemption''chapter reference''negative declaration''set forth''mechanical residential''taking additional''neither legislative''analyst financial''matter jurisdiction''separate discussion''south gate''three additional'
                'none limit''ability safely''removed considered''warrant register''form acceptable''undertake finalize''site review''floor area''new business''resolve find''find director''director determined''effectuate intent''mitigation program''master application''riverside county''member ending''conference litigation''waive full''parcel map''western riverside''update presentation''tentative map''adoption building''building fire'
                'conference conference''quarter ending''initiate zoning''full waive''tentative parcel''position member''ending member''district affected''contact person''result direct''charter taken''aken contact''mayor taken''mayor designee''oceanside oceanside''association oceanside''change contact''orange county''pacific avenue''avenue pacific''waive full''provide direction''notice completion''parcel map''edition building''make necessary''measure expenditure'
                'specific plan''determine result''result physical''physical change''change directly''introduce first''building edition''mayor behalf''costa mesa''direction regarding''specific plan''waive full''alternatively discuss''discuss take''housing element''memorandum understanding''superior court''negotiation price''improvement project''purchase order''court case''one motion''take related''agenda ocean''cost account''account cost''grant funds''listed agenda'
                'article class''board airport''last day''land use''long beach''general fund''closed session''office department''regular meeting''community development''award contract''consent calendar''legal counsel''report relative''reading ordinance''administrative officer''item consideration''staff report''recommendation recommendation''committee report''police department''exempt pursuant''chief executive''subject approval''second reading''real property''amendment agreement''successor agency''city council'
                'city manager''impact statement''authorize city''adopt resolution''code section''government code''city attorney''municipal code''code title''action approve''council city''resolution city''quality act ''public hearing''fiscal year''city clerk''environmental quality''receive file''public works''amount exceed''council action''council consider''manager execute')

    agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':oneyearBefore}}]}, {'_id': 0, 'County':0, 'City':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
    agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList2}, { 'Date':{'$lte':today, '$gte':oneyearBefore}}]}, {'_id': 0, 'County':0, 'City':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
    agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County": chosencountyList3}, { 'Date':{'$lte':today, '$gte':oneyearBefore}}]}, {'_id': 0, 'County':0, 'City':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
    ####### Main Table##########
    box1=[]
    box2=[]
    box3=[]
    for x in agendaACounty:
        y=str(x)
        if x["Date"] > monthBefore:
            box1.extend(word_tokenize(y[34:150].lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        if x["Date"] > oneyearBefore:
            box2.extend(word_tokenize(y[34:150].lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
        if x["Date"] > threemonthBefore:
            box3.extend(word_tokenize(y[34:150].lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))
    week1=[]
    monthOne=[]
    monthThree=[]
    
    #######Box 1##########
    prev=None
    for w in box1:
        if w not in stop_words and len(w)>2:
            if w not in SingleWord:
                if w in words:
                    if str(w) != str(prev):
                        week1.append(w)
                    prev = w
    grams1 = nltk.ngrams(week1, 2)
    fdist1 = nltk.FreqDist(grams1)

    #######Box 2##########
    prev=None
    for aa in box2:
        if aa not in stop_words and len(aa)>2:
            if aa not in SingleWord:
                if aa in words:
                    if str(aa) != str(prev):
                        monthOne.append(aa)
                    prev = aa
    grams2 = nltk.ngrams(monthOne, 2)
    fdist2 = nltk.FreqDist(grams2)

    #######Box 3##########
    prev=None
    for bb in box3:
        if bb not in stop_words and len(bb)>2:
            if bb not in SingleWord:
                if bb in words:
                    if str(bb) != str(prev):
                        monthThree.append(bb)
                    prev = bb
    grams3 = nltk.ngrams(monthThree, 2)
    fdist3 = nltk.FreqDist(grams3)
    
    #######TOPIC SELECTION##########
    topics = ["reap","bids","solicit","cannabis", "EV", "homelessness","climate", "oil","waste","outdoor dining","financial"]
    chosen = topics.pop(random.randrange(len(topics)))

    ######Stats Occurancer##########
    if request.method == 'GET':
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, {"MeetingType":" City Council "}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3,chosencountyList=chosencountyList, agendaas=agendaa,chosen=chosen, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Cannabis' in request.form['select'] :
        chosen= 'cannabis'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Water' in request.form['select']:
        chosen= 'water'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'EV' in request.form['select']:
        chosen= 'EV'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Homeless' in request.form['select']:
        chosen= 'homeless'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Climate' in request.form['select']:
        chosen= 'climate'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Oil' in request.form['select']:
        chosen= 'oil'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Waste' in request.form['select']:
        chosen= 'waste'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Gas' in request.form['select']:
        chosen= 'gas'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Utility' in request.form['select']:
        chosen= 'utility'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Retail' in request.form['select']:
        chosen= 'retail'
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Los Angeles' in request.form['select'] :
        chosencountyList= ' LA County '
        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':threemonthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'San Bernandino' in request.form['select']:
        chosencountyList= ' San Bernandino County '
        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':threemonthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Orange County' in request.form['select']:
        chosencountyList= ' Orange County '
        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':threemonthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'San Diego' in request.form['select']:
        chosencountyList= ' San Diego County '
        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':threemonthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")
    elif request.method == 'POST' and 'Riverside' in request.form['select']:
        chosencountyList= ' Riverside County '
        agendaACounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':weekAhead, '$gte':weekBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaBCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':monthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaCCounty = mongo.db.Agenda.find({'$and':[ {"MeetingType":" City Council "}, {"County":chosencountyList}, { 'Date':{'$lte':today, '$gte':threemonthBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": chosen}}, { 'Date':{'$lte':twoweekAhead, '$gte':threemonthBefore}}]}).sort('Date',-1)
        return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2, fdist3s=fdist3, agendaas=agendaa,chosen=chosen, chosencountyList=chosencountyList, title="Welcome to Policy Edge")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if "username" in session:
        flash(session["username"])
        return redirect(url_for("index"))
    return render_template("register.html", title="Become a member of PolicyEdge's agenda monitoring services")

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
        return render_template('subscription.html', title='Please re-subscribe to PolicyEdge at any time. Los Angeles agenda monitoring service')
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

    ############################################
    ##Issue onlys###
    if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']:
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html', agendas=agenda,  title = "PolicyEdge Search Results")
    if request.form['select'] == 'Issue' and request.form['startdate_field'] and request.form['enddate_field']=="":# Allows user to not input End date ==today
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": searchKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]})
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    if request.form['select'] == 'Issue' and request.form['startdate_field'] =="" and request.form['enddate_field']=="":# Allows user to not input date
        agenda = mongo.db.Agenda.find({ '$text': { "$search": searchKey}})
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ############################################
    ##LA Only County no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Only County Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Only County End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Only County both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'LA County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##LA County and City no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and City Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and City End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and City Both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##LA County and Issue no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue Both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##LA County and Issue and City no dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue and City Start dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue and City End dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA County and Issue and City Both dates###
    if request.form['select'] == 'LA County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'LA County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ############################################
    ##Orange County Only County no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County Only County Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County Only County End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County Only County both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'Orange County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Orange County and City no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and City Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and City End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and City Both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Orange County and Issue no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue Both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Orange County and Issue and City no dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue and City Start dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue and City End dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Orange County and Issue and City Both dates###
    if request.form['select'] == 'Orange County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Orange County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ############################################
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA No selection just Start Date###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA No selection just End Date###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA No selection just Both dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##LA ISSue search only no dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA ISSue search and Start Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA ISSue search and End Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA ISSue search and both dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##LA Committee Search only no dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} ,{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee search and Start Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee search and End Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee search and both dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##LA Committee and Issue No dates###
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} ,{'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee and Issue search and Start Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee and Issue search and End Date##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##LA Committee and Issue search and both dates##
    if request.form['select'] == 'LA Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Los Angeles', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    
    ############################################
    ##Long Beach  No selection just Criteria no dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}},{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach No selection just Start Date###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach No selection just End Date###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach No selection just Both dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']=="" :
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Long Beach ISSue search only no dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach ISSue search and Start Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach ISSue search and End Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach ISSue search and both dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Long Beach Committee Search only no dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} ,{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee search and Start Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee search and End Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee search and both dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$regex': searchKey, '$options': 'i' }} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Long Beach Committee and Issue No dates###
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} ,{'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee and Issue search and Start Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee and Issue search and End Date##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':today, '$gte':int(end)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}}, {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Long Beach Committee and Issue search and both dates##
    if request.form['select'] == 'Long Beach Committees' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search'] and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {"MeetingType":{'$not':{'$regex': "City Council", '$options': 'i' }}}, {'$text': { "$search": deepKey}} , {'City': {'$regex': 'Long Beach', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ############################################
    ##Riverside County Only County no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County Only County Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County Only County End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County Only County both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Riverside County and City no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and City Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and City End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and City Both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Riverside County and Issue no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue Both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##Riverside County and Issue and City no dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue and City Start dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue and City End dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##Riverside County and Issue and City Both dates###
    if request.form['select'] == 'Riverside County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'Riverside County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ############################################
    ##San Diego County Only County no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County Only County Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County Only County End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County Only County both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##San Diego County and City no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and City Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and City End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and City Both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##San Diego County and Issue no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue Both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##San Diego County and Issue and City no dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue and City Start dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue and City End dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Diego County and Issue and City Both dates###
    if request.form['select'] == 'San Diego County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Diego County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date').sort('City')
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ############################################
    ##San Bernandino County Only County no dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County Only County Start dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(start)}}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County Only County End dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':today, '$gte':int(end)}}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County Only County both dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, { 'Date':{'$lte':int(end), '$gte':int(start)}}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##San Bernandino County and City no dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and City Start dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and City End dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and City Both dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']=="":
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##San Bernandino County and Issue no dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']=="" and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and Issue Start dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and Issue End dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and Issue Both dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']==""  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

    ##San Bernandino County and Issue and City no dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }}, {'City': {'$regex': searchKey, '$options': 'i' }},{'$text': { "$search": deepKey}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and Issue and City Start dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field']=="" and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(start)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and Issue and City End dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field']=="" and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':today, '$gte':int(end)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")
    ##San Bernandino County and Issue and City Both dates###
    if request.form['select'] == 'San Bernandino County' and request.form['startdate_field'] and request.form['enddate_field'] and request.form['primary_search']  and request.form['secondary_search']:
        agenda = mongo.db.Agenda.find({'$and':[ { '$or':[{"MeetingType":{'$regex': "City Council" }},{"MeetingType":{'$regex': "Special Meeting", '$options': 'i' }}]}, {'County': {'$regex': 'San Bernandino County', '$options': 'i' }},{'$text': { "$search": deepKey}}, {'City': {'$regex': searchKey, '$options': 'i' }}, { 'Date':{'$lte':int(end), '$gte':int(start)}}]}).sort('Date',-1)
        return render_template('results.html',searchKey=searchKey,deepKey=deepKey, agendas=agenda, title = "PolicyEdge Search Results")

@app.template_filter('aTime')
def int2date(agDate: int) -> date:
    agDate=(str(agDate))
    dt = datetime.strptime(agDate, '%Y%m%d')
    return (dt.strftime('%B %d, %Y'))

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
                c = date.today() + relativedelta(days=-7)
                d= str(c).replace("-","")
                today_1month= int(d)

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

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agendaa.append(z)

                return render_template('savedIssues.html', issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Monitor List')

            elif request.method == 'POST' and request.form['action'] == 'Add':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()+ relativedelta(days=30)
                b= str(a).replace("-","")
                today=int(b) #add 30 so new agendas will be caught
                c = date.today() + relativedelta(days=-7)
                d= str(c).replace("-","")
                today_1month= int(d)

                #####Adds key to Issues########
                issue = request.form['monitor_search']
                cityKey = request.form['city_search']
                committeeKey = request.form['committee_search']
                countyKey = request.form['county_search']

                CompleteIssue = {
                    "searchWord": issue,
                    "City": cityKey,
                    "Committee": committeeKey,
                    "County": countyKey,
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

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agendaa.append(z)

                return render_template('savedIssues.html',issues_placeholders=issues_placeholder, form=form, agendaas=agendaa,  title='Monitor List')


            elif request.method == 'POST' and request.form['action']  == 'Delete':
                form = monitorListform()
                user = session["username"]

                #####Creates dates########
                a = date.today()+ relativedelta(days=30)
                b= str(a).replace("-","")
                today=int(b) #add 30 so new agendas will be caught
                c = date.today() + relativedelta(days=-15)
                d= str(c).replace("-","")
                today_1month= int(d)

                #####Delete request#######
                issue = request.form['monitor_search']
                cityKey = request.form['city_search']
                committeeKey = request.form['committee_search']
                countyKey = request.form['county_search']
                CompleteIssue = {
                    "searchWord": issue,
                    "City": cityKey,
                    "Committee": committeeKey,
                    "County": countyKey,
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
                ####returns exact amount of topics to loop through####
                for y in range(len(issues_placeholder)):
                    city_Search= (issues_placeholder[y]['City'])
                    issue_Search= (issues_placeholder[y]['searchWord'])
                    committee_Search= (issues_placeholder[y]['Committee'])
                    county_Search= (issues_placeholder[y]['County'])

                    Multiquery=mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$regex': committee_Search,  '$options': 'i' }}, {"City":{'$regex': city_Search, '$options': 'i'}}, {"County":{'$regex': county_Search, '$options': 'i'}}  ,{'Description': { "$regex": issue_Search,  '$options': 'i' }}, { 'Date':{'$lte':int(today), '$gte':int(today_1month)}}]})

                    for z in Multiquery:
                        agendaa.append(z)

                return render_template('savedIssues.html', form=form, issues_placeholders=issues_placeholder, agendaas=agendaa,  title='Monitor List')
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
        return render_template('losangeles.html',whittiers=whittier,westlakeVillages=westlakeVillage,westHollywoods=westHollywood,westCovinas=westCovina,walnuts=walnut,vernons=vernon,torrances=torrance,templeCitys=templeCity,southGates=southGate,southelMontes=southelMonte,signalHills=signalHill,sierraMadres=sierraMadre,santaMonicas=santaMonica,santafeSpringss=santafeSprings,santaClaritas=santaClarita,sanMarinos=sanMarino,sanGabriels=sanGabriel,sanFernandos=sanFernando,sanDimass=sanDimas,sPasadenas=sPasadena,rosemeads=rosemead,rollinghillsEstates=rollinghillsEstate,rollingHillss=rollingHills,redondoBeachs=redondoBeach,ranchopalosVerdess=ranchopalosVerdes,pomonas=pomona,picoRiveras=picoRivera,pasadenas=pasadena,paramounts=paramount,palosverdesEstates=palosverdesEstates,palmdales=palmdale,norwalks=norwalk,montereyParks=montereyPark,montebellos=montebello,monrovias=monrovia,maywoods=maywood,manhattanBeachs=manhattanBeach,malibus=malibu,lynwoods=lynwood,losAngeless=losAngeles,longBeachs=longBeach,lomitas=lomita,lawndales=lawndale,lancasters=lancaster,lakewoods=lakewood,laVernes=laVerne,laPuentes=laPuente,laMiradas=laMirada,lahabraHeightss=lahabraHeights,lacanadaFlintridges=lacanadaFlintridge,irwindales=irwindale,inglewoods=inglewood,huntingtonParks=huntingtonPark,hiddenHillss=hiddenHills,hermosaBeachs=hermosaBeach,hawthornes=hawthorne,hawaiianGardenss=hawaiianGardens,glendoras=glendora,glendales=glendale,gardenas=gardena,elSegundos=elSegundo,elMontes=elMonte,duartes=duarte,downeys=downey,diamondBars=diamondBar,culverCitys=culverCity, cudahys=cudahy,covinas=covina,commerces=commerce,claremonts=claremont,cityIndustrys=cityIndustry,cerritoss=cerritos,carsons=carson,calabasass=calabasas,agouraHillss=agouraHills,alhambras=alhambra,arcadias=arcadia,artesias=artesia,azusas=azusa,baldwinParks=baldwinPark,bells=bell,bellflowers=bellflower, beverlyHillss=beverlyHills,comptons=compton, bradburys=bradbury, burbanks=burbank,title = "PolicyEdge agenda tracking monitoring Los Angeles County Search Results")


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

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug = True)













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

app = Flask(__name__,)

app.config['MONGO_URI'] = os.environ.get("MONGO_URI")
app.config['MAIL_SERVER']='smtp.gmail.com'#Email
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.secret_key = os.environ.get("SESS_KEY")

nltk.download('punkt')
nltk.download('stopwords')

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
        a = date.today()+ relativedelta(weeks=2)
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-1)
        d= str(c).replace("-","")
        lMonth=int(d)

        e = date.today()+ relativedelta(weeks=1)
        f= str(e).replace("-","")
        todayAlt=int(f)
        g = date.today() + relativedelta(weeks=-1)
        h= str(g).replace("-","")
        lMonthAlt=int(h)

        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'water'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendab = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'cannabis'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendac = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'EV'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendad = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'homeless'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendae = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'rfp'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendaf = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'sheriff'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendag = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'climate'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendah = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'military'}},{ 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendaWest = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Beverly Hills " , " Culver City " , " Malibu " , " Santa Monica " , " West Hollywood "]}}, { 'Date':{'$lte':todayAlt, '$gte':lMonthAlt}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaSanGab = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Alhambra "," Arcadia "," Azusa "," Baldwin Park "," Bradbury "," Covina "," Diamond Bar "," Duarte "," El Monte "," Glendora "," City of Industry "," Irwindale "," La Canada Flintridge "," La Puente "," La Verne "," Monrovia "," Montebello "," Monterey Park "," Pasadena "," Pomona "," Rosemead "," San Dimas "," San Gabriel "," San Marino "," Sierra Madre "," South El Monte ", " S Pasadena ", " Temple City "," Walnut "," West Covina "]}}, { 'Date':{'$lte':todayAlt, '$gte':lMonthAlt}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaGateway = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Lakewood "," Long Beach "," Signal Hill "," Compton ", " Lynwood ", " South Gate ", " Cudahy ", " Bell ", " Maywood ", " Vernon ", " Bell Gardens ", " Commerce ", " Downey ", " Pico Rivera ", " Santa Fe Springs "," Whittier ", " Santa Fe Springs ", " Norwalk ", " La Mirada ", " Cerritos ", " Hawaiian Gardens ", " Bellflower ", " Paramount "," Artesia "]}}, { 'Date':{'$lte':todayAlt, '$gte':lMonthAlt}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaSouthbay = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Torrance "," Carson "," Lomita "," Rancho Palos Verdes "," Rolling Hills "," Rolling Hills Estates "," Redondo Beach "," Hermosa Beach "," Manhattan Beach "," El Segundo "," Hawthorne "," Lawndale "," Gardena "]}}, { 'Date':{'$lte':todayAlt, '$gte':lMonthAlt}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaSanFer = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Agoura Hills " , " Burbank " , " Calabasas " , " Glendale " , " Hidden Hills " , " San Fernando " , " Westlake Village "]}}, { 'Date':{'$lte':todayAlt, '$gte':lMonthAlt}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaLAcomm = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not': {'$regex': " City Council ", '$options': 'i' }}}, {"City": " Los Angeles "},{ 'Date':{'$lte':todayAlt, '$gte':lMonthAlt}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})

        box1=[]
        for x in agendaWest:
            box1.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord1=('dobi''12727 wasshington''tenant space''space 463''463 north''north bedford''covering dates''single-family residence''331 north''north oakhurst'"9763""15061""vicente blvd""andweho.granicus.com/generatedagendaviewer.php""text alert""presiding officer""camden""discretion presiding""in-person""agreement.staff""received""voterequirement""305""andapproval""2022""csa"'file.staff'"ordinance.staff printouta""printout description""actionstaff""weho.granicus.com/generatedagendaviewer.php""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""manzano""tony""higgins""6:00""witzansky""ashcraft""chen""griffiths""ralph""mike""jennifer""paul""ken""robertson""viki""copeland""5:30""16.""17.""safety""acceptance""advisory""without""establishing""whittier""hand""virtual""given""introduce""week""recognition""2023""stop""mid-year""would""baldwin""verne""monterey""puente""due""duarte""audience""monte""pasadena""alhambra""rosemead""covina""valley""gabriel""pomona""n/a""continued""1383""azusa""allowed""held""written""fee""adjourned""number""hawthorne""terms""potential""options""chief""54956.9""check""exempt""conditional""excluded""folder""complete""estimated""refer""understanding""number""drive""April""april""january""february""May""june""july""august""september""october""november""december""2020""2021""printed""complete""2022""carson""torrance""redondo""palos""verdes""rolling""gardena""hills""rancho""exhibit""contact""pulled""lawndale""link""actions""successor""draft""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""manhattan""lomita""hermosa""application""required""attachment""separate""roll""proclamation""legislative""increase""two""requested""conduct""santa""11.""final""presentation""via""presentations""entitled""signal""treasurer""existing""pledge""center""adopting""subsequent""possible""summary""committee""planning""support""12.""councilmember""presented""allegiance""notice""2022.""bill""specific""enter""account""mirada""information""accept""compliance""please""case""resources""make""company""submitted""bodies""oral""board""monthly""person""requests" "schedule" "legal" "chambers" "enacted" "committees" "certain" "pico" "litigation" "south" "rivera" "boards" "upon" "submit" "made" "limited" "located" "findings" "human" "well" "declaring" "future" "alternatively" "hill" "various" "relating" "attachments" "13." "2021-22" "control" "activities" "and/or" "july" "continue" "system" "downey" "payment" "vote" "appointment" "element" "warrants" "none" "measure" "open" "american" "brown" "announcements""assistance""term""change""apn""response""springs""offset""requirements""counsel""claims""revised""map""direction""one-year""amended""quality""appropriate""opportunity""remote""appointments""regulations""transportation""commissions""adding""designated""also""shall""participate""hall""hours""norwalk""14.""accordance""federal""cerritos""event""adopted""rehabilitation""invocation""separately""6:30""payroll""association""plans""2021-2022""name""installation""administrator""demands""gate""residential""jurisdiction""on-call""assembly""provisions""redevelopment""operating""54953""bellflower""civic""vernon""15.""council/successor""specifications""communications""dba""not-to-exceed""recommendations""city" "council" "recommendation" "public" "agenda" "meeting" "2022" "resolution" "approve" "report""staff" "page""items""services""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""manager""agreement""action""minutes""section" "department" "item" "code" "may" "project""authorize""consent""adopt""california""office""contract""regular""comments""agency""2021""amount""mayor""calendar""january" "february" "time" "suggested" "session" "member" "file" "attorney" "approval" "ordinance" "government" "execute" "use" "receive" "beach" "long" "development" "pursuant" "amendment" "general" "April" "program" "state" "address" "community" "year" "plan" "approving" "clerk" "members" "meetings" "authorizing" "closed" "grant" "reading" "inc." "fiscal" "provide" "district" "recommends" "consideration" "related" "municipal" "one" "business" "local" "participation" "consider" "call" "provided" "act" "non-agenda" "lynwood" "emergency" "reports" "tuesday" "los" "period" "works" "street" "review" "discussion" "angeles" "budget" "warrant" "citywide" "iii" "avenue" "order" "hearing" "procedures" "fund" "housing" "documents" "successor" "title" "new" "recommended" "wishing" "approved" "speakers" "register" "amending" "funds" "motion" "necessary" "allotted" "annual" "comment" "teleconference" "instructions" "covid" "matters" "non-" "regarding" "additional" "form" "county" "authority" "request" "including" "proposed" "group" "designee" "p.m." "commission" "considered" "month" "bell" "update" "waive" "commerce" "chapter" "full" "award" "property" "conference" "improvement" "removed" "special" "5:00" "ordinances" "total" "listed""read""exceed""adoption""covid-19""take""llc""boulevard""funding""ceqa""director""within""june""routine""three""following""unless""capital""cudahy""amendments""improvements""subject""attached""prior""zoom""compton""service""361""10.""dated""second""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""management""first""discuss")
        tokens1=[]
        for w in box1:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord1:
                    tokens1.append(w)
        grams1 = nltk.ngrams(tokens1, 2)

        fdist1 = nltk.FreqDist(grams1)

        box2=[]
        for x in agendaSanGab:
            box2.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord2=('pdf''1424 street''moises''alhambra''view_id=10''fleet group''mayor sign''proclamation declaring''joint powers''office expire''requested mayor''traffic safety''//lacanadaflintridge-ca.granicus.com/generatedagendaviewer.php view_id=4''view_id=2 event_id=1150''rules update''inspections residential''residential inspection''inspection scope''scope repairs''queue heard''number potential''potential cases''dick richards'"injuryintersectionpedestrianaggressiveoverturneddistractedbroadsidesideswipehit""planningminimal""communitypublic""lark ellen""sheet""2020 2020""property located""50k""100k+""10k""2022""differential1other""2022""august""september""july""october""may desirable""additional related""related may""california environmental""environmental quality""grant program""consideration approval""south pasadena""general plan""provide direction""reading ordinance""roll call""considered routine""second reading""item consideration""west covina""one motion""state california""quality ceqa""first reading""take following""general fund""total cost""items listed""purchase order""conference legal""baldwin park""award contract""business item""amount exceed""listed considered""following actions""amount not-to-exceed""cost item""item budgeted""assembly bill""legal counsel""approval minutes""minutes february""taking additional""motion unless""monterey park""minutes january""oral communications""senate bill""enacted one""call order""steps necessary""march page""ceqa guidelines""financing parking""water page""warrant register""state emergency""waive reading""pursuant 54956.9""necessary finalize""notice completion""pledge allegiance""legislative bodies""january page""direct undertake""undertake steps""february page""local emergency""take additional""matters listed""memorandum understanding""ordinance amending""meetings attended""separate discussion""form approved""standing committee""7:00 p.m.""contract amount""block grant""valley boulevard""specific plan""attended expense""police department""california department""urgency ordinance""draft map""minutes per""claims demands""general election""items removed""business none""budgeted n/a""item removed""removed separate""adoption ordinance""wishing address""set forth""use permit""regarding item""account n/a""n/a cost""pomona california""inc. amount""reading adoption""parks recreation""capital improvement""budget amendment""cost n/a""n/a account""state law""election held""page february""grant funds""remote teleconference""assistance grant""teleconference meetings""exempt california""california amending""covina california""single motion""time members""direction regarding""litigation pursuant""meetings legislative""legislative body""members audience""approving warrant""state ceqa""councilmember chavez""first amendment""2021-2029 element""february 20.""amending chapter""improvements project""five minutes""operating budget""limited minutes""dated january""director finance""tract map""meetings pursuant""pursuant california""california approving""change order""comprehensive financial""within subject""subject matter""matter jurisdiction""attachment duarte""duarte draft""entitled ordinance""january 20.""replacement project""mid-year budget""sierra madre""ordinance ordinance""improvement program""program budget""per speaker""pomona page""page printed""ordinance entitled""strategic plan""change orders""plan amendment""conditional use""total amount""discussion items""discussion direction""allowing certain""certain claims""finance director""routine enacted""urban lot""grant cdbg""speaker card""tuesday june""address item""minutes special""wish speak""land use""monthly investment""register demands""agency/housing authority/financing""page march""enter contract""held tuesday""amending 2021-""january february""hearings none""three minutes""department administration""audience may""future items""committee councilmember""inviting bids""fire department""ending june""small business""plans specifications""person wishing""speaker limited""items unless""existing litigation""tuesday february""existence local""items business""proposed project""effect environment""authorizing submittal""second amendment""discussion regarding""may speak""counsel existing""consider adopting""items considered""6:00 p.m.""finance department""items may""continuous minutes""puente park""may address""ceqa pursuant""none scheduled""otherwise case""case item""contract amendment""draft maps""financial statements""make necessary""item may""specific item""minutes december""authorizing payment""governor newsom""may time""full reading""consideration consider""boards commission""city council""city manager""recommended city""recommended action""public hearing""consent calendar""council city""adopt resolution""authorize city""council meeting""fiscal year""staff recommends""staff report""recommends city""los angeles""resolution city""regular meeting""code section""municipal code""government code""receive file""successor agency""closed session""city attorney""council approve""services agreement""city clerk""public comment""council adopt""authority monte""recommendation recommended""housing authority""manager execute""meeting agenda""community development""san gabriel""council member")
        tokens2=[]
        for w in box2:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord2:
                    tokens2.append(w)
        grams2 = nltk.ngrams(tokens2, 2)

        fdist2 = nltk.FreqDist(grams2)

        box3=[]
        for x in agendaGateway:
            box3.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord3 =('finance \\uf0b7''thecity''______ councilof ''andadopting''required''14500 firestone''andaccept''downeymunicipal reference''offset transfer''priority transferred' 'transfer managerdepartment.office''anddecrease citywideactivities''22- ofthe''transferred citywideactivities''introduce 22-''building regulations''recommendation.page 18city''ofthe repealing''repealing recasting''recasting chapter''price thirddistrictsuggested''article viii''viii building''1 000 offset''500 offset''negative declaration''managerdepartment.office price''suely saro''associates inc.'"group""american disabilities""5:00""27city""one-time""suzie""palos verdes""bellflower""councildistrict""councilwoman""august""september""july""october""562""411""boulevardcivic""2022""city council""city manager""consent calendar""action approve""approve recommendation""suggested action""council city""city attorney""long beach""authorize city""council agenda""code section""government code""office department""closed session""city clerk""resolution city""adopt resolution""receive file""staff recommends""council member""recommends city""address city""regular meeting""fiscal year""agenda item""item may""page city""public works""public participation""los angeles""council meeting""non-agenda items""recommendation city""meeting procedures""page agenda""recommendation approve""wishing address""municipal code""items time""time allotted""allotted minutes""speakers wishing""may use""use instructions""instructions provided""provided section""section iii""iii covid""covid meeting""procedures page""minutes speakers""non- agenda""successor agency""public hearing""council consider""participation non-agenda""council non-""agenda public""city long""warrant register""recommendation staff""recommended city""council approve""recommendation receive""citywide office""manager designee""beach tuesday""public comment""pursuant government""council regular""public comments""recommendation adopt""staff report""council adopt""community development""agenda items""item report""city lynwood""recommendation page""manager execute""roll call""designee execute""one motion""removed consent""recommendation authorize""meeting minutes""consent agenda""approved city""agenda teleconference""calendar items""general plan""professional services""department city""amount exceed""city compton""execute agreement""council members""call order""meeting agenda""authorizing city""pledge allegiance""form approved""resolution authorizing""members public""take action""teleconference :00""improvement project""new business""february city""city cudahy""approve minutes""angeles county""meetings city""council receive""three minutes""enacted one""city commerce""full reading""related item""members city""considered routine""entitled resolution""staff recommendation""discuss take""action related""pico rivera""agenda city""waive reading""alternatively discuss""separate discussion""calendar considered""consideration possible""possible action""resolution entitled""documents item""attached resolution""ordinance amending""agreement city""tuesday february""district office""signal hill""may removed""capital improvement""brown act""meeting city""award contract""council requested""listed consent""council agency""tuesday march""local emergency""mayor execute""santa springs""january city""adopt attached""mayor pro""development agreement""conference legal""resolution approving""report city""pro tem""page page""parks recreation""recommendation recommended""regular city""legal counsel""items listed""attachments staff""general fund""waive full""south gate""tuesday january""page presented""grant program""6:30 p.m.""contract amount""report attachment""city bell""file report""council/successor agency""council meetings""council successor""investment report""state california""march city""may enacted""reading adopt""county los""assembly bill""quality act""clerk office""agenda consent""vice mayor""city santa""listed agenda""year 2021-22""documents necessary""considered separately""subsequent amendments""increase appropriations""city staff""council recommendation""california environmental""environmental quality""public hearings""execute documents""city pico""housing element""read title""total amount""pursuant california""agenda march""discussion items""item consideration""p.m. city""agency regular""meeting tuesday""city administrator""council authorize""police department""amendment contract""via zoom""clerk recommendation""beach municipal""manager department""adoption resolution""development block""block grant""project cip""agenda report""items considered""additional one-year""ceqa guidelines""second reading""ordinances resolutions""municipal election""boards commissions""minutes city""routine matters""register dated""appropriations general""authorizing mayor""redevelopment agency""public safety""california government""execute amendment""march page""city hall""report resolution""proposed resolution""approve authorize""necessary documents""department public""file city""consider adopting""act ceqa""manager enter""council chambers""items consent""specific items""items unless""council comments""agency member""recommendation recommendation""meeting page""report public""planning commission""minutes january""provide direction""general municipal""section 54956.9""works department""matters listed""direct staff""housing successor""ocean boulevard""services suggested""lynwood city""services city""acted upon""human resources""adopt ordinance""bell gardens""plans specifications""address council""attorney suggested""civic chambers""chambers :00""documents including""discretion city""acceptable city""ordinance city""community redevelopment""california department""real property""motion waive""legislative body""treasurer report""january 2022.""presented city""remote teleconference""legislative bodies""consider adoption""consider approving""grant funds""authorize mayor""city downey""agenda ocean""boulevard civic""works suggested""vote item""teleconference meetings""conference labor""session report")
        tokens3=[]
        for w in box3:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord3:
                    tokens3.append(w)
        grams3 = nltk.ngrams(tokens3, 2)

        fdist3 = nltk.FreqDist(grams3)

        box4=[]
        for x in agendaSouthbay:
            box4.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord4=('rolling hills''definitions''17.96 ''2022california''manhattan''written''councilapprove''22-0644 written''proclamation declaring''declaring october''view_id=5 event_id=2081''suja lowenthal''12:46 view_id=5''control district''perry street''measure november''uses zoning''uses specified''publish summary''summary newspaper''days post''post bulletin''attorney-client section54956.9' 'agency/city september' '2023 2025' 'price terms' '2025 anamount' 'negotiation price' 'managergreg waterfront' 'september 2022recommendation' 'servicesfor 2023' 'professional servicesagreement' '-the 54956.8.agency''54956.8.agency managergreg' 'portion apn' 'whichever occurs' 'professional servicesfor' 'losangeles county' 'ordinances resolutions' 'salary range''godinez council:1.' "kapovich""isauthorized""viki""copeland""witzansky""authority/successor"".name""amendingthe""negotiator""mike""naughton""vanessa""myra""amendingthe""carson""classification""human resources""privilege""closedsession""https""real property""property negotiator""none.recommendation ""2022""//lomita.granicus.com/generatedagendaviewer.php""redondo beach""rancho palos""palos verdes""hermosa beach""//rpv.granicus.com/generatedagendaviewer.php""may desirable""additional related""related may""california environmental""environmental quality""grant program""consideration approval""south pasadena""general plan""provide direction""reading ordinance""roll call""considered routine""second reading""item consideration""west covina""one motion""state california""quality ceqa""first reading""take following""general fund""total cost""items listed""purchase order""conference legal""baldwin park""award contract""business item""amount exceed""listed considered""following actions""amount not-to-exceed""cost item""item budgeted""assembly bill""legal counsel""approval minutes""minutes february""taking additional""motion unless""monterey park""minutes january""oral communications""senate bill""enacted one""call order""steps necessary""march page""ceqa guidelines""financing parking""water page""warrant register""state emergency""waive reading""pursuant 54956.9""necessary finalize""notice completion""pledge allegiance""legislative bodies""january page""direct undertake""undertake steps""february page""local emergency""take additional""matters listed""memorandum understanding""ordinance amending""meetings attended""separate discussion""form approved""standing committee""7:00 p.m.""contract amount""block grant""valley boulevard""specific plan""attended expense""police department""california department""urgency ordinance""draft map""minutes per""claims demands""general election""items removed""business none""budgeted n/a""item removed""removed separate""adoption ordinance""wishing address""set forth""use permit""regarding item""account n/a""n/a cost""pomona california""inc. amount""reading adoption""parks recreation""capital improvement""budget amendment""cost n/a""n/a account""state law""election held""page february""grant funds""remote teleconference""assistance grant""teleconference meetings""exempt california""california amending""covina california""single motion""time members""direction regarding""litigation pursuant""meetings legislative""legislative body""members audience""approving warrant""state ceqa""councilmember chavez""first amendment""2021-2029 element""february 20.""amending chapter""improvements project""five minutes""operating budget""limited minutes""dated january""director finance""tract map""meetings pursuant""pursuant california""california approving""change order""comprehensive financial""within subject""subject matter""matter jurisdiction""attachment duarte""duarte draft""entitled ordinance""january 20.""replacement project""mid-year budget""sierra madre""ordinance ordinance""improvement program""program budget""per speaker""pomona page""page printed""ordinance entitled""strategic plan""change orders""plan amendment""conditional use""total amount""discussion items""discussion direction""allowing certain""certain claims""finance director""routine enacted""urban lot""grant cdbg""speaker card""tuesday june""address item""minutes special""wish speak""land use""monthly investment""register demands""agency/housing authority/financing""page march""enter contract""held tuesday""amending 2021-""january february""hearings none""three minutes""department administration""audience may""future items""committee councilmember""inviting bids""fire department""ending june""small business""plans specifications""person wishing""speaker limited""items unless""existing litigation""tuesday february""existence local""items business""proposed project""effect environment""authorizing submittal""second amendment""discussion regarding""may speak""counsel existing""consider adopting""items considered""6:00 p.m.""finance department""items may""continuous minutes""puente park""may address""ceqa pursuant""none scheduled""otherwise case""case item""contract amendment""draft maps""financial statements""make necessary""item may""specific item""minutes december""authorizing payment""governor newsom""may time""full reading""consideration consider""boards commission""city council""city manager""recommended city""recommended action""public hearing""consent calendar""council city""adopt resolution""authorize city""council meeting""fiscal year""staff recommends""staff report""recommends city""los angeles""resolution city""regular meeting""code section""municipal code""government code""receive file""successor agency""closed session""city attorney""council approve""services agreement""city clerk""public comment""council adopt""authority monte""recommendation recommended""housing authority""manager execute""meeting agenda""community development""san gabriel""council member")
        tokens4=[]
        for w in box4:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord4:
                    tokens4.append(w)
        grams4 = nltk.ngrams(tokens4, 2)

        fdist4 = nltk.FreqDist(grams4)

        box5=[]
        for x in agendaSanFer:
            box5.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord5=('onhow''aatachment''2022staff''adevaadministrative''yellow cardmust''cardmust commentperiod.council''interim urgency''prima facie''facie speed''limits segments''north limits''building standards''publicworks departmentrecommendation''segments ofsan''ofsan fernando''fernando north''george izay''arezzo italy''12:39 current''10/6/2022 9:03:33''9:03:33 am10''attending virtually''posted website'"reportattachment""1attachment""2attachment""3attachment""joint""attendance""govt""view_id=6""//burbank.granicus.com/generatedagendaviewer.php""2022"'file.staff'"ordinance.staff printouta""printout description""actionstaff""weho.granicus.com/generatedagendaviewer.php""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""manzano""tony""higgins""6:00""witzansky""ashcraft""chen""griffiths""ralph""mike""jennifer""paul""ken""robertson""viki""copeland""5:30""16.""17.""safety""acceptance""advisory""without""establishing""whittier""hand""virtual""given""introduce""week""recognition""2023""stop""mid-year""would""baldwin""verne""monterey""puente""due""duarte""audience""monte""pasadena""alhambra""rosemead""covina""valley""gabriel""pomona""n/a""continued""1383""azusa""allowed""held""written""fee""adjourned""number""hawthorne""terms""potential""options""chief""54956.9""check""exempt""conditional""excluded""folder""complete""estimated""refer""understanding""number""drive""April""april""january""february""May""june""july""august""september""october""november""december""2020""2021""printed""complete""2022""carson""torrance""redondo""palos""verdes""rolling""gardena""hills""rancho""exhibit""contact""pulled""lawndale""link""actions""successor""draft""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""manhattan""lomita""hermosa""application""required""attachment""separate""roll""proclamation""legislative""increase""two""requested""conduct""santa""11.""final""presentation""via""presentations""entitled""signal""treasurer""existing""pledge""center""adopting""subsequent""possible""summary""committee""planning""support""12.""councilmember""presented""allegiance""notice""2022.""bill""specific""enter""account""mirada""information""accept""compliance""please""case""resources""make""company""submitted""bodies""oral""board""monthly""person""requests" "schedule" "legal" "chambers" "enacted" "committees" "certain" "pico" "litigation" "south" "rivera" "boards" "upon" "submit" "made" "limited" "located" "findings" "human" "well" "declaring" "future" "alternatively" "hill" "various" "relating" "attachments" "13." "2021-22" "control" "activities" "and/or" "july" "continue" "system" "downey" "payment" "vote" "appointment" "element" "warrants" "none" "measure" "open" "american" "brown" "announcements""assistance""term""change""apn""response""springs""offset""requirements""counsel""claims""revised""map""direction""one-year""amended""quality""appropriate""opportunity""remote""appointments""regulations""transportation""commissions""adding""designated""also""shall""participate""hall""hours""norwalk""14.""accordance""federal""cerritos""event""adopted""rehabilitation""invocation""separately""6:30""payroll""association""plans""2021-2022""name""installation""administrator""demands""gate""residential""jurisdiction""on-call""assembly""provisions""redevelopment""operating""54953""bellflower""civic""vernon""15.""council/successor""specifications""communications""dba""not-to-exceed""recommendations""city" "council" "recommendation" "public" "agenda" "meeting" "2022" "resolution" "approve" "report""staff" "page""items""services""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""manager""agreement""action""minutes""section" "department" "item" "code" "may" "project""authorize""consent""adopt""california""office""contract""regular""comments""agency""2021""amount""mayor""calendar""january" "february" "time" "suggested" "session" "member" "file" "attorney" "approval" "ordinance" "government" "execute" "use" "receive" "beach" "long" "development" "pursuant" "amendment" "general" "April" "program" "state" "address" "community" "year" "plan" "approving" "clerk" "members" "meetings" "authorizing" "closed" "grant" "reading" "inc." "fiscal" "provide" "district" "recommends" "consideration" "related" "municipal" "one" "business" "local" "participation" "consider" "call" "provided" "act" "non-agenda" "lynwood" "emergency" "reports" "tuesday" "los" "period" "works" "street" "review" "discussion" "angeles" "budget" "warrant" "citywide" "iii" "avenue" "order" "hearing" "procedures" "fund" "housing" "documents" "successor" "title" "new" "recommended" "wishing" "approved" "speakers" "register" "amending" "funds" "motion" "necessary" "allotted" "annual" "comment" "teleconference" "instructions" "covid" "matters" "non-" "regarding" "additional" "form" "county" "authority" "request" "including" "proposed" "group" "designee" "p.m." "commission" "considered" "month" "bell" "update" "waive" "commerce" "chapter" "full" "award" "property" "conference" "improvement" "removed" "special" "5:00" "ordinances" "total" "listed""read""exceed""adoption""covid-19""take""llc""boulevard""funding""ceqa""director""within""june""routine""three""following""unless""capital""cudahy""amendments""improvements""subject""attached""prior""zoom""compton""service""361""10.""dated""second""monica""beverly""culver""2022-23""agoura""westlake""village""calabasas""correspondence""west""giugni""3.a""quarker""lovano""hollywood""must""completed""glendale""burbank""setting""intent""2022-2023""levy""yes""pdf""lauren""vasquez""council/housing""briefly""orals""volume""conducted""management""first""discuss")
        tokens5=[]
        for w in box5:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord5:
                    tokens5.append(w)
        grams5 = nltk.ngrams(tokens5, 2)

        fdist5 = nltk.FreqDist(grams5)

        box6=[]
        for x in agendaLAcomm:
            box6.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord6=('pre\\xadqualified''bpw\\xad2022\\xad0647cd''on\\xadcall ''ecommendations adoption''adoption determine''designee said''funding sources''december''accounting requesting''requesting andexecution''andexecution authority''authority expenditure''june 2023''fund 760''760 sewer''maintenance fund''fund dept''dept no.50''no.50 appropriation''appropriation 50wx82''tos''pay annual''annual npdes''fees required''required stateof''stateof period''system modifications' 'modifications cip' 'cip 6163recommending' '6163recommending szd11204' 'szd11204 c\\xad129307' 'bpw\\xad2022\\xad0588cd onbehalf' 'world airports''airport commissioners''inwood drive''drive 13375''13375 bulkhead''contracting corporation''corporation amount''removal 11700''11700 11706''11706 charnock''charnock roadrecommending''roadrecommending categorically''categorically actguidelines''actguidelines willhave''willhave compliance''compliance thecalifornia''reclamation plantelectrical''plantelectrical power''lacity.org 213''find exceptions''exceptions setforth''setforth 15300.2''allthe mayor''mayor approved''approved authorized''relative entitled''property negotiators''negotiators 54956.8''obtained attorney.''conference property''54956.8 instructions''instructions negotiators''negotiators respect''negotiation price''price terms''limit file''construction budget''c.s legacy''second one\\xadyear''15332 class''committee may''real estate''deputy clerk''continues directly''safely person''significant effect''execute amendment''15303 class''may recess''recess 54956.9''54956.9 confer''lowest responsive''construction orders''execute thecontract''communication dated''last day''use meeting''motion reconsider''responsible bidder''attorney dated''pursuant article''closed session''agenda items''court case''five working''shall provide''instruct immediately''within five''substantial evidence''boecd 6contract''6contract acceptance''acceptance donald''donald tillman''land use''california pursuant''superior court''working days''and3 instruct'"neighborhood council""planning commission""administrative officer""area planning""relay service""and2 authorize""board:1. accept""attachments board""accept contract.""contract. w.o""department planning""commission action""authorize president""president two""board comment/correspondence""two members""members board""bureau street""proposed project""board works""categorical exemption""legal counsel""approval ""as\\xadto\\xadform""square feet""street services""act ceqa""city los""angeles""city""statement none ""government code""code section""statement impact""ceqa guidelines""Los Angeles""impact statement""environmental quality""2022""chief executive""nocommunity""letterpublic""submittedreport""yescommunity""2022""august""september""july""october")
        tokens6=[]
        for w in box6:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord6:
                    tokens6.append(w)
        grams6 = nltk.ngrams(tokens6, 2)

        fdist6 = nltk.FreqDist(grams6)

    return render_template('index.html',fdist1s=fdist1,fdist2s=fdist2,fdist3s=fdist3,fdist4s=fdist4,fdist5s=fdist5,fdist6s=fdist6,agendaas=agendaa,agendabs=agendab,agendacs=agendac,agendads=agendad,agendaes=agendae,agendafs=agendaf,agendags=agendag,agendahs=agendah, title="Welcome to my site")


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
        a = date.today()+ relativedelta(weeks=1)
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) #Change month to 3
        d= str(c).replace("-","")
        lMonth=int(d)        
        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'water'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendab = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'cannabis'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendac = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'EV'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendad = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'homeless'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendae = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'healthcare'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendaf = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'criminal'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendag = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'climate'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendah = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'military'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('loggedIn.html',agendaas=agendaa,agendabs=agendab,agendacs=agendac,agendads=agendad,agendaes=agendae,agendafs=agendaf,agendags=agendag,agendahs=agendah, username = username, title = "You are now logged into PolicyEdge. Government at a glance.")
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

@app.route('/southBay', methods=['GET', 'POST'])
def southbay():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) 
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Torrance "," Carson "," Lomita "," Rancho Palos Verdes "," Rolling Hills "," Rolling Hills Estates "," Redondo Beach "," Hermosa Beach "," Manhattan Beach "," El Segundo "," Hawthorne "," Lawndale "," Gardena "]}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('southbay.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring Southbay Search Results")

@app.route('/gateway', methods=['GET', 'POST'])
def gateway():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) 
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[ " Lakewood "," Long Beach "," Signal Hill "," Compton ", " Lynwood ", " South Gate ", " Cudahy ", " Bell ", " Maywood ", " Vernon ", " Bell Gardens ", " Commerce ", " Downey ", " Pico Rivera ", " Santa Fe Springs "," Whittier ", " Santa Fe Springs ", " Norwalk ", " La Mirada ", " Cerritos ", " Hawaiian Gardens ", " Bellflower ", " Paramount "," Artesia " ]}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('gateway.html', agendas=agenda,  title = "PolicyEdge agenda Gateway Cities Search Results")

@app.route('/westside', methods=['GET', 'POST'])
def westside():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2)
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Beverly Hills " , " Culver City " , " Malibu " , " Santa Monica " , " West Hollywood "]}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('westside.html', agendas=agenda,  title = "PolicyEdge agenda Westside area Search Results")

@app.route('/sangabrielCities', methods=['GET', 'POST'])
def sangabriel():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) 
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Alhambra "," Arcadia "," Azusa "," Baldwin Park "," Bradbury "," Covina "," Diamond Bar "," Duarte "," El Monte "," Glendora "," City of Industry "," Irwindale "," La Canada Flintridge "," La Puente "," La Verne "," Monrovia "," Montebello "," Monterey Park "," Pasadena "," Pomona "," Rosemead "," San Dimas "," San Gabriel "," San Marino "," Sierra Madre "," South El Monte ", " S Pasadena ", " Temple City "," Walnut "," West Covina "]}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('sangabrielCities.html', agendas=agenda,  title = "PolicyEdge agenda San Gabriel Area Search Results")

@app.route('/sanfernandoCities', methods=['GET', 'POST'])
def sanfernando():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) 
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {"City":{'$in':[" Agoura Hills " , " Burbank " , " Calabasas " , " Glendale " , " Hidden Hills " , " San Fernando " , " Westlake Village "]}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('sanfernandoCities.html', agendas=agenda,  title = "PolicyEdge agenda tracking monitoring San Fernando Search Results")

@app.route('/cannabis', methods=['GET', 'POST'])
def cannabis():
    if request.method == 'GET':
        a = date.today()
        b= str(a).replace("-","")
        today=int(b)
        c = date.today() + relativedelta(weeks=-2) 
        d= str(c).replace("-","")
        lMonth=int(d)
        agenda = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'cannabis'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        return render_template('cannabis.html', agendas=agenda,  title = "Search Results")

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

if __name__ == '__main__':
    app.run(debug = True)













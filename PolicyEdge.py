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

        e = date.today()+ relativedelta(weeks=2)
        f= str(e).replace("-","")
        weekAhead=int(f)
        g = date.today() + relativedelta(weeks=-3)
        h= str(g).replace("-","")
        timeBefore=int(h)

        agendaa = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'water'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendab = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'cannabis'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendac = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'EV'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendad = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'homeless'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendae = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'rfp'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendaf = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'healthcare'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendag = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'climate'}}, { 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendah = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'military'}},{ 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendah = mongo.db.Agenda.find({'$and':[ {'$text': { "$search": 'military'}},{ 'Date':{'$lte':today, '$gte':lMonth}}]}).sort('Date').sort('City')
        agendaLACounty = mongo.db.Agenda.find({'$and':[ {"County":" LA County "}, { 'Date':{'$lte':weekAhead, '$gte':timeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaSanBerCounty = mongo.db.Agenda.find({'$and':[ {"County":" San Bernadino County "}, { 'Date':{'$lte':weekAhead, '$gte':timeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaRiverCounty = mongo.db.Agenda.find({'$and':[ {"County":" Riverside County "}, { 'Date':{'$lte':weekAhead, '$gte':timeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaSanDieCounty = mongo.db.Agenda.find({'$and':[ {"County":" San Diego County "}, { 'Date':{'$lte':weekAhead, '$gte':timeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaOrangeCounty = mongo.db.Agenda.find({'$and':[ {"County":" Orange County "}, { 'Date':{'$lte':weekAhead, '$gte':timeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})
        agendaLAcomm = mongo.db.Agenda.find({'$and':[ {"MeetingType":{'$not': {'$regex': " City Council ", '$options': 'i' }}}, {"City": " Los Angeles "},{ 'Date':{'$lte':weekAhead, '$gte':timeBefore}}]},{'_id': 0, 'County':0, 'City':0, 'Date':0, 'Num':0, 'MeetingType':0, 'ItemType':0})

        box1=[]
        for x in agendaLACounty:
            box1.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord1=('conditions findings.applicant''2022.present setting''articles xiiic''xiiic xiiid''xiiid constitution''collected annually''annually starting''starting 2022-23''2022-23 dedicated''dedicated system.community''purposes 100/56''pdf " cc"''chair personnel''resolve environmentalmanagement''environmentalmanagement determined''supplemental tax-exempt''full ordinances''ability members''education neighborhoods''including errata''district.recommendations deny''deny protest''protest confirm''confirm assessments.present''assessments.present levying''levying assessments''assessments ordering''ordering 53753''plans specifications''common sense''web link''adoption intention''due covid-19''al. superior''independent judgment''650 676''656 medical''15308 class''site review''hearings held''subdivision security''security documents''documents bond''subdivider paid''processing 19.02''19.02 additional''additional needed.community''western avenue''avenue cdbg''roll call''september 2022.''new received''task force''adding chapter''incorporating amending''view onbase''agoura hills''cubic yards''silver lake''appellant representative''2021-22.fiscal 10-14-22''assessment district\\xad''22- repealing''andexecution authority''760 sewer''operations dept''dept no.50''no.50 appropriation''labor negotiator''metropolitan transportation''transportation authority''county metropolitan''proclamation declaring''measures promote''december december''lacity.org 213''citycouncil carson''human resources''proposed amendment''approving amendment''whole record''final l.a.''written comments''amendments thereto''teleconference meetings''mitigation monitoring''reports recommendations''list historic-cultural''recess 54956.9''recommended find''related findings''associates inc.''considered routine''safely person''within jurisdiction''make technical''corrections clarifications''president two''united states''minutes special''three years''continues directly''information technology''technical corrections''oaks initiative''march 2020''assembly bill''reap lahd''accounting requesting''south vicente''west neighborhood''negotiation price''motion reconsider''rent escrow''escrow account''account program''program reap''lahd accompanying''effectuate intent''police commissioners''form approved''local officials''reap.fiscal lahd''january 2023''june 2023''21city tuesday''2022city 411''411 ocean''ocean boulevardcivic''boulevardcivic chambers''chambers 5:00''palos verdes''sections 6.95-6.127''communication adopted''separate discussion''audits animal''substantial evidence''multifamily conduit''conduit revenue''exempt guidelines''existing litigation''expenditure none.recommendation''parks recreation''zone change''pico rivera''economic development''take place''successor agency''advisory board''extend term''submittedtime limit''thecity downey''floor area''development director''provide direction''negative declaration''categorical exemption''budget finance''notice completion''memorandum understanding''regulations title''regular minute''california quality''agenda items''property located''land use''warrant register''recommendation staff''award contract''removing property''santa monica''parcel map''waived consideration''purchase order''proposition 218''adopting reference''designee execute''committee waived''set forth''grant funds''second consideration''district accordance''consideration matter''court case''real property''improvement project''staff reportattachment''general fund''receive file''planning commission''subject approval''closed session''legal counsel''professional services''chief legislative''consent calendar''services agreement''pursuant ceqa''approval mayor''conference legal''first reading''amount exceed''legislative completed''ceqa pursuant''housing department''long beach''last day''attached file''reading ordinance''city council''impact statement''los angeles''statement none''city manager''council action''october 2022''november 2022''report dated''none submitted''administrative officer''municipal code''adopt resolution''city clerk''action approve''code section''fiscal year''authorize city''public works''government code''city administrative''street lighting''recommends city''public hearing''council meeting''impact statement''statement yescommunity''yescommunity impact''statement submittedreport''report.community impact''bureau lighting''financial analysis''analysis report.community''analyst financial''policies statement''neither administrative''square feet''administrative analyst''building standards''relative maintenance ''statement nocommunity ''nocommunity impact ''bureau sanitation ''water power ''assessor i.d''statement yesfinancial ''yesfinancial policies ''statement cao ''environmental article')
        tokens1=[]
        for w in box1:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord1:
                    tokens1.append(w)
        grams1 = nltk.ngrams(tokens1, 2)

        fdist1 = nltk.FreqDist(grams1)

        box2=[]
        for x in agendaSanBerCounty:
            box2.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord2=()
        tokens2=[]
        for w in box2:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord2:
                    tokens2.append(w)
        grams2 = nltk.ngrams(tokens2, 2)

        fdist2 = nltk.FreqDist(grams2)

        box3=[]
        for x in agendaRiverCounty:
            box3.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord3=('designee necessarydocuments.click''legislative bodies''text entirety''amending section''perris state''hemetand southern''amanda wells''wells director/city''director/city treasurerrecommended''management analystrecommended''hall avenue''improvement projects''real property''waring drive''conflict interest''sole discretion.2''pursuant §54956.9''§54956.9 and/or''wards 5-minute''propositions regarding''mustang way''open hearing''calling election''entitled ofthe''southeast corner''extend term''28214-9 exhibit''exhibit haul''32129 exhibit''fisher street''street lennar''2005-1 safety''rancho mcholland''mcholland llc''lake elsinore''investment september''conference legal''closed session''desertcity negotiator''negotiator todd''cejanegotiating parties''negotiation price''2025 two''proposed number''items listed''approving amendment''successor agency''notice completion''coachella valley''necessary documents.click''next order''approve purchase''establishment appropriations''take testimony''listed agenda''county riverside''approve amendment''approve contract''supplemental appropriation''appropriations limit''tax within''palm springs''click view''second reading''fiscal year''regular meeting''tract map''community development''development block''2022-02 saddle''saddle point''block grant''amount exceed''reading ordinance''documents related''authorizing finance''classification compensation''levy special''waive reading''read title''consent calendar''final tract''city council''city manager''council city''resolution city''city hemet''hemet california''manager execute''adopt resolution''services agreement''interim city''recommends city''authorize city''staff recommends''receive file''action staff''public works''recommended city''pdfrecommendation respectfully''respectfully recommended''october 2022''government code''authorize interim''facilities district''consideration resolution''warrant report')
        tokens3=[]
        for w in box3:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord3:
                    tokens3.append(w)
        grams3 = nltk.ngrams(tokens3, 2)

        fdist3 = nltk.FreqDist(grams3)

        box4=[]
        for x in agendaSanDieCounty:
            box4.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord4=('block grant''meets minimum''requirements sbmc''found conditioned''council:1. hearing.2''hearing.2 find''find tosection''and3 makes''makes requisite''requisite findings''findings approves''track phase''approving tentative''tentative parcel''waiver full''conference legal''2022- approving''dispatch authority''certain provisions''office.solana page''thefinal office''efficiency committeemeeting''cate-yea elo-rivera-yea''miguel merrell''paid liability''liability fund.council''exemption two''servicesenvironmental 15378''15378 stateguidelines''accept quarterly''quarterly financial''requests excused''columbus statue''528 529''adopted budget''local agency''jpa primary-harless''commissiono commissiono''boards commissions''2nd pipelines''lacava-yea campbell-yea''actions.vote 3-0''3-0 lacava-yea''planning decision''independent budget''budget analyst''budget government''hilda mendoza''considered afternoon''afternoon session''session scheduledto''scheduledto begin''begin 2:00''2:00 p.m.total''proclaiming november''program coordinator''chula vista''next order''building fire''unified school''98-02 lighting''categorically exempt''approve minutes''.attachments election''conduct open''open disclosures''disclosures receive''receive testimony''testimony close''highway 101''reference mr.''consent calendar''ordinances resolutions''reason survive''subject n/adevelopment''n/adevelopment services''voted councilmember''von wilpert-yea''associated action.council''apportionment special''waive text''league cities''warrant register''following introduced''moreno-not present''vice chair''chamber commerce''parks recreation''provide direction''joint powers''citizen commission''appropriating funds''entitled national''not-to-exceed amount''amendment agreement''north county''general plan''amending title''regular agenda''montgomery steppe-yea''court case''153''guidelinessection''otay ranch''ranch village''note file''attached certifying''annexing theproperties''theproperties listed''listed community''annexation boundary''boundary map''property maps''method apportionmen''council approval''state guidelines''introduction ordinance''2022.action motion''recommend council''notice activity''activity project''project defined''defined''78''guidelines therefore''approval staff''ceqa guidelines''cfd 98-01''recommendation council1''staff recommends''submittals.the final''final clerk''solana beach''ordinance authorizing''adopting amended''specific geographic''geographic locationdepartment''15060 required.recommended''board directors''san diego''cost proposed''proposed action''action source''public hearing''attorney contact''quality act''district citywide.proposed''citywide.proposed actions''municipal code''adopt resolution''environmental quality''fiscal year''october 2022''san marcos''second reading''action adopt''pursuant section''environmental review''2022 california''thecalifornia environmental''cut time''time meeting''meeting new''actions item''estimated funding''affected citywide.propose''supplemental docs''posted reports''reports supplemental''docs contain''contain records''records prior''prior start''start processing''official record''record containing''containing handouts''handouts powerpoints''powerpoints etc''etc obtained''obtained records''records request''conflict interest''click posted''taken heard''mayor veto.committee''veto.committee taken''votes required''required charter')
        tokens4=[]
        for w in box4:
            if w not in stop_words and len(w)>2:
                if w not in SingleWord4:
                    tokens4.append(w)
        grams4 = nltk.ngrams(tokens4, 2)

        fdist4 = nltk.FreqDist(grams4)

        box5=[]
        for x in agendaOrangeCounty:
            box5.extend(word_tokenize(str(x).lower().replace('\\n','').replace('\\xa0','').replace('\\t','').replace('description','')))

        stop_words=set(stopwords.words("english") + list(string.punctuation))
        SingleWord5=('legislative bodies''commissions committees''initiative uasi''resolutions approving''wire transfer''warrant registers''santa margarita''thecalifornia standards''regulations including''model codes''director designee''certificate recognition''lake forest''committee reports''transportation authority''advisory committee''titles appear''services agreements''related documents''potential cases''second adoption''works department''capital improvement''establishing classification''classification andcompensation''andcompensation policy''based 2021''chapman avenue''54956.9 number''wishing address''yorba linda''bella terra''september 2022recommended''project 21/22''dana point''treasurer monthly''take necessary''cityof anaheim''paragraph subdivision''closed session''name case''property located''final payment''certain amendments''laguna hills''planning commission''counsel existing''pay period''successor agency''exempt change''counsel anticipated''management association''san clemente''agenda report''community development''adopting reference''approval minutes''amending chapter''effective pay''period includes''minutes ofoctober''mission viejo''items removed''amount exceed''consent calendar''view item''item etai''entitled ordinance''staff recommends''quality ceqa''inc. amount''litigation pursuant''notice completion''check register''fiscal year''full ordinances''ceqa pursuant''provide direction''huntington beach''pursuant ceqa''mayor execute''execute agreement''introduce ordinance''city council''city manager''adopt resolution''council city''october 2022''code 2022''resolution city''authorize city''city clerk''receive file''november 2022''regular meeting''government code''municipal code''action approve''2022 california''council approve''2022 edition''conference legal''council member''city california''public hearing''orange county''waive reading''action receive''share tweet''physical environment''result physical''memorandum ofunderstanding''sections 15060''15060 15060''buena park''ofirvine memorandum''ofunderstanding irvine''determine environmental''environmental sections''15060 guidelinesbecause''guidelinesbecause result''environment directly''directly orindirectly''buildings construction''additions deletions''together additions''2025 confirm''performance evaluation''ratify accompanying')
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
        SingleWord6=('conversion 2015\\xad2016''2015\\xad2016 lightingprojectrecommending''supplemental transmittalattachment''silver lake''regulations would''north westwood''transportation committees''melrose avenue''"o farrell" krekorian''calls trs''trs available''interest● requests●''continued friday''concur davisapproving''ocb amendthe''amendthe current''nuys series''series multiplehigh''recommended organizationapproval''covid-19 emergency''three years''local officials''please passcode''commissionaction matter.b''matter.b thecommission''waiver allow''penalty 8 360''holding via''via teleconferencemotion''teleconferencemotion 54953''54953 covid-19''accordance 361''zoning administrator''whole record''669 900-9128''recommendation transmit''motions make''previous consistently''consistently rule''rule 9.3''9.3 provided''provided retains''merits voted''voted majority''merits original''determination which:1.''march 2020''negative declaration''task force''fromthe requirements''communitybenefit foundation''mladen buntich''relates listed''listed beingconsidered''beingconsidered orcommission''orcommission copy''chair discretion''discretion councils''taken time''general commentthe''commentthe opportunity''opportunity open''open meetings''meetings address''cumulative total''total thirty''thirty minutes''minutes interest''commission.members wish''wish participate''participate offer''either access''access link''yesfinancial policies''resolve environmentalmanagement''operations 50w2wp''memorandum understanding''requiredproject site''conditions findings.applicant''cubic yards''subcontractor substitution''related findings''south robertson''resolution ____________''environmentalmanagement administratively''staff reportattachment''policies referred''advance calendar●''position statements''statements itemspresentations''itemspresentations representatives''representatives resolution''resolution orcommunity''orcommunity filed''change justice''justice river''economic development''draft ordinance''existing litigation''sherman oaks''appellant representative''lighting assessment''assessment district\\xad''district\\xad hearing''hearing november''fiscal 2021-22.fiscal''2021-22.fiscal''14-22''subject matter''matter jurisdiction''municipal lamc''development standards''director sanitation''grant program''pre\\xadqualified''bpw\\xad2022\\xad0647cd''on\\xadcall ''ecommendations adoption''adoption determine''designee said''funding sources''december''accounting requesting''requesting andexecution''andexecution authority''authority expenditure''june 2023''fund 760''760 sewer''maintenance fund''fund dept''dept no.50''no.50 appropriation''appropriation 50wx82''tos''pay annual''annual npdes''fees required''required stateof''stateof period''system modifications' 'modifications cip' 'cip 6163recommending' '6163recommending szd11204' 'szd11204 c\\xad129307' 'bpw\\xad2022\\xad0588cd onbehalf' 'world airports''airport commissioners''inwood drive''drive 13375''13375 bulkhead''contracting corporation''corporation amount''removal 11700''11700 11706''11706 charnock''charnock roadrecommending''roadrecommending categorically''categorically actguidelines''actguidelines willhave''willhave compliance''compliance thecalifornia''reclamation plantelectrical''plantelectrical power''lacity.org 213''find exceptions''exceptions setforth''setforth 15300.2''allthe mayor''mayor approved''approved authorized''relative entitled''property negotiators''negotiators 54956.8''obtained attorney.''conference property''54956.8 instructions''instructions negotiators''negotiators respect''negotiation price''price terms''limit file''construction budget''c.s legacy''second one\\xadyear''15332 class''committee may''real estate''deputy clerk''continues directly''safely person''significant effect''execute amendment''15303 class''may recess''recess 54956.9''54956.9 confer''lowest responsive''construction orders''execute thecontract''communication dated''last day''use meeting''motion reconsider''responsible bidder''attorney dated''pursuant article''closed session''agenda items''court case''five working''shall provide''instruct immediately''within five''substantial evidence''boecd 6contract''6contract acceptance''acceptance donald''donald tillman''land use''california pursuant''superior court''working days''and3 instruct'"neighborhood council""planning commission""administrative officer""area planning""relay service""and2 authorize""board:1. accept""attachments board""accept contract.""contract. w.o""department planning""commission action""authorize president""president two""board comment/correspondence""two members""members board""bureau street""proposed project""board works""categorical exemption""legal counsel""approval ""as\\xadto\\xadform""square feet""street services""act ceqa""city los""angeles""city""statement none ""government code""code section""statement impact""ceqa guidelines""Los Angeles""impact statement""environmental quality""2022""chief executive""nocommunity""letterpublic""submittedreport""yescommunity""2022""august""september""july""october")
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













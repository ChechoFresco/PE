from flask import Flask, render_template, request
from wtforms import StringField, SelectField, Form
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length


# Common choice sets
CITY_CHOICES = {
"LA": [
        ('', ''), ('Agoura Hills', 'Agoura Hills'), ('Alhambra', 'Alhambra'),
        ('Arcadia', 'Arcadia'), ('Artesia', 'Artesia'), ('Azusa', 'Azusa'),('Baldwin Park','Baldwin Park'), ('Bell','Bell'), ('Bell Gardens','Bell Gardens'), ('Bellflower','Bellflower'), ('Beverly Hills','Beverly Hills'),
        ('Bradbury','Bradbury'), ('Burbank','Burbank'), ('Calabasas','Calabasas'), ('Carson','Carson'), ('Cerritos','Cerritos'), ('City of Industry','City of Industry'), ('Claremont','Claremont'),('Commerce','Commerce'), ('Compton','Compton'),
        ('Covina','Covina'), ('Cudahy','Cudahy'), ('Culver City','Culver City'), ('Diamond Bar','Diamond Bar'), ('Downey','Downey'), ('Duarte','Duarte'), ('El Monte','El Monte'),
        ('El Segundo','El Segundo'), ('Gardena','Gardena'), ('Glendale','Glendale'), ('Glendora','Glendora'), ('Hawaiian Gardens','Hawaiian Gardens'), ('Hawthorne','Hawthorne'), ('Hermosa Beach','Hermosa Beach'), ('Hidden Hills','Hidden Hills'), ('Huntington Park','Huntington Park'), ('Inglewood','Inglewood'),
        ('Irwindale','Irwindale'), ('La Canada Flintridge','La Canada Flintridge'), ('La Habra Heights','La Habra Heights'), ('La Mirada','La Mirada'), ('La Puente','La Puente'), ('La Verne','La Verne'),
        ('Lakewood','Lakewood'), ('Lancaster','Lancaster'), ('Lawndale','Lawndale'), ('Lomita','Lomita'), ('Long Beach','Long Beach'), ('Los Angeles','Los Angeles'), ('Lynwood','Lynwood'), ('Malibu','Malibu'),('Manhattan Beach','Manhattan Beach'), ('Maywood','Maywood'), ('Monrovia','Monrovia'),
        ('Montebello','Montebello'), ('Monterey Park','Monterey Park'), ('Norwalk','Norwalk'), ('Palmdale','Palmdale'), ('Palos Verdes Estates',''), ('Paramount','Paramount'), ('Pasadena','Pasadena'), ('Pico Rivera','Pico Rivera'),
        ('Pomona','Pomona'), ('Rancho Palos Verdes','Rancho Palos Verdes'), ('Redondo Beach','Redondo Beach'), ('Rolling Hills','Rolling Hills'), ('Rolling Hills Estate','Rolling Hills Estate'), ('Rosemead','Rosemead'), ('San Dimas','San Dimas'),
        ('San Fernando','San Fernando'), ('San Gabriel','an Gabriel'), ('San Marino','San Marino'), ('Santa Clarita','Santa Clarita'), ('Santa Fe Springs','Santa Fe Springs'), ('Santa Monica','Santa Monica'),
        ('Sierra Madre','Sierra Madre'), ('Signal Hill','Signal Hill'), ('South El Monte','South El Monte'), ('South Gate','South Gate'), ('South Pasadena','South Pasadena'), ('Temple City','Temple City'), ('Torrance','Torrance'),
        ('Vernon','Vernon'), ('Walnut','Walnut'), ('West Covina','West Covina'), ('West Hollywood','West Hollywoo'), ('Westlake Village','Westlake Village'), ('Whittier','Whittier')
],
"OC": [
        ('', ''), ('Aliso Viejo', 'Aliso Viejo'), ('Anaheim', 'Anaheim'), ('Brea', 'Brea'), ('Buena Park', 'Buena Park'), ('Costa Mesa', 'Costa Mesa'), ('Cypress','Cypress'), ('Dana Point','Dana Point'),
        ('Fountain Valley','Fountain Valley'), ('Fullerton','Fullerton'), ('Huntington Beach','Huntington Beach'), ('Irvine','Irvine'), ('La Habra','La Habra'), ('La Palma','La Palma'),
        ('Laguna Beach','Laguna Beach'), ('Laguna Hills','Laguna Hills'), ('Laguna Niguel','Laguna Niguel'), ('Laguna Woods','Laguna Woods'), ('Lake Forest','Lake Forest'), ('Los Alamitos','Los Alamitos'), ('Mission Viejo','Mission Viejo'), ('Newport Beach','Newport Beach'), ('Orange','Orange'), ('Placentia','Placentia'),
        ('Rancho Santa Margarita','Rancho Santa Margarita'), ('San Clemente','San Clemente'), ('San Juan Capistrano','San Juan Capistrano'), ('Santa Ana','Santa Ana'), ('Seal Beach','Seal Beach'), ('Stanton','Stanton'), ('Tustin','Tustin'), ('Villa Park','Villa Park'), ('Westminister','Westminister'), ('Yorba Linda','Yorba Linda')
],
"RS": [
        ('', ''), ('Banning', 'Banning'), ('Beaumont', 'Beaumont'), ('Blythe', 'Blythe'), ('Calimesa', 'Calimesa'), ('Canyon Lake', 'Canyon Lake'),
        ('Cathedral City','Cathedral City'), ('Coachella','Coachella'), ('Corona','Corona'), ('Desert Hot Springs','Desert Hot Springs'), ('Eastvale','Eastvale'),
        ('Hemet','Hemet'), ('Indian Wells','Indian Wells'), ('Indio','Indio'), ('Jurupa Valley','Jurupa Valley'), ('Lake Elsinore','Lake Elsinore'),
        ('La Quinta','La Quinta'), ('Menifee','Menifee'), ('Moreno Valley','Moreno Valley'), ('Murrieta','Murrieta'), ('Norco','Norco'), ('Palm Desert','Palm Desert'), ('Palm Springs','Palm Springs'), ('Perris','Perris'),
        ('Rancho Mirage','Rancho Mirage'), ('Riverside','Riverside'), ('San Jacinto','San Jacinto'), ('Temecula','Temecula'), ('Wildomar','Wildomar')
],
"SB": [
        ('', ''), ('Adelanto', 'Adelanto'), ('Apple Valley', 'Apple Valley'), ('Barstow', 'Barstow'), ('Big Bear Lake', 'Big Bear Lake'), ('Chino', 'Chino'), ('Chino Hills','Chino Hills'), ('Colton','Colton'), ('Fontana','Fontana'), ('Grand Terrace','Grand Terrace'),
        ('Hesperia','Hesperia'), ('Highland','Highland'), ('Loma Linda','Loma Linda'), ('Montclair','Montclair'), ('Needles','Needles'),
        ('Ontario','Ontario'), ('Rancho Cucamonga','Rancho Cucamonga'), ('Redlands','Redlands'), ('Rialto','Rialto'), ('San Bernandino','San Bernandino'),
        ('Twnentynine Palms','Twnentynine Palms'), ('Upland','Upland'), ('Victorville','Victorville'), ('Yucaipa','Yucaipa'),('Yucca Valley','Yucca Valley')
],
"SD": [
        ('', ''), ('Carlsbad', 'Carlsbad'), ('Chula Vista', 'Chula Vista'), ('Coronado', 'Coronado'), ('Del Mar', 'Del Mar'), ('El Cajon', 'El Cajon'),
        ('Encinitas','Encinitas'),('Escondido','Escondido'),('Imprial Beach','Imprial Beach'),('La Mesa','La Mesa'),('Lemon Grove','Lemon Grove'),
        ('National City','National City'),('Oceanside','Oceanside'),('Poway','Poway'), ('San Diego','San Diego'),('San Marcos','San Marcos'),('Santee','Santee'),('Solana Beach','Solana Beach'),('Vista','Vista')],
"LACM": [
        ('', ''), ('Arts, Parks, Health, Education and Neighborhoods Committee','Arts, Parks, Health, Education and Neighborhoods Committee'),('Board of Airport Commissioners', 'Board of Airport Commissioners'),
        ('Board of Fire Commissioners','Board of Fire Commissioners'),('Board of Public Works','Board of Public Works',),
        ('Board of Rec and Park Commission','Board of Rec and Park Commission'),('Board of Transportation Commissioners','Board of Transportation Commissioners'),('Budget & Finance','Budget & Finance'),('Cannabis Regulation Commission','Cannabis Regulation Commission'),
        ('City Planning Commission','City Planning Commission'),('Economic Development and Jobs Committee','Economic Development and Jobs Committee'),('Energy Climate','Energy Climate'),
        ('Homelessness & Poverty Committee','Homelessness & Poverty Committee'),('Immigrant Affairs , Civil Rights, and Equity Committee','Immigrant Affairs , Civil Rights, and Equity Committee'),
        ('Information Technology & General Service Committee','Information Technology & General Service Committee'),('LA City Health Commission','LA City Health Commission'),('LA County Board','LA County Board'),
        ('LA Police Commission','LA Police Commission'),('LADWP Board','LADWP Board'),('Personnel, Audits, and Animal Welfare Committee','Personnel, Audits, and Animal Welfare Committee'),('PLUM','PLUM'),('Port of LA','Port of LA'),('Public Safety Committee','Public Safety Committee'),
        ('Public Works','Public Works'),('Rules Elections','Rules Elections'),('Trade, Travel, and Tourism Committee','Trade, Travel, and Tourism Committee'),('Transportation Committee','Transportation Committee')
],
"LBCM": [
        ('', ''), ('Airport', 'Airport'),('Economic Development and Finance Committee', 'Economic Development and Finance Committee'),('Long Beach Transit','Long Beach Transit'),
        ('Parks and Recreation Commission','Parks and Recreation Commission'),('Planning Commission','Planning Commission'),('Port, Transportation and Infrastructure Committee','Port, Transportation and Infrastructure Committee'),
        ('Public Safety Committee','Public Safety Committee'),('Technology and Innovation Commission','Technology and Innovation Commission'),('Water Commission','Water Commission')
        ],
}

COMMITTEE_CHOICES = {
"LACM": [
        ('', ''), ('Arts, Parks, Health, Education and Neighborhoods Committee','Arts, Parks, Health, Education and Neighborhoods Committee'),('Board of Airport Commissioners', 'Board of Airport Commissioners'),
        ('Board of Fire Commissioners','Board of Fire Commissioners'),('Board of Public Works','Board of Public Works',),
        ('Board of Rec and Park Commission','Board of Rec and Park Commission'),('Board of Transportation Commissioners','Board of Transportation Commissioners'),('Budget & Finance','Budget & Finance'),('Cannabis Regulation Commission','Cannabis Regulation Commission'),
        ('City Planning Commission','City Planning Commission'),('Economic Development and Jobs Committee','Economic Development and Jobs Committee'),('Energy Climate','Energy Climate'),
        ('Homelessness & Poverty Committee','Homelessness & Poverty Committee'),('Immigrant Affairs , Civil Rights, and Equity Committee','Immigrant Affairs , Civil Rights, and Equity Committee'),
        ('Information Technology & General Service Committee','Information Technology & General Service Committee'),('LA City Health Commission','LA City Health Commission'),('LA County Board','LA County Board'),
        ('LA Police Commission','LA Police Commission'),('LADWP Board','LADWP Board'),('Personnel, Audits, and Animal Welfare Committee','Personnel, Audits, and Animal Welfare Committee'),('PLUM','PLUM'),('Port of LA','Port of LA'),('Public Safety Committee','Public Safety Committee'),
        ('Public Works','Public Works'),('Rules Elections','Rules Elections'),('Trade, Travel, and Tourism Committee','Trade, Travel, and Tourism Committee'),('Transportation Committee','Transportation Committee')
],
"LBCM": [
        ('', ''), ('Airport', 'Airport'),('Economic Development and Finance Committee', 'Economic Development and Finance Committee'),('Long Beach Transit','Long Beach Transit'),
        ('Parks and Recreation Commission','Parks and Recreation Commission'),('Planning Commission','Planning Commission'),('Port, Transportation and Infrastructure Committee','Port, Transportation and Infrastructure Committee'),
        ('Public Safety Committee','Public Safety Committee'),('Technology and Innovation Commission','Technology and Innovation Commission'),('Water Commission','Water Commission')
        ],
}

SEARCH_CRITERIA_CHOICES = [
        ('Issue', 'Issue'), ('LA County', 'LA County'),
        ('LA Committees', 'LA Committees'), ('Orange County', 'Orange County'),
        ('Long Beach Committees', 'Long Beach Committees'), ('Riverside County', 'Riverside County'),
        ('San Diego County', 'San Diego County'), ('San Bernardino County', 'San Bernardino County')
        ]


class searchForm2(Form):
        select = SelectField('Criteria:', choices=SEARCH_CRITERIA_CHOICES)
        selectLA = SelectField('Cities:', choices=CITY_CHOICES["LA"])
        selectOC = SelectField('Cities:', choices=CITY_CHOICES["OC"])
        selectSB = SelectField('Cities:', choices=CITY_CHOICES["SB"])
        selectRS = SelectField('Cities:', choices=CITY_CHOICES["RS"])
        selectSD = SelectField('Cities:', choices=CITY_CHOICES["SD"])
        selectLACM = SelectField('Cities:', choices=CITY_CHOICES["LACM"])
        selectLBCM = SelectField('Cities:', choices=CITY_CHOICES["LBCM"])
        primary_search = StringField('Keyword:', validators=[Length(min=1, max=25), DataRequired()])
        startdate_field = DateField('Start Date:', format='%Y%m%d')
        enddate_field = DateField('End Date:', format='%Y%m%d')

class searchForm(Form):
        select = SelectField('Criteria:', choices=SEARCH_CRITERIA_CHOICES)
        selectLA = SelectField('Cities:', choices=CITY_CHOICES["LA"])
        selectOC = SelectField('Cities:', choices=CITY_CHOICES["OC"])
        selectSB = SelectField('Cities:', choices=CITY_CHOICES["SB"])
        selectRS = SelectField('Cities:', choices=CITY_CHOICES["RS"])
        selectSD = SelectField('Cities:', choices=CITY_CHOICES["SD"])
        selectLACM = SelectField('Committees:', choices=COMMITTEE_CHOICES["LACM"])
        selectLBCM = SelectField('Committees:', choices=COMMITTEE_CHOICES["LBCM"])
        primary_search = StringField('Keyword:', validators=[Length(min=1, max=25), DataRequired()])
        startdate_field = DateField('Start Date:', format='%Y%m%d')
        enddate_field = DateField('End Date:', format='%Y%m%d')


class monitorListform(Form):
        monitor_search = StringField('Issue', validators=[Length(min=1, max=25), DataRequired()])
        city_search = StringField('City:')
        committee_search = StringField('Committee:')
        county_search = StringField('County:')


class monitorListform2(Form):
        select = SelectField('Criteria:', choices=SEARCH_CRITERIA_CHOICES)
        selectLA = SelectField('Cities:', choices=CITY_CHOICES["LA"])
        selectOC = SelectField('Cities:', choices=CITY_CHOICES["OC"])
        selectSB = SelectField('Cities:', choices=CITY_CHOICES["SB"])
        selectRS = SelectField('Cities:', choices=CITY_CHOICES["RS"])
        selectSD = SelectField('Cities:', choices=CITY_CHOICES["SD"])
        selectLACM = SelectField('Committees:', choices=COMMITTEE_CHOICES["LACM"])
        selectLBCM = SelectField('Committees:', choices=COMMITTEE_CHOICES["LBCM"])

class chartForm(Form):
        chartSearch = StringField('',render_kw={"placeholder": "Explore Other Issues?"}, validators=[Length(min=1, max=25),DataRequired()])


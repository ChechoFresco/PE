from wtforms import StringField, SelectField, Form
from wtforms.fields.html5 import DateField, TimeField
from wtforms.validators import ValidationError, DataRequired, Length

class searchForm(Form):
        choices = [('LA County', 'LA County'),('Issue', 'Issue'), ('LA Committees', 'LA Committees'), ('Orange County', 'Orange County'), ('Long Beach Committees', 'Long Beach Committees'), ('Riverside County', 'Riverside County'), ('San Diego County', 'San Diego County'), ('San Bernandino County', 'San Bernandino County')]
        select = SelectField('Criteria:', choices=choices)
        primary_search = StringField('City:')
        secondary_search = StringField('Issue:')
        startdate_field =  DateField('Start Date:', format='%Y%m%d')
        enddate_field = DateField('End Date:', format='%Y%m%d')

class monitorListform(Form):
        monitor_search = StringField('Issue', validators=[Length(min=1, max=25),DataRequired()])
        city_search = StringField('City:')
        committee_search= StringField('Committee:')
        county_search= StringField('County:')

from wtforms import StringField, SelectField, Form
from wtforms.fields.html5 import DateField
from wtforms.validators import ValidationError, DataRequired, Length

class searchForm(Form):
        choices = [('City', 'City'),('Description', 'Description')]
        select = SelectField('Criteria:', choices=choices)
        primary_search = StringField('Search for keyword:', validators=[DataRequired()])
        startdate_field =  DateField('Start Date', format='%Y%m%d')
        enddate_field = DateField('End Date', format='%Y%m%d')

class monitorListform(Form):
        monitor_search = StringField('Add keywords to list:', validators=[Length(min=1, max=25),DataRequired()])

class notificationForm(Form):
        notification_search = StringField('What would you like notifications for?:', validators=[Length(min=1, max=25),DataRequired()])

class secondnotificationForm(Form):
        secondnotificationsearch = StringField('What would you like notifications for?:', validators=[Length(min=1, max=25),DataRequired()])

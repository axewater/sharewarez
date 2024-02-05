# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, SubmitField, PasswordField, TextAreaField, RadioField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Regexp, URL,Email
from wtforms.widgets import TextInput

class WhitelistForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Add to Whitelist')

class EditProfileForm(FlaskForm):
    avatar = FileField('Profile Avatar', validators=[
        FileAllowed(['jpg', 'png'], 'Images only!')
    ])
    
class ScanFolderForm(FlaskForm):
    folder_path = StringField('Folder Path', validators=[DataRequired()])
    scan = SubmitField('Scan')
    cancel = SubmitField('Cancel')


class UserDetailForm(FlaskForm):
    submit = SubmitField('Save')
    cancel = SubmitField('Cancel')
    about = TextAreaField('About')


class UserPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Save')
    cancel = SubmitField('Cancel')


class NewsletterForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    recipients = StringField('Recipients')
    send = SubmitField('Send')

class EditUserForm(FlaskForm):

    name = SelectField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = StringField('Role', validators=[DataRequired()])
    state = RadioField('State', choices=[('1', 'Active'), ('0', 'Inactive')])
    avatarpath = StringField('Avatar Path', validators=[DataRequired()])
    submit = SubmitField('Save')
    
    
class UserManagementForm(FlaskForm):
    user_id = SelectField('User ID', coerce=int)
    name = StringField('Name', validators=[Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    role = StringField('Role', validators=[Length(max=64)])
    state = BooleanField('Account Enabled')
    search = StringField('Search Users')
    submit = SubmitField('Submit')
    delete = SubmitField('Delete User')
    
class IGDBApiForm(FlaskForm):
    endpoint = SelectField('Select API Endpoint', choices=[
        ('https://api.igdb.com/v4/covers', 'Covers'),
        ('https://api.igdb.com/v4/games', 'Games'),
        ('https://api.igdb.com/v4/game_videos', 'Game Videos'),
        ('https://api.igdb.com/v4/keywords', 'Keywords'),
        ('https://api.igdb.com/v4/screenshots', 'Screenshots'),
        ('https://api.igdb.com/v4/search', 'Search')
    ], validators=[DataRequired()])
    query = TextAreaField('Query', validators=[DataRequired()])
    submit = SubmitField('Submit')
    
class AddGameForm(FlaskForm):
    igdb_id = IntegerField('IGDB ID', validators=[DataRequired(), NumberRange()], widget=TextInput())
    name = StringField('Name', validators=[
        DataRequired(), 
        Regexp(r'^[\w\d\s\-!?\'"]+$', message="Name must only contain letters, numbers, dashes, exclamation marks, question marks, and apostrophes.")
    ])
    summary = TextAreaField('Summary', validators=[Optional()])
    storyline = TextAreaField('Storyline', validators=[Optional()])
    url = StringField('URL', validators=[Optional(), URL()])
    full_disk_path = StringField('Full Disk Path', validators=[DataRequired()], widget=TextInput())
    video_urls = StringField('Video URLs', validators=[Optional(), URL()])
    submit = SubmitField('Save')
    
    
class ClearDownloadRequestsForm(FlaskForm):
    submit = SubmitField('CLEAR')
    
class CsrfProtectForm(FlaskForm):
    pass
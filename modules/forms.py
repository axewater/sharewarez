# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, SubmitField, PasswordField, TextAreaField, RadioField, FloatField, DateTimeField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Regexp, URL,Email
from wtforms.widgets import TextInput
from wtforms_sqlalchemy.fields import QuerySelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.fields import URLField, DateField
from modules.models import Status, Category, genre_choices, game_mode_choices, theme_choices, platform_choices, player_perspective_choices, developer_choices, publisher_choices

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

        ('https://api.igdb.com/v4/games', 'Games'),
        ('https://api.igdb.com/v4/search', 'Search'),
        ('https://api.igdb.com/v4/screenshots', 'Screenshots'),
        ('https://api.igdb.com/v4/covers', 'Covers'),
        ('https://api.igdb.com/v4/game_videos', 'Game Videos'),
        ('https://api.igdb.com/v4/keywords', 'Keywords'),
        ('https://api.igdb.com/v4/involved_companies', 'InvolvedCompanies')

    ], validators=[DataRequired()])
    query = TextAreaField('Query', validators=[DataRequired()])
    submit = SubmitField('Submit')


class AddGameForm(FlaskForm):
    # Existing fields
    igdb_id = IntegerField('IGDB ID', validators=[DataRequired(), NumberRange()], widget=TextInput())
    name = StringField('Name', validators=[DataRequired()])
    summary = TextAreaField('Summary', validators=[Optional()])
    storyline = TextAreaField('Storyline', validators=[Optional()])
    url = StringField('URL', validators=[Optional(), URL()])
    full_disk_path = StringField('Full Disk Path', validators=[DataRequired()], widget=TextInput())
    video_urls = StringField('Video URLs', validators=[Optional(), URL()])
    aggregated_rating = FloatField('Aggregated Rating', validators=[Optional()])
    first_release_date = DateField('First Release Date', format='%Y-%m-%d', validators=[Optional()])
    status = SelectField('Status', choices=[(choice.name, choice.value) for choice in Status], coerce=str, validators=[Optional()])
    category = SelectField('Category', choices=[(choice.name, choice.value) for choice in Category], coerce=str, validators=[Optional()])
    genres = QuerySelectMultipleField('Genres', query_factory=genre_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    game_modes = QuerySelectMultipleField('Game Modes', query_factory=game_mode_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    themes = QuerySelectMultipleField('Themes', query_factory=theme_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    platforms = QuerySelectMultipleField('Platforms', query_factory=platform_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    player_perspectives = QuerySelectMultipleField('Player Perspectives', query_factory=player_perspective_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    developer = QuerySelectMultipleField('Developer', query_factory=developer_choices, get_label='name')
    publisher = QuerySelectMultipleField('Publisher', query_factory=publisher_choices, get_label='name')

    submit = SubmitField('Save')    
    
class ClearDownloadRequestsForm(FlaskForm):
    submit = SubmitField('CLEAR')
    
class CsrfProtectForm(FlaskForm):
    pass
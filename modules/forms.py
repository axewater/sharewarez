# forms.py
import re
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, BooleanField, SubmitField, PasswordField, TextAreaField, RadioField, FloatField, DateTimeField, ValidationError, HiddenField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Regexp, URL,Email, EqualTo
from wtforms.widgets import TextInput
from wtforms_sqlalchemy.fields import QuerySelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.fields import URLField, DateField
from modules.models import Status, Category, genre_choices, game_mode_choices, theme_choices, platform_choices, player_perspective_choices, developer_choices, publisher_choices, LibraryPlatform
from urllib.parse import urlparse
from modules.utils_functions import comma_separated_urls
from modules.utils_themes import ThemeManager
from flask import current_app

class UpdateUnmatchedFolderForm(FlaskForm):
    folder_id = HiddenField('Folder ID', validators=[DataRequired()])
    new_status = HiddenField('New Status', default='Ignore')
    submit = SubmitField('Ignore')

class SetupForm(FlaskForm):
    username = StringField('Admin Username', validators=[
        DataRequired(),
        Length(min=3, max=64),
        Regexp(r'^[\w.]+$', message="Username can only contain letters, numbers, dots and underscores")
    ])
    email = StringField('Admin Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Next Step')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
    
class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class AutoScanForm(FlaskForm):
    folder_path = StringField('Browse Folder Path', validators=[DataRequired()])
    library_uuid = SelectField('Select Library', coerce=str, validators=[DataRequired()])
    scan_mode = RadioField('Select Scan Mode', choices=[('folders', 'My Games are Folders'), ('files', 'My Games are Files')], default='folders')
    remove_missing = BooleanField('Remove missing games')
    submit = SubmitField('AutoScan')


class WhitelistForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Add to Whitelist')

class EditProfileForm(FlaskForm):
    avatar = FileField('Profile Avatar', validators=[
        FileAllowed(['jpg', 'jpeg','png', 'gif'], 'Images only!')
    ])
    
class ScanFolderForm(FlaskForm):
    folder_path = StringField('Folder Path', validators=[DataRequired()])
    scan_mode = RadioField('Select Scan Mode', choices=[('folders', 'My Games are Folders'), ('files', 'My Games are Files')], default='folders')
    library_uuid = SelectField('Select Library', coerce=str, validators=[DataRequired()])
    scan = SubmitField('List Games')
    cancel = SubmitField('Cancel')


class InviteForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(message='Invalid email.')], render_kw={"placeholder": "Enter email to invite"})
    submit = SubmitField('Send Invite')

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
    user_id = SelectField('Choose pirate', coerce=int)
    name = StringField('Pirate Name', validators=[Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    role = StringField('Role', validators=[Length(max=64)])
    state = BooleanField('Account Enabled')
    search = StringField('Search Users')
    is_email_verified = BooleanField('Email Verified', validators=[Optional()])
    about = TextAreaField('Admin Notes', validators=[Optional()])
    submit = SubmitField('Save Changes')
    delete = SubmitField('Walk the plank!')


class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Create User')

    
class IGDBApiForm(FlaskForm):
    endpoint = SelectField('Select API Endpoint', choices=[

        ('https://api.igdb.com/v4/games', 'Games'),
        ('https://api.igdb.com/v4/search', 'Search'),
        ('https://api.igdb.com/v4/screenshots', 'Screenshots'),
        ('https://api.igdb.com/v4/covers', 'Covers'),
        ('https://api.igdb.com/v4/game_videos', 'Game Videos'),
        ('https://api.igdb.com/v4/keywords', 'Keywords'),
        ('https://api.igdb.com/v4/involved_companies', 'InvolvedCompanies'),
        ('https://api.igdb.com/v4/platforms', 'Platforms'),

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
    video_urls = StringField('Video URLs', validators=[Optional(), comma_separated_urls])
    aggregated_rating = FloatField('Aggregated Rating', validators=[Optional()])
    first_release_date = DateField('First Release Date', format='%Y-%m-%d', validators=[Optional()])
    status = SelectField('Status', choices=[(choice.name, choice.value) for choice in Status], coerce=str, validators=[Optional()])
    category = SelectField('Category', choices=[(choice.name, choice.value) for choice in Category], coerce=str, validators=[Optional()])
    genres = QuerySelectMultipleField('Genres', query_factory=genre_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    game_modes = QuerySelectMultipleField('Game Modes', query_factory=game_mode_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    themes = QuerySelectMultipleField('Themes', query_factory=theme_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    platforms = QuerySelectMultipleField('Platforms', query_factory=platform_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    player_perspectives = QuerySelectMultipleField('Player Perspectives', query_factory=player_perspective_choices, get_label='name', widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    developer = StringField('Developer', validators=[Optional()])
    publisher = StringField('Publisher', validators=[Optional()])
    library_uuid = SelectField('Library', coerce=str, validators=[DataRequired()])
    submit = SubmitField('Save')    
    
class ClearDownloadRequestsForm(FlaskForm):
    submit = SubmitField('Clear processing queue')
    
class CsrfProtectForm(FlaskForm):
    pass

class CsrfForm(FlaskForm):
    pass 

class ReleaseGroupForm(FlaskForm):
    rlsgroup = StringField('Release Group', validators=[DataRequired()])
    rlsgroupcs = SelectField('Case-Sensitive Release Group', choices=[('no', 'No'), ('yes', 'Yes')], default='no')
    submit = SubmitField('Add')
    
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Register')

class UserPreferencesForm(FlaskForm):
    items_per_page_choices = [
        ('16', '16'),
        ('20', '20'),
        ('50', '50'),
        ('100', '100'),
        ('500', '500'),
        ('1000', '1000')
    ]
    default_sort_choices = [
        ('name', 'Name'),
        ('rating', 'Rating'),
        ('first_release_date', 'Date Released'),
        ('date_identified', 'Date Added'),
        ('size', 'Filesize')
    ]
    default_sort_order_choices = [
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ]

    items_per_page = SelectField('Max items per Page', choices=items_per_page_choices, coerce=int)
    default_sort = SelectField('Default Sort', choices=default_sort_choices)
    default_sort_order = SelectField('Default Sort Order', choices=default_sort_order_choices)
    theme = SelectField('Theme', choices=[('default', 'Default')])  # Default theme is always an option
    submit = SubmitField('Save Preferences')

    def __init__(self, *args, **kwargs):
        super(UserPreferencesForm, self).__init__(*args, **kwargs)
        theme_manager = ThemeManager(current_app)
        installed_themes = theme_manager.get_installed_themes()
        self.theme.choices = [('default', 'Default')] + [(theme['name'], theme['name']) for theme in installed_themes if theme['name'] != 'Default']


class LibraryForm(FlaskForm):
    name = StringField('Library Name', validators=[DataRequired()])
    platform = SelectField('Platform', choices=[(choice.value, choice.name) for choice in LibraryPlatform], validators=[DataRequired()])
    image = FileField('Library Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])

class ThemeUploadForm(FlaskForm):
    theme_zip = FileField('Theme ZIP File', validators=[
        FileRequired(),
        FileAllowed(['zip'], 'ZIP files only!')
    ])
    submit = SubmitField('Upload Theme')

class IGDBSetupForm(FlaskForm):
    igdb_client_id = StringField('Client ID', validators=[
        DataRequired(),
        Length(min=20, max=50, message='Client ID must be between 20 and 50 characters')
    ])
    igdb_client_secret = StringField('Client Secret', validators=[
        DataRequired(),
        Length(min=20, max=50, message='Client Secret must be between 20 and 50 characters')
    ])
    submit = SubmitField('Complete Setup')
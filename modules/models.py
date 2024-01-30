# modules/models.py
from modules import db
from sqlalchemy import Table
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
from uuid import uuid4

class ReleaseGroup(db.Model):
    __tablename__ = 'filters'

    id = db.Column(db.Integer, primary_key=True)
    rlsgroup = db.Column(db.String, nullable=True)
    rlsgroupcs = db.Column(db.String, nullable=True)

    def __repr__(self):
        return f"<ReleaseGroup id={self.id}, rlsgroup={self.rlsgroup}, rlsgroupcs={self.rlsgroupcs}>"


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(64), nullable=False)
    state = db.Column(db.Boolean, default=True)
    about = db.Column(db.String(64), unique=True, nullable=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    lastlogin = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String(36), unique=True, nullable=False, default=str(uuid4()))
    avatarpath = db.Column(db.String(256), default='avatars_users/default.jpg')
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(256), nullable=True)
    password_reset_token = db.Column(db.String(256), nullable=True)
    token_creation_time = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User id={self.id}, name={self.name}, email={self.email}>"


class Whitelist(db.Model):
    __tablename__ = 'whitelist'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)


class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    banned_name = db.Column(db.String, unique=True, nullable=False)
    
    
    
    # Character Model
class Character(db.Model):
    __tablename__ = 'characters'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    level = db.Column(db.Integer, default=1)
    experience = db.Column(db.Integer, default=0)
    health = db.Column(db.Integer)
    mana = db.Column(db.Integer)
    strength = db.Column(db.Integer)
    agility = db.Column(db.Integer)
    intelligence = db.Column(db.Integer)
    location = db.Column(db.String(128))
    inventory = db.relationship('Inventory', backref='character', lazy=True)

    def __repr__(self):
        return f"<Character id={self.id}, name={self.name}>"

# Inventory Model
class Inventory(db.Model):
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    def __repr__(self):
        return f"<Inventory id={self.id}, item_id={self.item_id}, quantity={self.quantity}>"

# Items Model
class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(64))
    stats = db.Column(db.String(256))

    def __repr__(self):
        return f"<Item id={self.id}, name={self.name}>"

# Monsters Model
class Monster(db.Model):
    __tablename__ = 'monsters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    level = db.Column(db.Integer)
    health = db.Column(db.Integer)
    attack = db.Column(db.Integer)
    defense = db.Column(db.Integer)
    loot_table_id = db.Column(db.Integer, db.ForeignKey('loot_tables.id'))

    def __repr__(self):
        return f"<Monster id={self.id}, name={self.name}>"
    
# GameLevels Model
class GameLevel(db.Model):
    __tablename__ = 'game_levels'

    id = db.Column(db.Integer, primary_key=True)
    map_data = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer)

    def __repr__(self):
        return f"<GameLevel id={self.id}, difficulty={self.difficulty}>"

# GameSessions Model
class GameSession(db.Model):
    __tablename__ = 'game_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    current_level_id = db.Column(db.Integer, db.ForeignKey('game_levels.id'))
    session_data = db.Column(db.Text)

    def __repr__(self):
        return f"<GameSession id={self.id}, user_id={self.user_id}, character_id={self.character_id}>"

# Spells/Skills Model
class SpellSkill(db.Model):
    __tablename__ = 'spells_skills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    mana_cost = db.Column(db.Integer)
    cooldown = db.Column(db.Integer)
    effect = db.Column(db.String(256))

    def __repr__(self):
        return f"<SpellSkill id={self.id}, name={self.name}>"

# LootTable Model
class LootTable(db.Model):
    __tablename__ = 'loot_tables'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    drop_chance = db.Column(db.Float)

    def __repr__(self):
        return f"<LootTable id={self.id}, item_id={self.item_id}, drop_chance={self.drop_chance}>"


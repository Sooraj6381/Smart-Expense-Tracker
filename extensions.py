
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Database connection manager
db = SQLAlchemy()

# User login manager
login_manager = LoginManager()

# CSRF security protection
csrf = CSRFProtect()

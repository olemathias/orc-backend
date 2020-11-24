from django_auth_ldap.config import LDAPSearch, GroupOfNamesType
import ldap
from pathlib import Path
import os
import datetime

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'SECRET_KEY', 'v!rv367j9!lxb&i@x4)w23(-6jv!!x(um4%)xtu=belb&b%h86')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(' ')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'vm.apps.VmConfig',
    'ipam.apps.IpamConfig',
    'django_rq',
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt.token_blacklist',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'orc.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'orc.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

if os.environ.get('DB_NAME') is None:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': os.environ.get('DB_NAME'),
            'USER': os.environ.get('DB_USER'),
            'PASSWORD': os.environ.get('DB_PASSWORD'),
            'HOST': os.environ.get('DB_HOST'),
            'PORT': os.environ.get('DB_PORT', 5432),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOGIN_REDIRECT_URL = os.environ.get('LOGIN_REDIRECT_URL', '/')
LOGOUT_REDIRECT_URL = os.environ.get('LOGOUT_REDIRECT_URL', '/')

STATIC_URL = os.environ.get('STATIC_URL', '/static/')

RQ_QUEUES = {
    'default': {
        'HOST': os.environ.get('RQ_QUEUES_HOST', 'localhost'),
        'PORT': os.environ.get('RQ_QUEUES_PORT', 6379),
        'DB': os.environ.get('RQ_QUEUES_DB', 15),
        'DEFAULT_TIMEOUT': os.environ.get('RQ_QUEUES_TIMEOUT', 360),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
}

CORS_ALLOW_ALL_ORIGINS = True

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': datetime.timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': datetime.timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,

    'AUTH_HEADER_TYPES': ('Bearer', 'JWT'),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

##### LDAP #####

# Read secret from file
def _read_secret(secret_name, default=None):
    try:
        f = open(BASE_DIR / secret_name, 'r', encoding='utf-8')
    except EnvironmentError:
        return default
    else:
        with f:
            return f.readline().strip()

# Baseline configuration.
AUTH_LDAP_SERVER_URI = os.environ.get('AUTH_LDAP_SERVER_URI', 'ldap://ipa1.msbone.net')
LDAP_IGNORE_CERT_ERRORS = os.environ.get('LDAP_IGNORE_CERT_ERRORS', 'True').lower() == 'true'

AUTH_LDAP_BIND_DN = os.environ.get('AUTH_LDAP_BIND_DN', 'uid=orc,cn=users,cn=accounts,dc=msbone,dc=net')
AUTH_LDAP_BIND_PASSWORD = _read_secret('auth_ldap_bind_password', os.environ.get('AUTH_LDAP_BIND_PASSWORD', ''))

AUTH_LDAP_USER_SEARCH_BASEDN = os.environ.get('AUTH_LDAP_USER_SEARCH_BASEDN', 'cn=users,cn=accounts,dc=msbone,dc=net')
AUTH_LDAP_USER_SEARCH_ATTR = os.environ.get('AUTH_LDAP_USER_SEARCH_ATTR', 'uid')
AUTH_LDAP_USER_SEARCH = LDAPSearch(AUTH_LDAP_USER_SEARCH_BASEDN,
                                   ldap.SCOPE_SUBTREE,
                                   "(" + AUTH_LDAP_USER_SEARCH_ATTR + "=%(user)s)")

# Populate the Django user from the LDAP directory.
AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": os.environ.get('AUTH_LDAP_ATTR_FIRSTNAME', 'givenName'),
    "last_name": os.environ.get('AUTH_LDAP_ATTR_LASTNAME', 'sn'),
    "email": os.environ.get('AUTH_LDAP_ATTR_MAIL', 'mail')
}

# Set up the basic group parameters.
AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
    os.environ.get('AUTH_LDAP_GROUP_SEARCH', 'cn=groups,cn=accounts,dc=msbone,dc=net'),
    ldap.SCOPE_SUBTREE,
    "(objectClass=groupOfNames)",
)

AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(name_attr="cn")

AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    "is_active": os.environ.get('AUTH_LDAP_REQUIRE_GROUP_DN', 'cn=admins,cn=groups,cn=accounts,dc=msbone,dc=net'),
    "is_staff": os.environ.get('AUTH_LDAP_IS_ADMIN_DN', 'cn=admins,cn=groups,cn=accounts,dc=msbone,dc=net'),
    "is_superuser": os.environ.get('AUTH_LDAP_IS_SUPERUSER_DN', 'cn=admins,cn=groups,cn=accounts,dc=msbone,dc=net')
}

AUTH_LDAP_CACHE_TIMEOUT = int(os.environ.get('AUTH_LDAP_CACHE_TIMEOUT', 600))

# Keep ModelBackend around for per-user permissions and maybe a local
# superuser.
AUTHENTICATION_BACKENDS = (
    "django_auth_ldap.backend.LDAPBackend",
    "django.contrib.auth.backends.ModelBackend",
)

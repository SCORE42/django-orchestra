"""
Django settings for {{ project_name }} project.

Generated by 'django-admin startproject' using Django {{ django_version }}.

For more information on this file, see
https://docs.djangoproject.com/en/{{ docs_version }}/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/{{ docs_version }}/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/{{ docs_version }}/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '{{ secret_key }}'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


# Application definition

INSTALLED_APPS = [
    # django-orchestra apps
    'orchestra',
    'orchestra.contrib.accounts',
    'orchestra.contrib.systemusers',
    'orchestra.contrib.contacts',
    'orchestra.contrib.orchestration',
    'orchestra.contrib.bills',
    'orchestra.contrib.payments',
    'orchestra.contrib.tasks',
    'orchestra.contrib.mailer',
    'orchestra.contrib.history',
    'orchestra.contrib.issues',
    'orchestra.contrib.services',
    'orchestra.contrib.plans',
    'orchestra.contrib.orders',
    'orchestra.contrib.domains',
    'orchestra.contrib.mailboxes',
    'orchestra.contrib.lists',
    'orchestra.contrib.webapps',
    'orchestra.contrib.websites',
    'orchestra.contrib.letsencrypt',
    'orchestra.contrib.databases',
    'orchestra.contrib.vps',
    'orchestra.contrib.saas',
    'orchestra.contrib.miscellaneous',

    # Third-party apps
    'django_extensions',
    'djcelery',
    'fluent_dashboard',
    'admin_tools',
    'admin_tools.theming',
    'admin_tools.menu',
    'admin_tools.dashboard',
    'rest_framework',
    'rest_framework.authtoken',
    'passlib.ext.django',
    'django_countries',
#    'debug_toolbar',

    # Django.contrib
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin.apps.SimpleAdminConfig',

    # Last to load
    'orchestra.contrib.resources',
    'orchestra.contrib.settings',
#    'django_nose',
]


ROOT_URLCONF = '{{ project_name }}.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'orchestra.core.context_processors.site',
            ],
        },
    },
]


WSGI_APPLICATION = '{{ project_name }}.wsgi.application'


# Database
# https://docs.djangoproject.com/en/{{ docs_version }}/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        'USER': '',         # Not used with sqlite3.
        'PASSWORD': '',     # Not used with sqlite3.
        'HOST': '',       # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                # Set to empty string for default. Not used with sqlite3.
        'CONN_MAX_AGE': 60*10      # Enable persistent connections
    }
}


# Internationalization
# https://docs.djangoproject.com/en/{{ docs_version }}/topics/i18n/

LANGUAGE_CODE = 'en-us'


try:
    TIME_ZONE = open('/etc/timezone', 'r').read().strip()
except IOError:
    TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/{{ docs_version }}/howto/static-files/

STATIC_URL = '/static/'


# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Absolute filesystem path to the directory that will hold user-uploaded files.
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Path used for database translations files
LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale'),
)

ORCHESTRA_SITE_NAME = '{{ project_name }}'


MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    # 'django.middleware.locale.LocaleMiddleware'
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'orchestra.core.caches.RequestCacheMiddleware',
    # also handles transations, ATOMIC_REQUESTS does not wrap middlewares
    'orchestra.contrib.orchestration.middlewares.OperationsMiddleware',
)


AUTH_USER_MODEL = 'accounts.Account'


AUTHENTICATION_BACKENDS = [
    'orchestra.permissions.auth.OrchestraPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
]


EMAIL_BACKEND = 'orchestra.contrib.mailer.backends.EmailBackend'


#################################
## 3RD PARTY APPS CONIGURATION ##
#################################

# Admin Tools
ADMIN_TOOLS_MENU = 'orchestra.admin.menu.OrchestraMenu'

# Fluent dashboard
ADMIN_TOOLS_INDEX_DASHBOARD = 'orchestra.admin.dashboard.OrchestraIndexDashboard'
FLUENT_DASHBOARD_ICON_THEME = '../orchestra/icons'


# Django-celery
import djcelery
djcelery.setup_loader()
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'


# rest_framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'orchestra.permissions.api.OrchestraPermissionBackend',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        ('rest_framework.filters.DjangoFilterBackend',)
    ),
}


# Use a UNIX compatible hash
PASSLIB_CONFIG = (
    "[passlib]\n"
    "schemes = sha512_crypt, django_pbkdf2_sha256, django_pbkdf2_sha1, "
    "    django_bcrypt, django_bcrypt_sha256, django_salted_sha1, des_crypt, "
    "    django_salted_md5, django_des_crypt, hex_md5, bcrypt, phpass\n"
    "default = sha512_crypt\n"
    "deprecated = django_pbkdf2_sha1, django_salted_sha1, django_salted_md5, "
    "    django_des_crypt, des_crypt, hex_md5\n"
    "all__vary_rounds = 0.05\n"
    "django_pbkdf2_sha256__min_rounds = 10000\n"
    "sha512_crypt__min_rounds = 80000\n"
    "staff__django_pbkdf2_sha256__default_rounds = 12500\n"
    "staff__sha512_crypt__default_rounds = 100000\n"
    "superuser__django_pbkdf2_sha256__default_rounds = 15000\n"
    "superuser__sha512_crypt__default_rounds = 120000\n"
)

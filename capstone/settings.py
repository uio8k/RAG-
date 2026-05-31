from pathlib import Path
import os
from dotenv import load_dotenv

# 0. 加载 .env 环境变量（必须在其他配置之前）
load_dotenv(os.path.join(Path(__file__).resolve().parent.parent, '.env'))

# 1. 基础路径定义
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. 安全设置
SECRET_KEY = 'django-insecure-j1_1q20c^ul&3n!r*ijg91tyziyaxii9t5ckptg3g2)w0_39%$'
DEBUG = True
ALLOWED_HOSTS = []

# 3. 应用注册 (添加了 'stock')
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'stock', # 你的应用
]

# 4. 中间件
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'capstone.urls'

# 5. 模板配置
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'capstone.wsgi.application'

# 6. 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 7. 指定你的自定义 User 模型 (必须加这一行)
AUTH_USER_MODEL = 'stock.User'

# 8. 密码验证
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 9. 语言与时区 (改为中国时区方便你查看交易记录)
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# 10. 静态文件配置 (CSS, JS, 你的图片)
STATIC_URL = 'static/'
import os
STATICFILES_DIRS = [
    BASE_DIR / "stock" / "static", 
]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
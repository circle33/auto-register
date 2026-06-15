"""ChatGPT2 浏览器注册常量。"""
from __future__ import annotations

import random
import string

# ── URL ────────────────────────────────────────────────────────────────────
CHATGPT_APP = "https://chatgpt.com/"
OPENAI_AUTH = "https://auth.openai.com/"
EMAIL_VERIFICATION_URL = "https://auth.openai.com/email-verification"
ABOUT_YOU_URL = "https://auth.openai.com/about-you"

# ── XPath 选择器（用户指定） ───────────────────────────────────────────────
LOGIN_BUTTON_XPATH = '//*[@id="conversation-header-actions"]/div/div/button[2]'
EMAIL_FORM_XPATH = '//*[@id="radix-_r_1j_"]/div/div/div/form'
EMAIL_INPUT_XPATH = '//*[@id="email"]'
EMAIL_SUBMIT_XPATH = '//*[@id="radix-_r_1j_"]/div/div/div/form/button'
OTP_INPUT_XPATH = '//*[@id="_R_35H5_-code"]'
OTP_SUBMIT_XPATH = '//*[@id="_R_35H5_"]/div[2]/div[1]/div[1]/button'
NAME_INPUT_XPATH = '//*[@id="_r_3_-name"]'
AGE_INPUT_XPATH = '//*[@id="_r_3_-age"]'
ABOUT_YOU_SUBMIT_XPATH = '//*[@id="_r_3_"]/div[2]/div/button'

# ── Fallback CSS 选择器（当 Radix 动态 ID 变化时） ─────────────────────────
EMAIL_INPUT_FALLBACK = 'input[type="email"], input[name="email"], input[id*="email" i]'
OTP_INPUT_FALLBACK = 'input[inputmode="numeric"], input[autocomplete="one-time-code"], input[name*="code" i], input[id*="code" i]'
NAME_INPUT_FALLBACK = 'input[name*="name" i], input[id*="name" i], input[autocomplete="name"]'
SUBMIT_BUTTON_FALLBACK = 'button[type="submit"]'

# ── 等待时间（秒） ──────────────────────────────────────────────────────────
LOGIN_FORM_WAIT = 10
NETWORK_IDLE_TIMEOUT = 30
PAGE_LOAD_TIMEOUT = 30
OTP_POLL_TIMEOUT = 120
ELEMENT_WAIT_TIMEOUT = 15

# ── 随机姓名 / 年龄 ────────────────────────────────────────────────────────
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Daniel", "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark",
    "Margaret", "Donald", "Sandra", "Steven", "Ashley", "Paul", "Dorothy",
    "Andrew", "Kimberly", "Joshua", "Emily", "Kenneth", "Donna",
    "Kevin", "Michelle", "Brian", "Carol", "George", "Amanda", "Timothy",
    "Melissa", "Ronald", "Deborah", "Edward", "Stephanie", "Jason", "Rebecca",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
]


def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_age(min_age: int = 20, max_age: int = 40) -> int:
    return random.randint(min_age, max_age)


def random_password(length: int = 16) -> str:
    specials = ",._!@#"
    required = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
        random.choice(specials),
    ]
    pool = string.ascii_letters + string.digits + specials
    required.extend(random.choice(pool) for _ in range(length - len(required)))
    random.shuffle(required)
    return "".join(required)

# noinspection PyUnresolvedReferences
from misc.base_config import *
import time

user_query_and_count = [
    ('location:china followers:>200', 1000),
    ('location:china followers:100..200', 1000),
    ('location:PRC followers:>=100', 1000),
]
count_per_request = 100
cache_time = 86400
contribution_year = 3
past = int(time.time()) - int(365 * 24 * 3600 * contribution_year)

extra_user = [
    'guaxiao',
    'vczh',
    'JeffreyZhao',
    'librehat',
    'aa65535',
    'riobard',
    'gyteng',
    'zonyitoo',
    'icylogic',
    'GangZhuo',
    'xinzhengzhang',
    'zhouxinyu',
    'rebornix',
]
